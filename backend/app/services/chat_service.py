import json
import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.models.database import Connection, ConnectionStatus
from app.models.schemas import ConnectionResponse
from app.models.vanna_models import (
    VannaConfig, DatabaseConfig, QueryRequest, QueryResponse, 
    SuggestedQuestionsResponse, ChartRequest, ChartResponse
)
from app.core.vanna_wrapper import vanna_service
from app.core.sse_manager import sse_manager
from app.utils.sse_utils import SSELogger
from app.config import settings

logger = logging.getLogger(__name__)


class ChatService:
    """Service for handling natural language queries and chat interactions"""
    
    def __init__(self):
        pass
    
    async def process_query(
        self, 
        db: AsyncSession, 
        connection_id: str, 
        question: str,
        session_id: str,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> QueryResponse:
        """Process a natural language query and return complete response"""
        sse_logger = SSELogger(sse_manager, session_id, "chat")
        
        try:
            await sse_logger.info(f"Processing query: {question}")
            await sse_manager.send_to_task(session_id, "query_started", {
                "question": question,
                "connection_id": connection_id,
                "session_id": session_id
            })
            
            # Get connection and validate
            connection = await self._get_connection(db, connection_id)
            if not connection:
                raise ValueError(f"Connection {connection_id} not found")
            
            if connection.status != ConnectionStatus.TRAINED:
                raise ValueError(f"Connection must be trained first. Current status: {connection.status}")
            
            # Get Vanna instance
            await sse_logger.progress(10, "Loading AI model...")
            vanna_instance = await self._get_vanna_instance(connection, sse_logger)
            if not vanna_instance:
                raise ValueError("Failed to load AI model")
            
            # Generate SQL
            await sse_logger.progress(25, "Generating SQL query...")
            sql = await self._generate_sql(vanna_instance, question, chat_history, sse_logger, session_id)
            
            if not sql:
                return QueryResponse(
                    question=question,
                    error_message="Could not generate SQL for this question"
                )
            
            # Validate SQL
            await sse_logger.progress(40, "Validating SQL query...")
            is_valid = await self._validate_sql(vanna_instance, sql, sse_logger, session_id)
            
            if not is_valid:
                return QueryResponse(
                    question=question,
                    sql=sql,
                    is_sql_valid=False,
                    error_message="Generated SQL query is not valid"
                )
            
            # Execute SQL
            await sse_logger.progress(55, "Executing SQL query...")
            data = await self._execute_sql(vanna_instance, sql, sse_logger, session_id)
            
            response = QueryResponse(
                question=question,
                sql=sql,
                is_sql_valid=True,
                data=data
            )
            
            if data:
                # Generate chart if appropriate
                await sse_logger.progress(70, "Checking if chart should be generated...")
                chart_result = await self._generate_chart(vanna_instance, question, sql, data, sse_logger, session_id)
                if chart_result:
                    response.chart_code = chart_result.chart_code
                    response.chart_data = chart_result.chart_figure
                
                # Generate summary
                await sse_logger.progress(85, "Generating summary...")
                summary = await self._generate_summary(vanna_instance, question, data, sse_logger, session_id)
                response.summary = summary
                
                # Generate follow-up questions
                await sse_logger.progress(95, "Generating follow-up questions...")
                followup_questions = await self._generate_followup_questions(
                    vanna_instance, question, sql, data, sse_logger, session_id
                )
                response.followup_questions = followup_questions
            
            await sse_logger.progress(100, "Query processing completed")
            await sse_manager.send_to_task(session_id, "query_completed", {
                "success": True,
                "question": question,
                "has_data": bool(data),
                "has_chart": bool(response.chart_data),
                "has_summary": bool(response.summary),
                "followup_count": len(response.followup_questions) if response.followup_questions else 0,
                "session_id": session_id
            })
            
            return response
            
        except Exception as e:
            error_msg = f"Query processing failed: {str(e)}"
            logger.error(error_msg)
            await sse_logger.error(error_msg)
            await sse_manager.send_to_task(session_id, "query_error", {
                "error": error_msg,
                "question": question,
                "session_id": session_id
            })
            
            return QueryResponse(
                question=question,
                error_message=error_msg
            )
    
    async def get_suggested_questions(
        self, 
        db: AsyncSession, 
        connection_id: str
    ) -> SuggestedQuestionsResponse:
        """Get suggested questions for a connection"""
        try:
            # Get connection
            connection = await self._get_connection(db, connection_id)
            if not connection:
                raise ValueError(f"Connection {connection_id} not found")
            
            if connection.status != ConnectionStatus.TRAINED:
                raise ValueError(f"Connection must be trained first. Current status: {connection.status}")
            
            # Get Vanna instance
            vanna_instance = await self._get_vanna_instance(connection)
            if not vanna_instance:
                raise ValueError("Failed to load AI model")
            
            # Generate questions
            questions = vanna_instance.generate_questions()
            
            return SuggestedQuestionsResponse(
                questions=questions,
                connection_id=connection_id
            )
            
        except Exception as e:
            logger.error(f"Failed to generate suggested questions: {e}")
            return SuggestedQuestionsResponse(
                questions=[],
                connection_id=connection_id
            )
    
    async def _get_connection(self, db: AsyncSession, connection_id: str) -> Optional[Connection]:
        """Get connection from database"""
        stmt = select(Connection).where(Connection.id == uuid.UUID(connection_id))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def _get_vanna_instance(self, connection: Connection, sse_logger: Optional[SSELogger] = None):
        """Get Vanna instance for connection"""
        try:
            vanna_config = VannaConfig(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
                model=settings.OPENAI_MODEL
            )
            
            db_config = DatabaseConfig(
                server=connection.server,
                database_name=connection.database_name,
                username=connection.username,
                password=connection.password,  # TODO: Decrypt in production
                table_name=connection.table_name
            )
            
            vanna_instance = vanna_service.get_vanna_instance(
                str(connection.id), db_config, vanna_config
            )
            
            if sse_logger:
                if vanna_instance:
                    await sse_logger.info("AI model loaded successfully")
                else:
                    await sse_logger.error("Failed to load AI model")
            
            return vanna_instance
            
        except Exception as e:
            if sse_logger:
                await sse_logger.error(f"Error loading AI model: {str(e)}")
            logger.error(f"Failed to get Vanna instance: {e}")
            return None
    
    async def _generate_sql(
        self, 
        vanna_instance, 
        question: str, 
        chat_history: Optional[List[Dict[str, str]]], 
        sse_logger: SSELogger,
        session_id: str
    ) -> Optional[str]:
        """Generate SQL from natural language question"""
        try:
            # Prepare chat history for Vanna
            vanna_history = []
            if chat_history:
                for msg in chat_history[-10:]:  # Last 10 messages
                    if msg.get("role") in ["user", "assistant"]:
                        vanna_history.append({
                            "role": msg["role"],
                            "content": msg["content"]
                        })
            
            sql = vanna_instance.generate_sql(
                question=question, 
                allow_llm_to_see_data=True, 
                chat_history=vanna_history
            )
            
            if sql:
                await sse_logger.info(f"Generated SQL: {sql[:100]}...")
                await sse_manager.send_to_task(session_id, "sql_generated", {
                    "sql": sql,
                    "question": question,
                    "session_id": session_id
                })
            else:
                await sse_logger.warning("No SQL generated")
            
            return sql
            
        except Exception as e:
            await sse_logger.error(f"SQL generation failed: {str(e)}")
            return None
    
    async def _validate_sql(
        self, 
        vanna_instance, 
        sql: str, 
        sse_logger: SSELogger,
        session_id: str
    ) -> bool:
        """Validate generated SQL"""
        try:
            is_valid = vanna_instance.is_sql_valid(sql=sql)
            
            if is_valid:
                await sse_logger.info("SQL validation successful")
                await sse_manager.send_to_task(session_id, "sql_validated", {
                    "valid": True,
                    "sql": sql,
                    "session_id": session_id
                })
            else:
                await sse_logger.warning("SQL validation failed")
                await sse_manager.send_to_task(session_id, "sql_validation_failed", {
                    "valid": False,
                    "sql": sql,
                    "session_id": session_id
                })
            
            return is_valid
            
        except Exception as e:
            await sse_logger.error(f"SQL validation error: {str(e)}")
            return False
    
    async def _execute_sql(
        self, 
        vanna_instance, 
        sql: str, 
        sse_logger: SSELogger,
        session_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Execute SQL and return data"""
        try:
            df = vanna_instance.run_sql(sql=sql)
            
            if df is not None and not df.empty:
                # Convert DataFrame to list of dictionaries
                data = df.to_dict('records')
                
                # Convert non-serializable types
                for row in data:
                    for key, value in row.items():
                        if hasattr(value, 'isoformat'):  # datetime objects
                            row[key] = value.isoformat()
                        elif value is None:
                            row[key] = None
                        else:
                            row[key] = str(value)
                
                await sse_logger.info(f"Query returned {len(data)} rows")
                await sse_manager.send_to_task(session_id, "data_fetched", {
                    "row_count": len(data),
                    "data": data[:10] if len(data) > 10 else data,  # Send first 10 rows for preview
                    "total_rows": len(data),
                    "session_id": session_id
                })
                
                return data
            else:
                await sse_logger.info("Query executed but returned no data")
                await sse_manager.send_to_task(session_id, "no_data", {
                    "message": "Query executed successfully but returned no data",
                    "session_id": session_id
                })
                return []
            
        except Exception as e:
            await sse_logger.error(f"SQL execution failed: {str(e)}")
            await sse_manager.send_to_task(session_id, "sql_execution_failed", {
                "error": str(e),
                "sql": sql,
                "session_id": session_id
            })
            return None
    
    async def _generate_chart(
        self, 
        vanna_instance, 
        question: str, 
        sql: str, 
        data: List[Dict[str, Any]], 
        sse_logger: SSELogger,
        session_id: str
    ) -> Optional[ChartResponse]:
        """Generate chart if appropriate"""
        try:
            # Convert data back to DataFrame for Vanna
            import pandas as pd
            df = pd.DataFrame(data)
            
            # Check if chart should be generated
            should_generate = vanna_instance.should_generate_chart(df=df)
            
            if not should_generate:
                await sse_logger.info("Chart generation not recommended for this data")
                await sse_manager.send_to_task(session_id, "chart_skipped", {
                    "reason": "Chart not recommended for this data type",
                    "session_id": session_id
                })
                return ChartResponse(should_generate=False)
            
            # Generate chart code
            chart_code = vanna_instance.generate_plotly_code(
                question=question, sql=sql, df=df
            )
            
            if not chart_code:
                await sse_logger.warning("Failed to generate chart code")
                return ChartResponse(should_generate=True, error_message="Failed to generate chart code")
            
            # Generate actual plot
            fig = vanna_instance.get_plotly_figure(plotly_code=chart_code, df=df)
            
            if fig:
                # Convert figure to JSON
                chart_json = fig.to_dict()
                
                await sse_logger.info("Chart generated successfully")
                await sse_manager.send_to_task(session_id, "chart_generated", {
                    "chart_data": chart_json,
                    "chart_code": chart_code,
                    "session_id": session_id
                })
                
                return ChartResponse(
                    should_generate=True,
                    chart_code=chart_code,
                    chart_figure=chart_json
                )
            else:
                await sse_logger.warning("Failed to generate chart figure")
                return ChartResponse(
                    should_generate=True, 
                    chart_code=chart_code,
                    error_message="Failed to generate chart figure"
                )
            
        except Exception as e:
            await sse_logger.error(f"Chart generation failed: {str(e)}")
            return ChartResponse(
                should_generate=True,
                error_message=f"Chart generation failed: {str(e)}"
            )
    
    async def _generate_summary(
        self, 
        vanna_instance, 
        question: str, 
        data: List[Dict[str, Any]], 
        sse_logger: SSELogger,
        session_id: str
    ) -> Optional[str]:
        """Generate summary of results"""
        try:
            # Convert data back to DataFrame for Vanna
            import pandas as pd
            df = pd.DataFrame(data)
            
            summary = vanna_instance.generate_summary(question=question, df=df)
            
            if summary:
                await sse_logger.info("Summary generated successfully")
                await sse_manager.send_to_task(session_id, "summary_generated", {
                    "summary": summary,
                    "session_id": session_id
                })
            else:
                await sse_logger.warning("Failed to generate summary")
            
            return summary
            
        except Exception as e:
            await sse_logger.error(f"Summary generation failed: {str(e)}")
            return None
    
    async def _generate_followup_questions(
        self, 
        vanna_instance, 
        question: str, 
        sql: str, 
        data: List[Dict[str, Any]], 
        sse_logger: SSELogger,
        session_id: str
    ) -> List[str]:
        """Generate follow-up questions"""
        try:
            # Convert data back to DataFrame for Vanna
            import pandas as pd
            df = pd.DataFrame(data)
            
            followup_questions = vanna_instance.generate_followup_questions(
                question=question, sql=sql, df=df
            )
            
            if followup_questions:
                await sse_logger.info(f"Generated {len(followup_questions)} follow-up questions")
                await sse_manager.send_to_task(session_id, "followup_generated", {
                    "questions": followup_questions[:5],  # Limit to 5 questions
                    "total_questions": len(followup_questions),
                    "session_id": session_id
                })
                return followup_questions[:5]
            else:
                await sse_logger.info("No follow-up questions generated")
                return []
            
        except Exception as e:
            await sse_logger.error(f"Follow-up generation failed: {str(e)}")
            return []

# Global chat service instance
chat_service = ChatService()