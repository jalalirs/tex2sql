import json
import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, asc
from sqlalchemy.orm import joinedload
from fastapi import HTTPException, status
import logging
from datetime import datetime, timezone

from app.models.database import User, Connection, Conversation, Message, ConnectionStatus
from app.models.schemas import (
    ConversationCreate, ConversationUpdate, ConversationResponse,
    ConversationWithMessagesResponse, MessageResponse, MessageType,
    ConversationListResponse, ConversationStatsResponse,
    SuggestedQuestionsResponse
)
from app.models.vanna_models import (
    VannaConfig, DatabaseConfig, ChartResponse
)
from app.services.vanna_service import vanna_service
from app.services.connection_service import connection_service
from app.core.sse_manager import sse_manager
from app.utils.sse_utils import SSELogger
from app.config import settings

logger = logging.getLogger(__name__)


class ConversationService:
    """Service for conversation management and query processing with user authentication"""
    
    def __init__(self):
        pass
    
    # ========================
    # QUERY PROCESSING (Main Method)
    # ========================
    
    async def process_conversation_query(
        self,
        user: User,
        question: str,
        conversation_id: Optional[str],
        session_id: str,
        db: AsyncSession
    ) -> tuple[str, str, bool, bool]:  # Returns (conversation_id, user_message_id, is_new_conversation, connection_locked)
        """Process a query in a conversation context with user authentication"""
        sse_logger = SSELogger(sse_manager, session_id, "conversation")
        
        try:
            # Get or create conversation
            if conversation_id:
                conversation = await self.get_conversation(conversation_id, user, db)
                if not conversation:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Conversation not found or access denied"
                    )
                is_new_conversation = False
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="conversation_id is required. Create conversation first."
                )
            
            await sse_logger.info(f"Processing query in conversation: {conversation.id} for user: {user.email}")
            
            # Add user message
            from app.models.schemas import MessageCreate
            user_message = await self.add_message(
                conversation,
                MessageCreate(
                    conversation_id=str(conversation.id),
                    content=question, 
                    message_type=MessageType.USER
                ),
                db
            )
            
            # Lock connection after first user message if not already locked
            connection_locked = False
            if not conversation.connection_locked:
                conversation.connection_locked = True
                connection_locked = True
                await db.commit()
                await sse_logger.info("Connection locked to this conversation")
            
            # Verify user owns the connection
            connection_response = await connection_service.get_user_connection(
                db, str(user.id), str(conversation.connection_id)
            )
            if not connection_response:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: Connection does not belong to user"
                )
            
            # Get raw connection for internal operations
            connection = await self._get_connection(db, str(conversation.connection_id))
            if not connection:
                raise ValueError(f"Connection {conversation.connection_id} not found")
            
            # Double-check user ownership
            if str(connection.user_id) != str(user.id):
                raise ValueError(f"Access denied: Connection does not belong to user {user.email}")
            
            if connection.status != ConnectionStatus.TRAINED:
                raise ValueError(f"Connection must be trained first. Current status: {connection.status}")
            
            # Get conversation history for context
            chat_history = await self.get_conversation_history(conversation, db, max_messages=10)
            
            # Process query with Vanna
            await self._process_query_with_vanna(
                connection, question, chat_history, session_id, sse_logger, conversation, db, user
            )
            
            return str(conversation.id), str(user_message.id), is_new_conversation, connection_locked
            
        except Exception as e:
            error_msg = f"Conversation query processing failed for user {user.email}: {str(e)}"
            logger.error(error_msg)
            await sse_logger.error(error_msg)
            await sse_manager.send_to_task(session_id, "query_error", {
                "error": error_msg,
                "question": question,
                "session_id": session_id,
                "user_id": str(user.id),
                "user_email": user.email
            })
            raise
    
    async def _process_query_with_vanna(
        self,
        connection: Connection,
        question: str,
        chat_history: List[Dict[str, str]],
        session_id: str,
        sse_logger,
        conversation: Conversation,
        db: AsyncSession,
        user: User
    ):
        """Process query with Vanna AI (with user context)"""
        
        await sse_manager.send_to_task(session_id, "query_started", {
            "question": question,
            "connection_id": str(connection.id),
            "connection_name": connection.name,
            "conversation_id": str(conversation.id),
            "user_id": str(user.id),
            "user_email": user.email,
            "session_id": session_id
        })
        
        # Get Vanna instance
        await sse_logger.progress(10, "Loading AI model...")
        vanna_instance = await self._get_vanna_instance(connection, sse_logger, user)
        if not vanna_instance:
            raise ValueError("Failed to load AI model")
        
        # Generate SQL
        await sse_logger.progress(25, "Generating SQL query...")
        sql = await self._generate_sql(vanna_instance, question, chat_history, sse_logger, session_id, user)
        
        if not sql:
            # Save error message
            from app.models.schemas import MessageCreate
            await self.add_message(
                conversation,
                MessageCreate(
                    conversation_id=str(conversation.id),
                    content="Could not generate SQL for this question", 
                    message_type=MessageType.SYSTEM
                ),
                db
            )
            return
        
        # Validate SQL
        await sse_logger.progress(40, "Validating SQL query...")
        is_valid = await self._validate_sql(vanna_instance, sql, sse_logger, session_id, user)
        
        if not is_valid:
            # Save error message
            from app.models.schemas import MessageCreate
            await self.add_message(
                conversation,
                MessageCreate(conversation_id=str(conversation.id),content="Generated SQL query is not valid", message_type=MessageType.SYSTEM),
                db,
                generated_sql=sql
            )
            return
        
        # Execute SQL
        await sse_logger.progress(55, "Executing SQL query...")
        data = await self._execute_sql(vanna_instance, sql, sse_logger, session_id, user)
        
        if data is None:
            # Save error message
            from app.models.schemas import MessageCreate
            await self.add_message(
                conversation,
                MessageCreate(conversation_id=str(conversation.id),content="SQL execution failed", message_type=MessageType.SYSTEM),
                db,
                generated_sql=sql
            )
            return
        
        # Prepare assistant response
        response_content = f"I found {len(data)} records for your query."
        query_results = data
        chart_data = None
        summary = None
        followup_questions = []
        
        if data:
            # Generate chart if appropriate
            await sse_logger.progress(70, "Checking if chart should be generated...")
            chart_result = await self._generate_chart(vanna_instance, question, sql, data, sse_logger, session_id, user)
            if chart_result and chart_result.chart_figure:
                chart_data = chart_result.chart_figure
            
            # Generate summary
            await sse_logger.progress(85, "Generating summary...")
            summary = await self._generate_summary(vanna_instance, question, data, sse_logger, session_id, user)
            if summary:
                response_content = summary
            
            # Generate follow-up questions
            await sse_logger.progress(95, "Generating follow-up questions...")
            followup_questions = await self._generate_followup_questions(
                vanna_instance, question, sql, data, sse_logger, session_id, user
            )
        
        # Save assistant response
        from app.models.schemas import MessageCreate
        assistant_message = await self.add_message(
            conversation,
            MessageCreate(
                conversation_id=str(conversation.id),  # Add this line
                content=response_content, 
                message_type=MessageType.ASSISTANT
            ),
            db,
            generated_sql=sql,
            query_results=query_results,
            chart_data=chart_data,
            row_count=len(data) if data else 0
        )
        
        await sse_logger.progress(100, "Query processing completed")
        await sse_manager.send_to_task(session_id, "query_completed", {
            "success": True,
            "question": question,
            "conversation_id": str(conversation.id),
            "message_id": str(assistant_message.id),
            "has_data": bool(data),
            "has_chart": bool(chart_data),
            "has_summary": bool(summary),
            "followup_count": len(followup_questions),
            "user_id": str(user.id),
            "user_email": user.email,
            "session_id": session_id
        })
    
    # ========================
    # VANNA AI INTEGRATION (Updated with user context)
    # ========================
    
    async def _get_connection(self, db: AsyncSession, connection_id: str) -> Optional[Connection]:
        """Get connection from database"""
        stmt = select(Connection).where(Connection.id == uuid.UUID(connection_id))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def _get_vanna_instance(self, connection: Connection, sse_logger: Optional[SSELogger] = None, user: Optional[User] = None):
        """Get Vanna instance for connection with user context"""
        try:
            # Validate user access to Vanna model
            if user and not vanna_service.validate_user_access_to_connection(str(connection.id), user):
                raise ValueError(f"User {user.email} does not have access to this connection's AI model")
            
            vanna_config = VannaConfig(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
                model=settings.OPENAI_MODEL
            )
            
            db_config = DatabaseConfig(
                server=connection.server,
                database_name=connection.database_name,
                username=connection.username,
                password=connection.password,
                table_name=connection.table_name,
                driver=connection.driver
            )
            
            vanna_instance = vanna_service.get_vanna_instance(
                str(connection.id), db_config, vanna_config, user
            )
            
            if sse_logger:
                if vanna_instance:
                    user_info = f" for user {user.email}" if user else ""
                    await sse_logger.info(f"AI model loaded successfully{user_info}")
                else:
                    await sse_logger.error("Failed to load AI model")
            
            return vanna_instance
            
        except Exception as e:
            error_msg = f"Error loading AI model: {str(e)}"
            if sse_logger:
                await sse_logger.error(error_msg)
            logger.error(f"Failed to get Vanna instance for user {user.email if user else 'unknown'}: {e}")
            return None
    
    async def _generate_sql(
        self, 
        vanna_instance, 
        question: str, 
        chat_history: Optional[List[Dict[str, str]]], 
        sse_logger: SSELogger,
        session_id: str,
        user: Optional[User] = None
    ) -> Optional[str]:
        """Generate SQL from natural language question"""
        try:
            # Prepare chat history for Vanna
            vanna_history = []
            if chat_history:
                for msg in chat_history[-10:]:  # Last 10 messages
                    if msg.get("role") in ["user", "assistant", "human"]:
                        vanna_history.append({
                            "role": "human" if msg["role"] == "user" else msg["role"],
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
                    "user_id": str(user.id) if user else None,
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
        session_id: str,
        user: Optional[User] = None
    ) -> bool:
        """Validate generated SQL"""
        try:
            is_valid = vanna_instance.is_sql_valid(sql=sql)
            
            if is_valid:
                await sse_logger.info("SQL validation successful")
                await sse_manager.send_to_task(session_id, "sql_validated", {
                    "valid": True,
                    "sql": sql,
                    "user_id": str(user.id) if user else None,
                    "session_id": session_id
                })
            else:
                await sse_logger.warning("SQL validation failed")
                await sse_manager.send_to_task(session_id, "sql_validation_failed", {
                    "valid": False,
                    "sql": sql,
                    "user_id": str(user.id) if user else None,
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
        session_id: str,
        user: Optional[User] = None
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
                    "data": data[:10] if len(data) > 10 else data,
                    "total_rows": len(data),
                    "user_id": str(user.id) if user else None,
                    "session_id": session_id
                })
                
                return data
            else:
                await sse_logger.info("Query executed but returned no data")
                await sse_manager.send_to_task(session_id, "no_data", {
                    "message": "Query executed successfully but returned no data",
                    "user_id": str(user.id) if user else None,
                    "session_id": session_id
                })
                return []
            
        except Exception as e:
            await sse_logger.error(f"SQL execution failed: {str(e)}")
            await sse_manager.send_to_task(session_id, "sql_execution_failed", {
                "error": str(e),
                "sql": sql,
                "user_id": str(user.id) if user else None,
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
        session_id: str,
        user: Optional[User] = None
    ) -> Optional[ChartResponse]:
        """Generate chart if appropriate"""
        try:
            import pandas as pd
            df = pd.DataFrame(data)
            
            should_generate = vanna_instance.should_generate_chart(df=df)
            
            if not should_generate:
                await sse_logger.info("Chart generation not recommended for this data")
                await sse_manager.send_to_task(session_id, "chart_skipped", {
                    "reason": "Chart not recommended for this data type",
                    "user_id": str(user.id) if user else None,
                    "session_id": session_id
                })
                return ChartResponse(should_generate=False)
            
            chart_code = vanna_instance.generate_plotly_code(
                question=question, sql=sql, df=df
            )
            
            if not chart_code:
                await sse_logger.warning("Failed to generate chart code")
                return ChartResponse(should_generate=True, error_message="Failed to generate chart code")
            
            fig = vanna_instance.get_plotly_figure(plotly_code=chart_code, df=df)
            
            if fig:
                chart_json = fig.to_dict()
                
                await sse_logger.info("Chart generated successfully")
                await sse_manager.send_to_task(session_id, "chart_generated", {
                    "chart_data": chart_json,
                    "chart_code": chart_code,
                    "user_id": str(user.id) if user else None,
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
        session_id: str,
        user: Optional[User] = None
    ) -> Optional[str]:
        """Generate summary of results"""
        try:
            import pandas as pd
            df = pd.DataFrame(data)
            
            summary = vanna_instance.generate_summary(question=question, df=df)
            
            if summary:
                await sse_logger.info("Summary generated successfully")
                await sse_manager.send_to_task(session_id, "summary_generated", {
                    "summary": summary,
                    "user_id": str(user.id) if user else None,
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
        session_id: str,
        user: Optional[User] = None
    ) -> List[str]:
        """Generate follow-up questions"""
        try:
            import pandas as pd
            df = pd.DataFrame(data)
            
            followup_questions = vanna_instance.generate_followup_questions(
                question=question, sql=sql, df=df
            )
            
            if followup_questions:
                await sse_logger.info(f"Generated {len(followup_questions)} follow-up questions")
                await sse_manager.send_to_task(session_id, "followup_generated", {
                    "questions": followup_questions[:5],
                    "total_questions": len(followup_questions),
                    "user_id": str(user.id) if user else None,
                    "session_id": session_id
                })
                return followup_questions[:5]
            else:
                await sse_logger.info("No follow-up questions generated")
                return []
            
        except Exception as e:
            await sse_logger.error(f"Follow-up generation failed: {str(e)}")
            return []
    
    async def get_suggested_questions(
        self, 
        db: AsyncSession, 
        user: User,
        connection_id: str,
        conversation_id: Optional[str] = None
    ) -> SuggestedQuestionsResponse:
        """Get suggested questions for a user's connection"""
        try:
            # Verify user owns the connection
            connection_response = await connection_service.get_user_connection(db, str(user.id), connection_id)
            if not connection_response:
                raise ValueError(f"Connection {connection_id} not found or access denied for user {user.email}")
            
            connection = await self._get_connection(db, connection_id)
            if not connection:
                raise ValueError(f"Connection {connection_id} not found")
            
            if connection.status != ConnectionStatus.TRAINED:
                raise ValueError(f"Connection must be trained first. Current status: {connection.status}")
            
            vanna_instance = await self._get_vanna_instance(connection, user=user)
            if not vanna_instance:
                raise ValueError("Failed to load AI model")
            
            questions = vanna_instance.generate_questions()
            
            logger.info(f"Generated {len(questions)} suggested questions for user {user.email}, connection {connection_id}")
            
            return SuggestedQuestionsResponse(
                questions=questions,
                connection_id=connection_id,
                conversation_id=conversation_id,
                total=len(questions)
            )
            
        except Exception as e:
            logger.error(f"Failed to generate suggested questions for user {user.email}: {e}")
            return SuggestedQuestionsResponse(
                questions=[],
                connection_id=connection_id,
                conversation_id=conversation_id,
                total=0
            )
    
    # ========================
    # CONVERSATION MANAGEMENT METHODS (Updated with better user context)
    # ========================
    
    async def create_conversation(
        self, 
        user: User, 
        conversation_data: ConversationCreate, 
        db: AsyncSession
    ) -> Conversation:
        """Create a new conversation"""
        
        # Verify connection belongs to user using connection service
        connection_response = await connection_service.get_user_connection(
            db, str(user.id), str(conversation_data.connection_id)
        )
        
        if not connection_response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found or access denied"
            )
        
        # Generate title if not provided
        title = conversation_data.title
        if not title:
            count_result = await db.execute(
                select(func.count(Conversation.id)).where(
                    and_(
                        Conversation.user_id == user.id,
                        Conversation.connection_id == conversation_data.connection_id
                    )
                )
            )
            count = count_result.scalar() or 0
            title = f"Conversation with {connection_response.name} #{count + 1}"
        
        # Create conversation
        conversation = Conversation(
            user_id=user.id,
            connection_id=conversation_data.connection_id,
            title=title,
            description=conversation_data.description
        )
        
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        
        logger.info(f"Conversation created: {conversation.id} for user {user.email} with connection {connection_response.name}")
        return conversation
    
    async def get_conversation(
        self, 
        conversation_id: str, 
        user: User, 
        db: AsyncSession,
        include_messages: bool = False
    ) -> Optional[Conversation]:
        """Get conversation by ID that belongs to user"""
        
        query = select(Conversation).where(
            and_(
                Conversation.id == conversation_id,
                Conversation.user_id == user.id
            )
        )
        
        if include_messages:
            query = query.options(joinedload(Conversation.messages))
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def list_user_conversations(
        self,
        user: User,
        db: AsyncSession,
        connection_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Conversation]:
        """List conversations for a user"""
        
        query = select(Conversation).where(Conversation.user_id == user.id)
        
        if connection_id:
            # Verify user owns the connection first
            connection_response = await connection_service.get_user_connection(db, str(user.id), connection_id)
            if not connection_response:
                return []  # Return empty list if user doesn't own connection
            
            query = query.where(Conversation.connection_id == connection_id)
        
        query = query.order_by(desc(Conversation.updated_at)).limit(limit).offset(offset)
        
        result = await db.execute(query)
        conversations = result.scalars().all()
        
        logger.info(f"Listed {len(conversations)} conversations for user {user.email}")
        return list(conversations)
    
    async def get_user_conversations(
        self,
        user: User,
        db: AsyncSession,
        connection_id: Optional[str] = None
    ) -> List[ConversationResponse]:
        """Get user's conversations formatted for API response"""
        
        # Get conversations using existing method
        conversations = await self.list_user_conversations(
            user, db, connection_id, limit=100
        )
        
        # Format for API response
        result = []
        for conv in conversations:
            # Get connection name
            connection_result = await db.execute(
                select(Connection.name).where(Connection.id == conv.connection_id)
            )
            connection_name = connection_result.scalar() or "Unknown Connection"
            
            # Get latest message
            latest_message_result = await db.execute(
                select(Message.content).where(
                    Message.conversation_id == conv.id
                ).order_by(desc(Message.created_at)).limit(1)
            )
            latest_message = latest_message_result.scalar()
            
            result.append(ConversationResponse(
                id=str(conv.id),
                connection_id=str(conv.connection_id),
                connection_name=connection_name,
                title=conv.title,
                description=conv.description,
                is_active=conv.is_active,
                is_pinned=conv.is_pinned,
                connection_locked=conv.connection_locked,
                message_count=conv.message_count,
                total_queries=conv.total_queries,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                last_message_at=conv.last_message_at,
                latest_message=latest_message
            ))
        
        return result

    async def delete_conversation(
        self,
        user: User,
        conversation_id: str,
        db: AsyncSession
    ) -> bool:
        """Delete a conversation that belongs to user"""
        
        conversation = await self.get_conversation(conversation_id, user, db)
        if not conversation:
            return False
        
        try:
            # Delete conversation (messages will be deleted via cascade)
            await db.delete(conversation)
            await db.commit()
            
            logger.info(f"Deleted conversation {conversation_id} for user {user.email}")
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to delete conversation {conversation_id} for user {user.email}: {e}")
            return False
    
    async def add_message(
        self,
        conversation: Conversation,
        message_data,  # MessageCreate
        db: AsyncSession,
        **additional_data
    ) -> Message:
        """Add message to conversation"""
        
        # Create message
        message = Message(
            conversation_id=conversation.id,
            content=message_data.content,
            message_type=message_data.message_type,
            **additional_data
        )
        
        db.add(message)
        
        # Update conversation stats
        conversation.message_count += 1
        conversation.last_message_at = datetime.now(timezone.utc)
        conversation.updated_at = datetime.now(timezone.utc)
        
        # Increment query count if assistant message
        if message_data.message_type == MessageType.ASSISTANT:
            conversation.total_queries += 1
            
            # Also update connection query stats
            connection_result = await db.execute(
                select(Connection).where(Connection.id == conversation.connection_id)
            )
            connection = connection_result.scalar_one_or_none()
            if connection:
                connection.total_queries = (connection.total_queries or 0) + 1
                connection.last_queried_at = datetime.now(timezone.utc)
        
        await db.commit()
        await db.refresh(message)
        
        return message
    
    async def get_conversation_history(
        self,
        conversation: Conversation,
        db: AsyncSession,
        max_messages: int = 10
    ) -> List[Dict[str, str]]:
        """Get conversation history for LLM context"""
        
        messages_result = await db.execute(
            select(Message).where(
                and_(
                    Message.conversation_id == conversation.id,
                    Message.message_type.in_(['user', 'assistant'])
                )
            ).order_by(desc(Message.created_at)).limit(max_messages)
        )
        
        messages = list(reversed(messages_result.scalars().all()))
        
        history = []
        for msg in messages:
            role = "human" if msg.message_type == "user" else "assistant"
            content = msg.content
            
            # For assistant messages, include SQL if available
            if msg.message_type == "assistant" and msg.generated_sql:
                content += f"\n\nGenerated SQL:\n```sql\n{msg.generated_sql}\n```"
            
            history.append({
                "role": role,
                "content": content
            })
        
        return history


# Global conversation service instance
conversation_service = ConversationService()