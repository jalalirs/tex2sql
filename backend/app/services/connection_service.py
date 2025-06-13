import os
import json
import uuid
import shutil
import asyncio
import pyodbc
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from datetime import datetime
import logging

from app.models.database import Connection, ColumnDescription, TrainingExample, TrainingTask, ConnectionStatus
from app.models.schemas import ConnectionCreate, ConnectionResponse, ConnectionTestResult, ColumnDescriptionItem, TrainingDataView
from app.models.vanna_models import DatabaseConfig, ColumnInfo
from app.core.sse_manager import sse_manager
from app.utils.sse_utils import SSELogger
from app.config import settings

logger = logging.getLogger(__name__)

class ConnectionService:
    """Service for managing database connections"""
    
    def __init__(self):
        self.data_dir = settings.DATA_DIR
    
    async def test_connection(self, connection_data: ConnectionCreate, task_id: str) -> ConnectionTestResult:
        """Test database connection and analyze schema"""
        sse_logger = SSELogger(sse_manager, task_id, "connection_test")
        
        try:
            await sse_logger.info(f"Starting connection test for {connection_data.name}")
            await sse_logger.progress(10, "Connecting to database...")
            
            # Create database config
            db_config = DatabaseConfig(
                server=connection_data.server,
                database_name=connection_data.database_name,
                username=connection_data.username,
                password=connection_data.password,
                table_name=connection_data.table_name
            )
            
            # Test connection
            conn_str = db_config.to_odbc_connection_string()
            
            try:
                cnxn = pyodbc.connect(conn_str, timeout=30)
                cursor = cnxn.cursor()
                await sse_logger.progress(30, "Connection successful, analyzing schema...")
                
            except pyodbc.Error as ex:
                error_msg = f"Database connection failed: {str(ex)}"
                await sse_logger.error(error_msg)
                return ConnectionTestResult(
                    success=False,
                    error_message=error_msg,
                    task_id=task_id
                )
            
            # Parse table name
            if '.' in connection_data.table_name:
                table_schema, table_name_only = connection_data.table_name.split('.', 1)
            else:
                table_schema = 'dbo'
                table_name_only = connection_data.table_name
            
            await sse_logger.progress(40, f"Analyzing table: {connection_data.table_name}")
            
            # Get schema information
            column_info = await self._analyze_table_schema(cursor, table_schema, table_name_only, sse_logger)
            
            await sse_logger.progress(70, "Fetching sample data...")
            
            # Get sample data
            sample_data = await self._get_sample_data(cursor, connection_data.table_name, sse_logger)
            
            cnxn.close()
            
            await sse_logger.progress(100, "Connection test completed successfully")
            await sse_logger.info(f"Found {len(column_info)} columns and {len(sample_data)} sample rows")
            
            return ConnectionTestResult(
                success=True,
                sample_data=sample_data,
                column_info=column_info,
                task_id=task_id
            )
            
        except Exception as e:
            error_msg = f"Connection test failed: {str(e)}"
            logger.error(error_msg)
            await sse_logger.error(error_msg)
            return ConnectionTestResult(
                success=False,
                error_message=error_msg,
                task_id=task_id
            )
    
    async def _analyze_table_schema(self, cursor, table_schema: str, table_name: str, sse_logger: SSELogger) -> Dict[str, Any]:
        """Analyze table schema and data characteristics"""
        columns_info = {}
        
        try:
            # Get column information
            cursor.execute(f"""
                SELECT COLUMN_NAME, DATA_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = '{table_schema}' AND TABLE_NAME = '{table_name}'
                ORDER BY ORDINAL_POSITION;
            """)
            schema_cols = cursor.fetchall()
            
            total_columns = len(schema_cols)
            await sse_logger.info(f"Analyzing {total_columns} columns...")
            
            for idx, (col_name, data_type) in enumerate(schema_cols):
                progress = 40 + int((idx / total_columns) * 25)  # 40-65%
                await sse_logger.progress(progress, f"Analyzing column: {col_name}")
                
                col_info = {'data_type': data_type}
                full_table_name = f"{table_schema}.{table_name}"
                
                # Categorical Data Analysis
                if data_type.lower() in ['varchar', 'nvarchar', 'char', 'nchar', 'text', 'ntext']:
                    try:
                        cursor.execute(f"""
                            SELECT COUNT(DISTINCT [{col_name}]), AVG(CAST(LEN([{col_name}]) AS DECIMAL(10,2))) 
                            FROM {full_table_name} 
                            WHERE [{col_name}] IS NOT NULL;
                        """)
                        result = cursor.fetchone()
                        if result:
                            distinct_count, avg_len = result
                            
                            if distinct_count and distinct_count < 50 and (avg_len is None or avg_len < 50):
                                cursor.execute(f"""
                                    SELECT DISTINCT TOP 50 [{col_name}] 
                                    FROM {full_table_name} 
                                    WHERE [{col_name}] IS NOT NULL;
                                """)
                                categories = [str(row[0]) for row in cursor.fetchall()]
                                col_info['categories'] = categories
                                col_info['variable_range'] = f"Categories: {', '.join(categories[:10])}" + ("..." if len(categories) > 10 else "")
                    except Exception as e:
                        await sse_logger.warning(f"Could not analyze categorical data for {col_name}: {str(e)}")
                
                # Numerical Data Analysis
                elif data_type.lower() in ['int', 'bigint', 'smallint', 'tinyint', 'decimal', 'numeric', 'float', 'real']:
                    try:
                        cursor.execute(f"""
                            SELECT MIN(CAST([{col_name}] AS FLOAT)), MAX(CAST([{col_name}] AS FLOAT)), AVG(CAST([{col_name}] AS FLOAT)) 
                            FROM {full_table_name} 
                            WHERE [{col_name}] IS NOT NULL;
                        """)
                        result = cursor.fetchone()
                        if result:
                            min_val, max_val, avg_val = result
                            if min_val is not None and max_val is not None:
                                col_info['range'] = {'min': min_val, 'max': max_val, 'avg': avg_val}
                                col_info['variable_range'] = f"Range: {min_val:.2f} - {max_val:.2f} (Avg: {avg_val:.2f})"
                    except Exception as e:
                        await sse_logger.warning(f"Could not analyze numerical data for {col_name}: {str(e)}")
                
                # Date/Time Data Analysis
                elif data_type.lower() in ['date', 'datetime', 'datetime2', 'smalldatetime', 'timestamp']:
                    try:
                        cursor.execute(f"""
                            SELECT MIN([{col_name}]), MAX([{col_name}]) 
                            FROM {full_table_name} 
                            WHERE [{col_name}] IS NOT NULL;
                        """)
                        result = cursor.fetchone()
                        if result:
                            min_date, max_date = result
                            if min_date and max_date:
                                col_info['date_range'] = {'min': str(min_date), 'max': str(max_date)}
                                col_info['variable_range'] = f"Date range: {min_date} to {max_date}"
                    except Exception as e:
                        await sse_logger.warning(f"Could not analyze date data for {col_name}: {str(e)}")
                
                if 'variable_range' not in col_info:
                    col_info['variable_range'] = f"Type: {data_type}"
                
                columns_info[col_name] = col_info
            
            await sse_logger.info(f"Schema analysis complete for {len(columns_info)} columns")
            return columns_info
            
        except Exception as e:
            await sse_logger.error(f"Schema analysis failed: {str(e)}")
            raise
    
    async def _get_sample_data(self, cursor, table_name: str, sse_logger: SSELogger) -> List[Dict[str, Any]]:
        """Get sample data from the table"""
        try:
            cursor.execute(f"SELECT TOP 10 * FROM {table_name};")
            rows = cursor.fetchall()
            
            # Get column names
            columns = [column[0] for column in cursor.description]
            
            # Convert to list of dictionaries
            sample_data = []
            for row in rows:
                row_dict = {}
                for i, value in enumerate(row):
                    # Convert to JSON-serializable types
                    if value is None:
                        row_dict[columns[i]] = None
                    elif hasattr(value, 'isoformat'):  # datetime objects
                        row_dict[columns[i]] = value.isoformat()
                    else:
                        row_dict[columns[i]] = str(value)
                sample_data.append(row_dict)
            
            await sse_logger.info(f"Retrieved {len(sample_data)} sample rows")
            return sample_data
            
        except Exception as e:
            await sse_logger.warning(f"Could not retrieve sample data: {str(e)}")
            return []
    
    async def create_connection(self, db: AsyncSession, connection_data: ConnectionCreate, 
                             column_descriptions: Optional[List[ColumnDescriptionItem]] = None) -> ConnectionResponse:
        """Create a new connection"""
        try:
            # Create connection record
            connection = Connection(
                name=connection_data.name,
                server=connection_data.server,
                database_name=connection_data.database_name,
                username=connection_data.username,
                password=connection_data.password,  # TODO: Encrypt in production
                table_name=connection_data.table_name,
                status=ConnectionStatus.TEST_SUCCESS,
                column_descriptions_uploaded=bool(column_descriptions)
            )
            
            db.add(connection)
            await db.flush()  # Get the ID without committing
            
            connection_id = str(connection.id)
            
            # Create data directory
            connection_dir = os.path.join(self.data_dir, "connections", connection_id)
            os.makedirs(connection_dir, exist_ok=True)
            
            # Save database config
            db_config = {
                "server": connection_data.server,
                "database_name": connection_data.database_name,
                "username": connection_data.username,
                "password": connection_data.password,
                "table_name": connection_data.table_name
            }
            
            config_path = os.path.join(connection_dir, "db_config.json")
            with open(config_path, 'w') as f:
                json.dump(db_config, f, indent=2)
            
            # Save column descriptions if provided
            if column_descriptions:
                for col_desc in column_descriptions:
                    column_desc_record = ColumnDescription(
                        connection_id=connection.id,
                        column_name=col_desc.column_name,
                        description=col_desc.description,
                        data_type=col_desc.data_type,
                        variable_range=col_desc.variable_range
                    )
                    db.add(column_desc_record)
                
                # Also save as CSV file
                csv_path = os.path.join(connection_dir, "column_descriptions.csv")
                with open(csv_path, 'w', newline='') as f:
                    f.write("column,description\n")
                    for col_desc in column_descriptions:
                        # Escape commas and quotes in CSV
                        desc = col_desc.description.replace('"', '""') if col_desc.description else ""
                        f.write(f'"{col_desc.column_name}","{desc}"\n')
            
            await db.commit()
            
            # Convert to response model
            return ConnectionResponse(
                id=connection_id,
                name=connection.name,
                server=connection.server,
                database_name=connection.database_name,
                table_name=connection.table_name,
                status=connection.status,
                test_successful=connection.test_successful,
                column_descriptions_uploaded=connection.column_descriptions_uploaded,
                generated_examples_count=connection.generated_examples_count,
                created_at=connection.created_at,
                trained_at=connection.trained_at
            )
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to create connection: {e}")
            raise
    
    async def get_connection(self, db: AsyncSession, connection_id: str) -> Optional[ConnectionResponse]:
        """Get a connection by ID"""
        try:
            stmt = select(Connection).where(Connection.id == uuid.UUID(connection_id))
            result = await db.execute(stmt)
            connection = result.scalar_one_or_none()
            
            if not connection:
                return None
            
            return ConnectionResponse(
                id=str(connection.id),
                name=connection.name,
                server=connection.server,
                database_name=connection.database_name,
                table_name=connection.table_name,
                status=connection.status,
                test_successful=connection.test_successful,
                column_descriptions_uploaded=connection.column_descriptions_uploaded,
                generated_examples_count=connection.generated_examples_count,
                created_at=connection.created_at,
                trained_at=connection.trained_at
            )
            
        except Exception as e:
            logger.error(f"Failed to get connection {connection_id}: {e}")
            return None
    
    async def list_connections(self, db: AsyncSession) -> List[ConnectionResponse]:
        """List all connections"""
        try:
            stmt = select(Connection).order_by(Connection.created_at.desc())
            result = await db.execute(stmt)
            connections = result.scalars().all()
            
            return [
                ConnectionResponse(
                    id=str(conn.id),
                    name=conn.name,
                    server=conn.server,
                    database_name=conn.database_name,
                    table_name=conn.table_name,
                    status=conn.status,
                    test_successful=conn.test_successful,
                    column_descriptions_uploaded=conn.column_descriptions_uploaded,
                    generated_examples_count=conn.generated_examples_count,
                    created_at=conn.created_at,
                    trained_at=conn.trained_at
                )
                for conn in connections
            ]
            
        except Exception as e:
            logger.error(f"Failed to list connections: {e}")
            return []
    
    async def get_training_data_view(self, db: AsyncSession, connection_id: str) -> Optional[TrainingDataView]:
        """Get training data view for a connection"""
        try:
            # Get connection
            connection = await self.get_connection(db, connection_id)
            if not connection:
                return None
            
            # Get column descriptions from database
            stmt = select(ColumnDescription).where(ColumnDescription.connection_id == uuid.UUID(connection_id))
            result = await db.execute(stmt)
            column_descriptions = result.scalars().all()
            
            column_desc_items = [
                ColumnDescriptionItem(
                    column_name=col.column_name,
                    data_type=col.data_type,
                    variable_range=col.variable_range,
                    description=col.description
                )
                for col in column_descriptions
            ]
            
            # Get generated examples
            stmt = select(TrainingExample).where(TrainingExample.connection_id == uuid.UUID(connection_id))
            result = await db.execute(stmt)
            examples = result.scalars().all()
            
            generated_examples = [
                {"question": ex.question, "sql": ex.sql}
                for ex in examples
            ]
            
            # Create initial prompt
            initial_prompt = self._create_initial_prompt(connection.table_name)
            
            return TrainingDataView(
                connection_id=connection_id,
                connection_name=connection.name,
                initial_prompt=initial_prompt,
                column_descriptions=column_desc_items,
                generated_examples=generated_examples,
                total_examples=len(generated_examples)
            )
            
        except Exception as e:
            logger.error(f"Failed to get training data view for {connection_id}: {e}")
            return None
    
    def _create_initial_prompt(self, table_name: str) -> str:
        """Create initial prompt for training"""
        return f"""You are a Microsoft SQL Server expert specializing in the {table_name} table. 
Your role is to generate accurate SQL queries based on natural language questions. 

Key Guidelines:
- Use Microsoft SQL Server syntax (square brackets for identifiers, TOP N instead of LIMIT)
- Focus on the single table: {table_name}
- Provide precise, executable queries
- Handle edge cases and NULL values appropriately
- Use appropriate aggregations, filtering, and sorting as needed"""
    
    async def delete_connection(self, db: AsyncSession, connection_id: str) -> bool:
        """Delete a connection and all associated data"""
        try:
            connection_uuid = uuid.UUID(connection_id)
            
            # Delete related records first
            await db.execute(delete(TrainingExample).where(TrainingExample.connection_id == connection_uuid))
            await db.execute(delete(ColumnDescription).where(ColumnDescription.connection_id == connection_uuid))
            await db.execute(delete(TrainingTask).where(TrainingTask.connection_id == connection_id))
            
            # Delete connection
            await db.execute(delete(Connection).where(Connection.id == connection_uuid))
            
            await db.commit()
            
            # Delete data directory
            connection_dir = os.path.join(self.data_dir, "connections", connection_id)
            if os.path.exists(connection_dir):
                shutil.rmtree(connection_dir)
                logger.info(f"Deleted data directory for connection {connection_id}")
            
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to delete connection {connection_id}: {e}")
            return False
    
    async def update_connection_status(self, db: AsyncSession, connection_id: str, status: ConnectionStatus) -> bool:
        """Update connection status"""
        try:
            stmt = select(Connection).where(Connection.id == uuid.UUID(connection_id))
            result = await db.execute(stmt)
            connection = result.scalar_one_or_none()
            
            if not connection:
                return False
            
            connection.status = status
            connection.updated_at = datetime.utcnow()
            
            if status == ConnectionStatus.TRAINED:
                connection.trained_at = datetime.utcnow()
            
            await db.commit()
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to update connection status: {e}")
            return False

# Global connection service instance
connection_service = ConnectionService()