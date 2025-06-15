import os
import json
import uuid
import asyncio
import pyodbc
from typing import Optional, List, Dict, Any, Callable
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime
import logging
import openai
import httpx

from app.models.database import Connection, TrainingExample, TrainingTask, ConnectionStatus, User
from app.models.schemas import GenerateExamplesRequest, TrainingExampleResponse
from app.models.vanna_models import (
    DataGenerationConfig, TrainingConfig, GeneratedDataResult, 
    TrainingResult, VannaTrainingData, TrainingDocumentation, 
    TrainingExample as VannaTrainingExample, MSSQLConstants
)
from app.services.connection_service import connection_service
from app.core.sse_manager import sse_manager
from app.utils.sse_utils import SSELogger
from app.config import settings

logger = logging.getLogger(__name__)

class TrainingService:
    """Service for generating training data and training Vanna models with user authentication"""
    
    def __init__(self):
        self.data_dir = settings.DATA_DIR
        self.openai_client = None
    
    async def _load_db_config(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Load database configuration from file"""
        config_path = os.path.join(self.data_dir, "connections", connection_id, "db_config.json")
        
        if not os.path.exists(config_path):
            return None
        
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load db config: {e}")
            return None

    def _get_openai_client(self):
        """Get OpenAI client with configuration"""
        if not self.openai_client:
            self.openai_client = openai.OpenAI(
                base_url=settings.OPENAI_BASE_URL,
                api_key=settings.OPENAI_API_KEY,
                http_client=httpx.Client(verify=False)
            )
        return self.openai_client
    
    async def generate_training_data(
        self, 
        db: AsyncSession, # Passed from connections.py background task
        user: User,
        connection_id: str, 
        num_examples: int,
        task_id: str
    ) -> GeneratedDataResult:
        """Generate training data for a user's connection"""
        sse_logger = SSELogger(sse_manager, task_id, "data_generation")
        
        # NOTE: This top-level try-except block is CRITICAL.
        # It ensures that even if something within _analyze_database_schema,
        # _generate_examples_with_llm, _save_training_examples, _create_training_documentation,
        # or _save_training_data_file fails, the final connection status and SSE error
        # are handled.
        try:
            await sse_logger.info(f"Starting data generation for user {user.email}, connection {connection_id}")
            await sse_logger.progress(5, "Verifying connection ownership...")
            
            # Verify user owns the connection
            connection_response = await connection_service.get_user_connection(db, str(user.id), connection_id)
            if not connection_response:
                raise ValueError(f"Connection {connection_id} not found or access denied for user {user.email}")
            
            # Get raw connection for internal operations
            connection = await connection_service.get_connection_by_id(db, connection_id)
            if not connection:
                raise ValueError(f"Connection {connection_id} not found")
            
            # Double-check user ownership
            if str(connection.user_id) != str(user.id):
                raise ValueError(f"Access denied: Connection does not belong to user {user.email}")
            
            # Update connection status
            # Important: Ensure this commit is separate or that the entire operation uses one transaction.
            # For now, let's assume `_update_connection_status` handles its own commit.
            await self._update_connection_status(db, connection_id, ConnectionStatus.GENERATING_DATA)
            
            await sse_logger.progress(10, "Analyzing database schema...")
            
            # Get database config
            db_config = await self._load_db_config(connection_id)
            if not db_config:
                raise ValueError("Database configuration not found")
            
            # Add user context to db_config for logging
            db_config['connection_id'] = connection_id
            db_config['user_id'] = str(user.id)
            db_config['user_email'] = user.email
            
            # Analyze schema
            column_info = await self._analyze_database_schema(db_config, sse_logger, user)
            
            await sse_logger.progress(20, f"Generating {num_examples} training examples...")
            
            # Generate examples using LLM
            generated_examples = await self._generate_examples_with_llm(
                db_config, column_info, num_examples, sse_logger, task_id, user
            )
            
            await sse_logger.progress(80, "Saving generated examples...")
            
            # Save examples to database - This part should be transactional with the connection status update
            # Suggestion: Perform a single `db.commit()` at the very end of generate_training_data
            # if `_save_training_examples` doesn't commit, and then change _save_training_examples
            # to not commit internally.
            
            # For now, assuming _save_training_examples and _update_connection_status commit,
            # ensure no unhandled exceptions between these and the final return/send_to_task.
            
            await self._save_training_examples(db, connection_id, generated_examples, user)
            
            # Create documentation
            documentation = await self._create_training_documentation(
                db_config, column_info, connection_id, user
            )
            
            await sse_logger.progress(90, "Saving training data...")
            
            # Save complete training data
            training_data = VannaTrainingData(
                documentation=documentation,
                examples=generated_examples
            )
            
            await self._save_training_data_file(connection_id, training_data, user)
            
            # Update connection status to DATA_GENERATED, this is the final DB commit for the success path
            await self._update_connection_status(db, connection_id, ConnectionStatus.DATA_GENERATED)
            
            await sse_logger.progress(100, f"Generated {len(generated_examples)} examples successfully")
            await sse_logger.info(f"Data generation completed for user {user.email}")
            
            # The SSE completion event is sent by `_run_data_generation` in `connections.py`
            # This service function *returns* the result, which is then used by the caller
            return GeneratedDataResult(
                success=True,
                total_generated=len(generated_examples),
                failed_count=num_examples - len(generated_examples),
                examples=generated_examples,
                documentation=documentation,
                generation_time=0.0  # TODO: Track actual time
            )
            
        except Exception as e:
            # This outer exception handler is crucial for catching any error
            # that might prevent the task from completing successfully.
            error_msg = f"Data generation failed for user {user.email}, connection {connection_id}: {str(e)}"
            logger.error(error_msg, exc_info=True) # Log full traceback
            
            # Update connection status back to test success (or failed if more appropriate)
            # Ensure this is robust against further errors.
            try:
                await self._update_connection_status(db, connection_id, ConnectionStatus.TEST_SUCCESS)
            except Exception as status_update_err:
                logger.error(f"Failed to update connection status to TEST_SUCCESS after generation error: {status_update_err}")

            # Rollback any pending transactions for this session if not already committed
            try:
                await db.rollback()
            except Exception as rollback_err:
                logger.error(f"Failed to rollback DB session in generate_training_data: {rollback_err}")

            # Return a failed result
            return GeneratedDataResult(
                success=False,
                total_generated=0,
                failed_count=num_examples,
                examples=[],
                documentation=[],
                generation_time=0.0,
                error_message=error_msg
            )
    
    async def _analyze_database_schema(
        self, 
        db_config: Dict[str, Any], 
        sse_logger: SSELogger,
        user: User
    ) -> Dict[str, Any]:
        """Analyze database schema (with user context)"""
        await sse_logger.info(f"Connecting to database for schema analysis (user: {user.email})...")
        driver = db_config.get('driver', 'ODBC Driver 17 for SQL Server')
        conn_str = (
            f"DRIVER={driver};"
            f"SERVER={db_config['server']};"
            f"DATABASE={db_config['database_name']};"
            f"UID={db_config['username']};"
            f"PWD={db_config['password']};"
            f"TrustServerCertificate=yes"
        )
        
        try:
            cnxn = pyodbc.connect(conn_str)
            cursor = cnxn.cursor()
            
            # Parse table name
            full_table_name = db_config['table_name']
            if '.' in full_table_name:
                table_schema, table_name_only = full_table_name.split('.', 1)
            else:
                table_schema = 'dbo'
                table_name_only = full_table_name
            
            await sse_logger.info(f"Analyzing schema for table: {full_table_name} (user: {user.email})")
            
            columns_info = {}
            
            # Get column information
            cursor.execute(f"""
                SELECT COLUMN_NAME, DATA_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = '{table_schema}' AND TABLE_NAME = '{table_name_only}';
            """)
            schema_cols = cursor.fetchall()
            
            total_cols = len(schema_cols)
            await sse_logger.info(f"Found {total_cols} columns to analyze")
            
            for idx, (col_name, data_type) in enumerate(schema_cols):
                progress = 20 + int((idx / total_cols) * 50)  # 20-70%
                await sse_logger.progress(progress, f"Analyzing column: {col_name}")
                
                col_info = {'data_type': data_type}
                
                # Categorical Data
                if data_type in ['varchar', 'nvarchar', 'char', 'nchar', 'text', 'ntext']:
                    try:
                        cursor.execute(f"""
                            SELECT COUNT(DISTINCT [{col_name}]), AVG(CAST(LEN([{col_name}]) AS DECIMAL(10,2))) 
                            FROM {full_table_name} WHERE [{col_name}] IS NOT NULL;
                        """)
                        distinct_count, avg_len_data = cursor.fetchone()
                        
                        if distinct_count and distinct_count < 50 and (avg_len_data is None or avg_len_data < 50):
                            cursor.execute(f"""
                                SELECT DISTINCT TOP 50 [{col_name}] 
                                FROM {full_table_name} WHERE [{col_name}] IS NOT NULL;
                            """)
                            col_info['categories'] = [str(row[0]) for row in cursor.fetchall()]
                    except Exception as e:
                        await sse_logger.warning(f"Could not profile categorical data for {col_name}: {e}")
                
                # Numerical Data
                elif data_type in ['int', 'bigint', 'smallint', 'tinyint', 'decimal', 'numeric', 'float', 'real']:
                    try:
                        cursor.execute(f"""
                            SELECT MIN(CAST([{col_name}] AS FLOAT)), MAX(CAST([{col_name}] AS FLOAT)), AVG(CAST([{col_name}] AS FLOAT)) 
                            FROM {full_table_name} WHERE [{col_name}] IS NOT NULL;
                        """)
                        min_val, max_val, avg_val = cursor.fetchone()
                        if min_val is not None and max_val is not None:
                            col_info['range'] = {'min': min_val, 'max': max_val, 'avg': avg_val}
                    except Exception as e:
                        await sse_logger.warning(f"Could not profile numerical data for {col_name}: {e}")
                
                # Date/Time Data
                elif data_type in ['date', 'datetime', 'datetime2', 'smalldatetime', 'timestamp']:
                    try:
                        cursor.execute(f"""
                            SELECT MIN([{col_name}]), MAX([{col_name}]) 
                            FROM {full_table_name} WHERE [{col_name}] IS NOT NULL;
                        """)
                        min_date, max_date = cursor.fetchone()
                        if min_date and max_date:
                            col_info['date_range'] = {'min': str(min_date), 'max': str(max_date)}
                    except Exception as e:
                        await sse_logger.warning(f"Could not profile date data for {col_name}: {e}")
                
                columns_info[col_name] = col_info
            
            cnxn.close()
            await sse_logger.info(f"Schema analysis complete for {len(columns_info)} columns (user: {user.email})")
            return columns_info
            
        except Exception as e:
            await sse_logger.error(f"Schema analysis failed for user {user.email}: {str(e)}")
            raise
    
    async def _generate_examples_with_llm(
        self, 
        db_config: Dict[str, Any], 
        column_info: Dict[str, Any], 
        num_examples: int,
        sse_logger: SSELogger,
        task_id: str,
        user: User
    ) -> List[VannaTrainingExample]:
        """Generate training examples using LLM (with user context)"""
        
        client = self._get_openai_client()
        table_name = db_config['table_name']
        connection_id = db_config.get('connection_id', '')
        
        # Create column details for prompt
        column_details = []
        for col_name, info in column_info.items():
            detail = f"Column '{col_name}' ({info['data_type']})"
            
            if 'categories' in info:
                categories = ', '.join(str(val) for val in info['categories'][:10])
                detail += f": Categories - {categories}"
                if len(info['categories']) > 10:
                    detail += "..."
            elif 'range' in info:
                range_info = info['range']
                detail += f": Range {range_info['min']:.2f} - {range_info['max']:.2f} (Avg: {range_info['avg']:.2f})"
            elif 'date_range' in info:
                date_range = info['date_range']
                detail += f": Date range {date_range['min']} to {date_range['max']}"
            
            column_details.append(detail)
        
        column_details_string = "\n".join(column_details)
        
        # Create system prompt
        system_prompt = f"""
You are an expert SQL query generator for Microsoft SQL Server.
Your task is to generate a natural language question and its corresponding SQL query for the table: {table_name}.

---
Table Schema:
{json.dumps({k: v['data_type'] for k, v in column_info.items()}, indent=2)}
---

---
MS SQL Server Conventions:
{MSSQLConstants.MSSQL_CONVENTIONS_DOC}
---

---
Column Details:
{column_details_string}
---

Generate exactly one JSON object with two keys: "question" (natural language) and "sql" (MS SQL query).
The SQL query MUST be valid for MS SQL Server syntax, adhering strictly to the conventions.
The natural language question must be diverse, complex, and sound like a human asking.
Vary the type of queries: simple selections, aggregations, filtering, ordering, grouping, calculations.
Ensure the SQL is realistic given the data types and potential values.
Always output only the JSON object and nothing else.
"""
        
        generated_examples = []
        failed_count = 0
        
        await sse_logger.info(f"Starting LLM generation for {num_examples} examples (user: {user.email})")
        
        for i in range(num_examples):
            progress = 20 + int((i / num_examples) * 60)  # 20-80%
            await sse_logger.progress(progress, f"Generating example {i+1}/{num_examples}")
            
            try:
                response = client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Generate a new, unique question and SQL query. Make it distinct from previous examples. Focus on analytical queries if possible."}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7
                )
                
                content = response.choices[0].message.content
                content = content.replace("```json\n", "").replace("\n```", "")
                example_data = json.loads(content)
                
                if "question" in example_data and "sql" in example_data:
                    example = VannaTrainingExample(
                        question=example_data["question"],
                        sql=example_data["sql"]
                    )
                    generated_examples.append(example)
                    
                    # Send real-time update with the new example and user context
                    await sse_manager.send_to_task(task_id, "example_generated", {
                        "example_number": i + 1,
                        "total_examples": num_examples,
                        "question": example.question,
                        "sql": example.sql,
                        "connection_id": connection_id,
                        "user_id": str(user.id),
                        "user_email": user.email,
                        "task_id": task_id
                    })
                    
                    await sse_logger.info(f"Generated: {example.question[:50]}...")
                else:
                    failed_count += 1
                    await sse_logger.warning(f"LLM response missing required keys in example {i+1}")
                
            except json.JSONDecodeError as e:
                failed_count += 1
                await sse_logger.warning(f"Failed to decode JSON for example {i+1}: {e}")
            except Exception as e:
                failed_count += 1
                await sse_logger.warning(f"Error generating example {i+1}: {e}")
            
            # Small delay to prevent rate limiting
            await asyncio.sleep(0.1)
        
        await sse_logger.info(f"Generation complete for user {user.email}: {len(generated_examples)} successful, {failed_count} failed")
        return generated_examples
    
    async def _create_training_documentation(
        self, 
        db_config: Dict[str, Any], 
        column_info: Dict[str, Any],
        connection_id: str,
        user: User
    ) -> List[TrainingDocumentation]:
        """Create training documentation entries (with user context)"""
        documentation = []
        
        logger.info(f"Creating training documentation for user {user.email}, connection {connection_id}")
        
        # MS SQL Server conventions
        documentation.append(TrainingDocumentation(
            doc_type="mssql_conventions",
            content=MSSQLConstants.MSSQL_CONVENTIONS_DOC
        ))
        
        # Table info
        documentation.append(TrainingDocumentation(
            doc_type="table_info",
            content=f"I only have one table which is {db_config['table_name']}"
        ))
        
        # Column-specific documentation
        for col_name, info in column_info.items():
            doc_content = ""
            
            if 'categories' in info:
                cat_string = ', '.join([str(val) for val in info['categories']])
                doc_content = f"The '{col_name}' column can have the following values: {cat_string}."
            elif 'range' in info:
                range_info = info['range']
                doc_content = f"The '{col_name}' column is a numerical field ranging from {range_info['min']} to {range_info['max']} (average: {range_info['avg']:.2f})."
            elif 'date_range' in info:
                date_range = info['date_range']
                doc_content = f"The '{col_name}' column contains dates from {date_range['min']} to {date_range['max']}."
            
            if doc_content:
                documentation.append(TrainingDocumentation(
                    doc_type=f"column_details_{col_name}",
                    content=doc_content
                ))
            
            # Special handling for 'View' column
            if col_name.lower() == 'view':
                documentation.append(TrainingDocumentation(
                    doc_type="column_keyword_view",
                    content="For the 'View' column, always use [View] when creating the SQL query as 'VIEW' is a reserved keyword in SQL Server."
                ))
        
        # Load column descriptions from database if available
        try:
            connection_dir = os.path.join(self.data_dir, "connections", connection_id)
            csv_path = os.path.join(connection_dir, "column_descriptions.csv")
            
            if os.path.exists(csv_path):
                import csv
                with open(csv_path, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get('column') and row.get('description'):
                            documentation.append(TrainingDocumentation(
                                doc_type=f"column_description_{row['column']}",
                                content=f"Column Name: {row['column']}, Column Description: {row['description']}"
                            ))
        except Exception as e:
            logger.warning(f"Could not load column descriptions for user {user.email}: {e}")
        
        return documentation
    
    async def _save_training_examples(
        self, 
        db: AsyncSession, 
        connection_id: str, 
        examples: List[VannaTrainingExample],
        user: User
    ):
        """Save training examples to database (with user context)"""
        connection_uuid = uuid.UUID(connection_id)
        
        logger.info(f"Saving {len(examples)} training examples for user {user.email}, connection {connection_id}")
        
        for example in examples:
            training_example = TrainingExample(
                connection_id=connection_uuid,
                question=example.question,
                sql=example.sql
            )
            db.add(training_example)
        
        await db.commit()
        
        # Update connection examples count
        stmt = (
            update(Connection)
            .where(Connection.id == connection_uuid)
            .values(generated_examples_count=len(examples))
        )
        await db.execute(stmt)
        await db.commit()
        
        logger.info(f"Successfully saved training examples for user {user.email}")
    
    async def _save_training_data_file(
        self, 
        connection_id: str, 
        training_data: VannaTrainingData,
        user: User
    ):
        """Save training data to JSON file (with user context)"""
        connection_dir = os.path.join(self.data_dir, "connections", connection_id)
        os.makedirs(connection_dir, exist_ok=True)
        
        output_file = os.path.join(connection_dir, "generated_training_data.json")
        
        # Convert to dict for JSON serialization
        data_dict = {
            "user_id": str(user.id),
            "user_email": user.email,
            "connection_id": connection_id,
            "generated_at": datetime.utcnow().isoformat(),
            "documentation": [
                {"doc_type": doc.doc_type, "content": doc.content}
                for doc in training_data.documentation
            ],
            "examples": [
                {"question": ex.question, "sql": ex.sql}
                for ex in training_data.examples
            ]
        }
        
        with open(output_file, 'w') as f:
            json.dump(data_dict, f, indent=2)
        
        logger.info(f"Saved training data to {output_file} for user {user.email}")
    
    async def _update_connection_status(self, db: AsyncSession, connection_id: str, status: ConnectionStatus):
        """Update connection status"""
        stmt = (
            update(Connection)
            .where(Connection.id == uuid.UUID(connection_id))
            .values(status=status, updated_at=datetime.utcnow())
        )
        await db.execute(stmt)
        await db.commit()
    
    # ========================
    # USER-SPECIFIC METHODS
    # ========================
    
    async def get_user_training_data(
        self, 
        db: AsyncSession, 
        user: User, 
        connection_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get training data for a user's connection"""
        try:
            # Verify user owns the connection
            connection_response = await connection_service.get_user_connection(db, str(user.id), connection_id)
            if not connection_response:
                logger.warning(f"Training data access denied for user {user.email}, connection {connection_id}")
                return None
            
            # Load training data file
            connection_dir = os.path.join(self.data_dir, "connections", connection_id)
            training_file = os.path.join(connection_dir, "generated_training_data.json")
            
            if not os.path.exists(training_file):
                return None
            
            with open(training_file, 'r') as f:
                training_data = json.load(f)
            
            # Add connection info
            training_data['connection_name'] = connection_response.name
            training_data['connection_status'] = connection_response.status
            
            return training_data
            
        except Exception as e:
            logger.error(f"Failed to get training data for user {user.email}, connection {connection_id}: {e}")
            return None
    
    async def delete_user_training_data(
        self, 
        db: AsyncSession, 
        user: User, 
        connection_id: str
    ) -> bool:
        """Delete training data for a user's connection"""
        try:
            # Verify user owns the connection
            connection_response = await connection_service.get_user_connection(db, str(user.id), connection_id)
            if not connection_response:
                logger.warning(f"Training data deletion denied for user {user.email}, connection {connection_id}")
                return False
            
            # Delete training examples from database
            connection_uuid = uuid.UUID(connection_id)
            from sqlalchemy import delete
            
            stmt = delete(TrainingExample).where(TrainingExample.connection_id == connection_uuid)
            await db.execute(stmt)
            
            # Reset connection examples count
            update_stmt = (
                update(Connection)
                .where(Connection.id == connection_uuid)
                .values(
                    generated_examples_count=0,
                    status=ConnectionStatus.TEST_SUCCESS
                )
            )
            await db.execute(update_stmt)
            await db.commit()
            
            # Delete training data files
            connection_dir = os.path.join(self.data_dir, "connections", connection_id)
            training_file = os.path.join(connection_dir, "generated_training_data.json")
            
            if os.path.exists(training_file):
                os.remove(training_file)
                logger.info(f"Deleted training data file for user {user.email}, connection {connection_id}")
            
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to delete training data for user {user.email}, connection {connection_id}: {e}")
            return False

# Global training service instance
training_service = TrainingService()