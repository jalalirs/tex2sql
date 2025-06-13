import csv
import io
import os
from typing import List, Dict, Any, Optional
from fastapi import UploadFile, HTTPException
import logging

from app.models.schemas import ColumnDescriptionUpload, ColumnDescriptionItem
from app.config import settings

logger = logging.getLogger(__name__)

class FileHandler:
    """Handle file uploads and processing"""
    
    def __init__(self):
        self.upload_dir = settings.UPLOAD_DIR
        self.max_file_size = settings.MAX_UPLOAD_SIZE
    
    async def process_column_descriptions_csv(self, file: UploadFile) -> List[ColumnDescriptionItem]:
        """Process uploaded column descriptions CSV file"""
        try:
            # Validate file type
            if not file.filename.lower().endswith('.csv'):
                raise HTTPException(status_code=400, detail="File must be a CSV file")
            
            # Read file content
            content = await file.read()
            
            # Check file size
            if len(content) > self.max_file_size:
                raise HTTPException(
                    status_code=400, 
                    detail=f"File too large. Maximum size is {self.max_file_size / 1024 / 1024:.1f}MB"
                )
            
            # Decode content
            try:
                text_content = content.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    text_content = content.decode('latin-1')
                except UnicodeDecodeError:
                    raise HTTPException(status_code=400, detail="Unable to decode file. Please use UTF-8 encoding.")
            
            # Parse CSV
            csv_reader = csv.DictReader(io.StringIO(text_content))
            
            # Validate headers
            fieldnames = csv_reader.fieldnames
            if not fieldnames or 'column' not in fieldnames or 'description' not in fieldnames:
                raise HTTPException(
                    status_code=400, 
                    detail="CSV must have 'column' and 'description' headers"
                )
            
            # Process rows
            column_descriptions = []
            row_count = 0
            
            for row in csv_reader:
                row_count += 1
                
                # Strip whitespace from column name and description
                column_name = row.get('column', '').strip()
                description = row.get('description', '').strip()
                
                if not column_name:
                    logger.warning(f"Empty column name in row {row_count}, skipping")
                    continue
                
                # Validate using Pydantic
                try:
                    validated_row = ColumnDescriptionUpload(
                        column=column_name,
                        description=description
                    )
                    
                    column_descriptions.append(ColumnDescriptionItem(
                        column_name=validated_row.column,
                        description=validated_row.description
                    ))
                    
                except Exception as e:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Invalid data in row {row_count}: {str(e)}"
                    )
            
            if not column_descriptions:
                raise HTTPException(status_code=400, detail="No valid column descriptions found in CSV")
            
            logger.info(f"Processed {len(column_descriptions)} column descriptions from CSV")
            return column_descriptions
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error processing CSV file: {e}")
            raise HTTPException(status_code=500, detail=f"Error processing CSV file: {str(e)}")
    
    async def save_uploaded_file(self, file: UploadFile, connection_id: str) -> str:
        """Save uploaded file to connection directory"""
        try:
            # Create connection upload directory
            connection_dir = os.path.join(self.upload_dir, connection_id)
            os.makedirs(connection_dir, exist_ok=True)
            
            # Generate safe filename
            safe_filename = self._get_safe_filename(file.filename)
            file_path = os.path.join(connection_dir, safe_filename)
            
            # Read and save file
            content = await file.read()
            
            with open(file_path, 'wb') as f:
                f.write(content)
            
            logger.info(f"Saved uploaded file to {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error saving uploaded file: {e}")
            raise HTTPException(status_code=500, detail=f"Error saving file: {str(e)}")
    
    def _get_safe_filename(self, filename: str) -> str:
        """Generate a safe filename"""
        import re
        from datetime import datetime
        
        # Remove path components
        filename = os.path.basename(filename)
        
        # Remove unsafe characters
        safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        
        # Add timestamp to avoid conflicts
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        name, ext = os.path.splitext(safe_name)
        
        return f"{name}_{timestamp}{ext}"
    
    def validate_csv_format(self, content: str) -> Dict[str, Any]:
        """Validate CSV format and return info"""
        try:
            csv_reader = csv.DictReader(io.StringIO(content))
            fieldnames = csv_reader.fieldnames
            
            # Count rows
            row_count = sum(1 for _ in csv_reader)
            
            return {
                "valid": True,
                "headers": fieldnames,
                "row_count": row_count,
                "has_required_headers": fieldnames and 'column' in fieldnames and 'description' in fieldnames
            }
            
        except Exception as e:
            return {
                "valid": False,
                "error": str(e)
            }
    
    def cleanup_connection_files(self, connection_id: str):
        """Clean up files for a connection"""
        try:
            connection_dir = os.path.join(self.upload_dir, connection_id)
            if os.path.exists(connection_dir):
                import shutil
                shutil.rmtree(connection_dir)
                logger.info(f"Cleaned up files for connection {connection_id}")
        except Exception as e:
            logger.error(f"Error cleaning up files for connection {connection_id}: {e}")

# Global file handler instance
file_handler = FileHandler()