from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import uuid
import logging

from app.dependencies import get_db, validate_api_key
from app.services.connection_service import connection_service
from app.models.schemas import (
    ConnectionCreate, ConnectionResponse, ConnectionTestRequest, ConnectionTestResult,
    ConnectionListResponse, TrainingDataView, ColumnDescriptionItem, TaskResponse,
    ConnectionDeleteResponse
)
from app.models.database import TrainingTask
from app.core.sse_manager import sse_manager
from app.utils.file_handler import file_handler
from app.utils.validators import validate_connection_data
from app.config import settings

router = APIRouter(prefix="/connections", tags=["Connections"])
logger = logging.getLogger(__name__)

@router.post("/test", response_model=ConnectionTestResult)
async def test_connection(
    request: ConnectionTestRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(validate_api_key)
):
    """Test database connection and analyze schema"""
    try:
        # Validate connection data
        validation_errors = validate_connection_data(request.connection_data)
        if validation_errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation errors: {', '.join(validation_errors)}"
            )
        
        # Create task for tracking
        task_id = str(uuid.uuid4())
        task = TrainingTask(
            id=task_id,
            connection_id=None,  # No connection yet
            task_type="test_connection",
            status="running"
        )
        
        db.add(task)
        await db.commit()
        
        # Start connection test in background
        background_tasks.add_task(
            _run_connection_test,
            request.connection_data,
            task_id,
            db
        )
        
        return ConnectionTestResult(
            success=True,
            task_id=task_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Connection test failed: {str(e)}"
        )

async def _run_connection_test(connection_data: ConnectionCreate, task_id: str, db: AsyncSession):
    """Background task to run connection test"""
    try:
        # Update task status
        await _update_task_status(db, task_id, "running", 0)
        
        # Run the actual test
        result = await connection_service.test_connection(connection_data, task_id)
        
        # Update task with result
        if result.success:
            await _update_task_status(db, task_id, "completed", 100)
            await sse_manager.send_to_task(task_id, "test_completed", {
                "success": True,
                "sample_data": result.sample_data,
                "column_info": result.column_info,
                "task_id": task_id
            })
        else:
            await _update_task_status(db, task_id, "failed", 0, result.error_message)
            await sse_manager.send_to_task(task_id, "test_failed", {
                "success": False,
                "error": result.error_message,
                "task_id": task_id
            })
            
    except Exception as e:
        logger.error(f"Background connection test failed: {e}")
        await _update_task_status(db, task_id, "failed", 0, str(e))
        await sse_manager.send_to_task(task_id, "test_failed", {
            "success": False,
            "error": str(e),
            "task_id": task_id
        })

@router.post("/", response_model=ConnectionResponse)
async def create_connection(
    name: str = Form(...),
    server: str = Form(...), 
    database_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    table_name: str = Form(...),
    column_descriptions_file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(validate_api_key)
):
    """Create a new database connection"""
    try:
        # Build connection data from form fields
        connection_data = ConnectionCreate(
            name=name,
            server=server,
            database_name=database_name,
            username=username,
            password=password,
            table_name=table_name
        )
        
        # Validate connection data
        validation_errors = validate_connection_data(connection_data)
        if validation_errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation errors: {', '.join(validation_errors)}"
            )
        
        # Process column descriptions if file provided
        column_descriptions = None
        if column_descriptions_file:
            try:
                column_descriptions = await file_handler.process_column_descriptions_csv(column_descriptions_file)
                logger.info(f"Processed {len(column_descriptions)} column descriptions")
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Error processing column descriptions file: {str(e)}"
                )
        
        # Create connection
        connection = await connection_service.create_connection(
            db, connection_data, column_descriptions
        )
        
        logger.info(f"Created connection: {connection.id}")
        return connection
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create connection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create connection: {str(e)}"
        )
    
@router.get("/", response_model=ConnectionListResponse)
async def list_connections(db: AsyncSession = Depends(get_db)):
    """List all connections"""
    try:
        connections = await connection_service.list_connections(db)
        return ConnectionListResponse(
            connections=connections,
            total=len(connections)
        )
    except Exception as e:
        logger.error(f"Failed to list connections: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list connections: {str(e)}"
        )

@router.get("/{connection_id}", response_model=ConnectionResponse)
async def get_connection(
    connection_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific connection"""
    try:
        connection = await connection_service.get_connection(db, connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found"
            )
        return connection
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get connection {connection_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get connection: {str(e)}"
        )

@router.get("/{connection_id}/training-data", response_model=TrainingDataView)
async def get_training_data_view(
    connection_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get training data view for a connection"""
    try:
        training_data = await connection_service.get_training_data_view(db, connection_id)
        if not training_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found or no training data available"
            )
        return training_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get training data view for {connection_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get training data view: {str(e)}"
        )

@router.delete("/{connection_id}", response_model=ConnectionDeleteResponse)
async def delete_connection(
    connection_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete a connection and all associated data"""
    try:
        # Check if connection exists
        connection = await connection_service.get_connection(db, connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found"
            )
        
        # Delete connection
        success = await connection_service.delete_connection(db, connection_id)
        
        if success:
            # Clean up uploaded files
            file_handler.cleanup_connection_files(connection_id)
            
            return ConnectionDeleteResponse(
                success=True,
                message=f"Connection '{connection.name}' deleted successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete connection"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete connection {connection_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete connection: {str(e)}"
        )

@router.post("/{connection_id}/validate-csv")
async def validate_column_descriptions_csv(
    connection_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Validate column descriptions CSV file format"""
    try:
        # Check if connection exists
        connection = await connection_service.get_connection(db, connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found"
            )
        
        # Validate file
        column_descriptions = await file_handler.process_column_descriptions_csv(file)
        
        return {
            "valid": True,
            "column_count": len(column_descriptions),
            "columns": [
                {
                    "column_name": col.column_name,
                    "description": col.description
                }
                for col in column_descriptions[:10]  # Show first 10 for preview
            ],
            "total_columns": len(column_descriptions)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CSV validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV validation failed: {str(e)}"
        )

async def _update_task_status(db: AsyncSession, task_id: str, status: str, progress: int, error_message: str = None):
    """Helper to update task status"""
    try:
        from sqlalchemy import select, update
        from datetime import datetime
        
        stmt = select(TrainingTask).where(TrainingTask.id == task_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        
        if task:
            task.status = status
            task.progress = progress
            if error_message:
                task.error_message = error_message
            if status == "running" and not task.started_at:
                task.started_at = datetime.utcnow()
            elif status in ["completed", "failed"]:
                task.completed_at = datetime.utcnow()
            
            await db.commit()
            
    except Exception as e:
        logger.error(f"Failed to update task status: {e}")