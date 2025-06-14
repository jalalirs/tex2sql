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

from app.models.database import Connection, ColumnDescription, TrainingExample, TrainingTask, ConnectionStatus, User
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
                table_name=connection_data.table_name,
                driver=connection_data.driver if hasattr(connection_data, 'driver') else None
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
    
    # ========================
    # USER-SPECIFIC CONNECTION METHODS (UPDATED)
    # ========================
    
    async def get_user_connection_by_name(self, db: AsyncSession, user_id: str, name: str) -> Optional[Connection]:
        """Check if user already has a connection with this name"""
        try:
            stmt = select(Connection).where(
                Connection.user_id == user_id,
                Connection.name == name
            )
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to check connection name for user {user_id}: {e}")
            return None
    
    async def create_connection_for_user(
        self, 
        db: AsyncSession, 
        user: User,
        connection_data: ConnectionCreate, 
        column_descriptions: Optional[List[ColumnDescriptionItem]] = None
    ) -> ConnectionResponse:
        """Create a new connection for a specific user"""
        try:
            # Create connection record with user_id
            connection = Connection(
                user_id=user.id,  # Associate with user
                name=connection_data.name,
                server=connection_data.server,
                database_name=connection_data.database_name,
                username=connection_data.username,
                password=connection_data.password,  # TODO: Encrypt in production
                table_name=connection_data.table_name,
                driver=getattr(connection_data, 'driver', None),
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
                "user_id": str(user.id),
                "server": connection_data.server,
                "database_name": connection_data.database_name,
                "username": connection_data.username,
                "password": connection_data.password,
                "table_name": connection_data.table_name,
                "driver": getattr(connection_data, 'driver', None)
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
                driver=connection.driver,
                status=connection.status,
                test_successful=connection.test_successful,
                column_descriptions_uploaded=connection.column_descriptions_uploaded,
                generated_examples_count=connection.generated_examples_count,
                total_queries=connection.total_queries or 0,
                last_queried_at=connection.last_queried_at,
                created_at=connection.created_at,
                trained_at=connection.trained_at
            )
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to create connection for user {user.email}: {e}")
            raise
    
    async def list_user_connections(self, db: AsyncSession, user_id: str) -> List[ConnectionResponse]:
        """List all connections for a specific user"""
        try:
            stmt = select(Connection).where(
                Connection.user_id == user_id
            ).order_by(Connection.created_at.desc())
            
            result = await db.execute(stmt)
            connections = result.scalars().all()
            
            return [
                ConnectionResponse(
                    id=str(conn.id),
                    name=conn.name,
                    server=conn.server,
                    database_name=conn.database_name,
                    table_name=conn.table_name,
                    driver=conn.driver,
                    status=conn.status,
                    test_successful=conn.test_successful,
                    column_descriptions_uploaded=conn.column_descriptions_uploaded,
                    generated_examples_count=conn.generated_examples_count,
                    total_queries=conn.total_queries or 0,
                    last_queried_at=conn.last_queried_at,
                    created_at=conn.created_at,
                    trained_at=conn.trained_at
                )
                for conn in connections
            ]
            
        except Exception as e:
            logger.error(f"Failed to list connections for user {user_id}: {e}")
            return []
    
    async def get_user_connection(self, db: AsyncSession, user_id: str, connection_id: str) -> Optional[ConnectionResponse]:
        """Get a connection by ID that belongs to a specific user"""
        try:
            stmt = select(Connection).where(
                Connection.id == uuid.UUID(connection_id),
                Connection.user_id == user_id
            )
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
                driver=connection.driver,
                status=connection.status,
                test_successful=connection.test_successful,
                column_descriptions_uploaded=connection.column_descriptions_uploaded,
                generated_examples_count=connection.generated_examples_count,
                total_queries=connection.total_queries or 0,
                last_queried_at=connection.last_queried_at,
                created_at=connection.created_at,
                trained_at=connection.trained_at
            )
            
        except Exception as e:
            logger.error(f"Failed to get connection {connection_id} for user {user_id}: {e}")
            return None
    
    async def delete_user_connection(self, db: AsyncSession, user_id: str, connection_id: str) -> bool:
        """Delete a connection that belongs to a specific user"""
        try:
            connection_uuid = uuid.UUID(connection_id)
            
            # First verify the connection belongs to the user
            stmt = select(Connection).where(
                Connection.id == connection_uuid,
                Connection.user_id == user_id
            )
            result = await db.execute(stmt)
            connection = result.scalar_one_or_none()
            
            if not connection:
                logger.warning(f"Connection {connection_id} not found for user {user_id}")
                return False
            
            # Delete related records first (cascade deletes will handle conversations/messages)
            await db.execute(delete(TrainingExample).where(TrainingExample.connection_id == connection_uuid))
            await db.execute(delete(ColumnDescription).where(ColumnDescription.connection_id == connection_uuid))
            await db.execute(delete(TrainingTask).where(TrainingTask.connection_id == connection_id))
            
            # Delete connection (conversations and messages will be deleted via cascade)
            await db.execute(delete(Connection).where(
                Connection.id == connection_uuid,
                Connection.user_id == user_id
            ))
            
            await db.commit()
            
            # Delete data directory
            connection_dir = os.path.join(self.data_dir, "connections", connection_id)
            if os.path.exists(connection_dir):
                shutil.rmtree(connection_dir)
                logger.info(f"Deleted data directory for connection {connection_id}")
            
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to delete connection {connection_id} for user {user_id}: {e}")
            return False
    
    # ========================
    # EXISTING METHODS (KEPT FOR TRAINING/ADMIN USE)
    # ========================
    
    async def get_training_data_view(self, db: AsyncSession, connection_id: str) -> Optional[TrainingDataView]:
        """Get training data view for a connection"""
        try:
            # Get connection
            connection = await self.get_connection_by_id(db, connection_id)
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
    
    async def get_connection_by_id(self, db: AsyncSession, connection_id: str) -> Optional[Connection]:
        """Get raw connection object by ID (for internal use)"""
        try:
            stmt = select(Connection).where(Connection.id == uuid.UUID(connection_id))
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get connection {connection_id}: {e}")
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

    async def refresh_connection_schema(
        self, 
        connection_data: ConnectionCreate, 
        connection_id: str, 
        task_id: str
    ) -> ConnectionTestResult:
        """Refresh and store schema information"""
        sse_logger = SSELogger(sse_manager, task_id, "schema_refresh")
        
        try:
            await sse_logger.info(f"Starting schema refresh for connection {connection_id}")
            await sse_logger.progress(10, "Connecting to database...")
            
            # Create database config
            db_config = DatabaseConfig(
                server=connection_data.server,
                database_name=connection_data.database_name,
                username=connection_data.username,
                password=connection_data.password,
                table_name=connection_data.table_name,
                driver=connection_data.driver if hasattr(connection_data, 'driver') else None
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
            
            await sse_logger.progress(90, "Saving schema information...")
            
            # Save schema to storage
            await self._save_schema_data(connection_id, column_info, sample_data)
            
            await sse_logger.progress(100, "Schema refresh completed successfully")
            await sse_logger.info(f"Refreshed schema with {len(column_info)} columns")
            
            return ConnectionTestResult(
                success=True,
                sample_data=sample_data,
                column_info=column_info,
                task_id=task_id
            )
            
        except Exception as e:
            error_msg = f"Schema refresh failed: {str(e)}"
            logger.error(error_msg)
            await sse_logger.error(error_msg)
            return ConnectionTestResult(
                success=False,
                error_message=error_msg,
                task_id=task_id
            )
    
    async def _save_schema_data(
        self, 
        connection_id: str, 
        column_info: Dict[str, Any], 
        sample_data: List[Dict[str, Any]]
    ):
        """Save schema information to storage"""
        try:
            connection_dir = os.path.join(self.data_dir, "connections", connection_id)
            os.makedirs(connection_dir, exist_ok=True)
            
            schema_data = {
                "connection_id": connection_id,
                "last_refreshed": datetime.utcnow().isoformat(),
                "table_info": {
                    "total_columns": len(column_info),
                    "sample_rows": len(sample_data)
                },
                "columns": column_info,
                "sample_data": sample_data[:5]  # Store only first 5 rows as sample
            }
            
            schema_path = os.path.join(connection_dir, "schema.json")
            with open(schema_path, 'w') as f:
                json.dump(schema_data, f, indent=2, default=str)
            
            logger.info(f"Saved schema data for connection {connection_id}")
            
        except Exception as e:
            logger.error(f"Failed to save schema data for {connection_id}: {e}")
            raise
    
    async def get_connection_schema(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get stored schema information"""
        try:
            connection_dir = os.path.join(self.data_dir, "connections", connection_id)
            schema_path = os.path.join(connection_dir, "schema.json")
            
            if not os.path.exists(schema_path):
                return None
            
            with open(schema_path, 'r') as f:
                schema_data = json.load(f)
            
            return schema_data
            
        except Exception as e:
            logger.error(f"Failed to get schema for connection {connection_id}: {e}")
            return None
    
    async def get_column_descriptions(
        self, 
        db: AsyncSession, 
        connection_id: str
    ) -> List[Dict[str, Any]]:
        """Get column descriptions from database and merge with schema info"""
        try:
            # Get schema information
            schema_data = await self.get_connection_schema(connection_id)
            if not schema_data:
                return []
            
            columns_info = schema_data.get("columns", {})
            
            # Get column descriptions from database
            stmt = select(ColumnDescription).where(
                ColumnDescription.connection_id == uuid.UUID(connection_id)
            )
            result = await db.execute(stmt)
            db_descriptions = result.scalars().all()
            
            # Create mapping of column descriptions
            description_map = {
                desc.column_name: desc.description 
                for desc in db_descriptions
            }
            
            # Combine schema info with descriptions
            column_data = []
            for col_name, col_info in columns_info.items():
                column_data.append({
                    "column_name": col_name,
                    "data_type": col_info.get("data_type", ""),
                    "variable_range": col_info.get("variable_range", ""),
                    "description": description_map.get(col_name, ""),
                    "has_description": col_name in description_map,
                    "categories": col_info.get("categories"),
                    "range": col_info.get("range"),
                    "date_range": col_info.get("date_range")
                })
            
            return column_data
            
        except Exception as e:
            logger.error(f"Failed to get column descriptions for {connection_id}: {e}")
            return []
    
    async def update_column_descriptions(
        self, 
        db: AsyncSession, 
        connection_id: str, 
        column_descriptions: List[ColumnDescriptionItem]
    ) -> bool:
        """Update column descriptions in database and storage"""
        try:
            connection_uuid = uuid.UUID(connection_id)
            
            # Delete existing descriptions
            await db.execute(
                delete(ColumnDescription).where(
                    ColumnDescription.connection_id == connection_uuid
                )
            )
            
            # Add new descriptions
            for col_desc in column_descriptions:
                column_desc_record = ColumnDescription(
                    connection_id=connection_uuid,
                    column_name=col_desc.column_name,
                    description=col_desc.description,
                    data_type=col_desc.data_type,
                    variable_range=col_desc.variable_range
                )
                db.add(column_desc_record)
            
            await db.commit()
            
            # Also save as CSV file for backup
            connection_dir = os.path.join(self.data_dir, "connections", connection_id)
            os.makedirs(connection_dir, exist_ok=True)
            
            csv_path = os.path.join(connection_dir, "column_descriptions.csv")
            with open(csv_path, 'w', newline='') as f:
                f.write("column,description\n")
                for col_desc in column_descriptions:
                    # Escape commas and quotes in CSV
                    desc = col_desc.description.replace('"', '""') if col_desc.description else ""
                    f.write(f'"{col_desc.column_name}","{desc}"\n')
            
            logger.info(f"Updated {len(column_descriptions)} column descriptions for {connection_id}")
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to update column descriptions for {connection_id}: {e}")
            return False
    
    async def update_connection_column_descriptions_flag(
        self, 
        db: AsyncSession, 
        connection_id: str, 
        has_descriptions: bool
    ) -> bool:
        """Update the column_descriptions_uploaded flag"""
        try:
            stmt = select(Connection).where(Connection.id == uuid.UUID(connection_id))
            result = await db.execute(stmt)
            connection = result.scalar_one_or_none()
            
            if connection:
                connection.column_descriptions_uploaded = has_descriptions
                connection.updated_at = datetime.utcnow()
                await db.commit()
                return True
            
            return False
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to update column descriptions flag: {e}")
            return False
    
    # Update the existing create_connection_for_user method to auto-refresh schema
    async def create_connection_for_user(
        self, 
        db: AsyncSession, 
        user: User,
        connection_data: ConnectionCreate, 
        column_descriptions: Optional[List[ColumnDescriptionItem]] = None
    ) -> ConnectionResponse:
        """Create a new connection for a specific user"""
        try:
            # Create connection record with user_id
            connection = Connection(
                user_id=user.id,
                name=connection_data.name,
                server=connection_data.server,
                database_name=connection_data.database_name,
                username=connection_data.username,
                password=connection_data.password,
                table_name=connection_data.table_name,
                driver=getattr(connection_data, 'driver', None),
                status=ConnectionStatus.TEST_SUCCESS,
                column_descriptions_uploaded=bool(column_descriptions)
            )
            
            db.add(connection)
            await db.flush()
            
            connection_id = str(connection.id)
            
            # Create data directory
            connection_dir = os.path.join(self.data_dir, "connections", connection_id)
            os.makedirs(connection_dir, exist_ok=True)
            
            # Save database config
            db_config = {
                "user_id": str(user.id),
                "server": connection_data.server,
                "database_name": connection_data.database_name,
                "username": connection_data.username,
                "password": connection_data.password,
                "table_name": connection_data.table_name,
                "driver": getattr(connection_data, 'driver', None)
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
                
                csv_path = os.path.join(connection_dir, "column_descriptions.csv")
                with open(csv_path, 'w', newline='') as f:
                    f.write("column,description\n")
                    for col_desc in column_descriptions:
                        desc = col_desc.description.replace('"', '""') if col_desc.description else ""
                        f.write(f'"{col_desc.column_name}","{desc}"\n')
            
            await db.commit()
            
            # Auto-refresh schema after creation
            try:
                # Create a temporary task ID for schema refresh
                temp_task_id = str(uuid.uuid4())
                schema_result = await self.refresh_connection_schema(
                    connection_data, connection_id, temp_task_id
                )
                if not schema_result.success:
                    logger.warning(f"Schema refresh failed during connection creation: {schema_result.error_message}")
            except Exception as e:
                logger.warning(f"Auto schema refresh failed for new connection {connection_id}: {e}")
            
            # Convert to response model
            return ConnectionResponse(
                id=connection_id,
                name=connection.name,
                server=connection.server,
                database_name=connection.database_name,
                table_name=connection.table_name,
                driver=connection.driver,
                status=connection.status,
                test_successful=connection.test_successful,
                column_descriptions_uploaded=connection.column_descriptions_uploaded,
                generated_examples_count=connection.generated_examples_count,
                total_queries=connection.total_queries or 0,
                last_queried_at=connection.last_queried_at,
                created_at=connection.created_at,
                trained_at=connection.trained_at
            )
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to create connection for user {user.email}: {e}")
            raise


# Global connection service instance
connection_service = ConnectionService()