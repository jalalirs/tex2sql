from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import uuid
import logging

from app.dependencies import get_db, get_current_active_user, validate_api_key
from app.services.conversation_service import conversation_service
from app.models.schemas import (
    ConversationQueryRequest, ConversationQueryResponse, ConversationCreate,
    ConversationResponse, ConversationWithMessagesResponse, SuggestedQuestionsResponse
)
from app.models.database import TrainingTask, User
from app.core.sse_manager import sse_manager

router = APIRouter(prefix="/conversations", tags=["Conversations"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    conversation_data: ConversationCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(validate_api_key)
):
    """Create a new conversation"""
    try:
        conversation = await conversation_service.create_conversation(
            current_user, conversation_data, db
        )
        
        # Get connection name for response
        from app.models.database import Connection
        from sqlalchemy import select
        
        connection_result = await db.execute(
            select(Connection.name).where(Connection.id == conversation.connection_id)
        )
        connection_name = connection_result.scalar()
        
        return ConversationResponse(
            id=str(conversation.id),
            connection_id=str(conversation.connection_id),
            connection_name=connection_name,
            title=conversation.title,
            description=conversation.description,
            is_active=conversation.is_active,
            is_pinned=conversation.is_pinned,
            connection_locked=conversation.connection_locked,
            message_count=conversation.message_count,
            total_queries=conversation.total_queries,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            last_message_at=conversation.last_message_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create conversation: {str(e)}"
        )


@router.post("/{conversation_id}/query", response_model=ConversationQueryResponse)
async def process_conversation_query(
    conversation_id: str,
    request: ConversationQueryRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(validate_api_key)
):
    """Process a query in a conversation"""
    try:
        # Create session for this query
        session_id = str(uuid.uuid4())
        
        # Create task for tracking
        task = TrainingTask(
            id=session_id,
            connection_id=None,  # Will be set when we know the connection
            user_id=current_user.id,
            task_type="query",
            status="running"
        )
        
        db.add(task)
        await db.commit()
        
        # Start query processing in background
        background_tasks.add_task(
            _run_conversation_query_processing,
            current_user,
            request.question,
            conversation_id,
            session_id
        )
        
        return ConversationQueryResponse(
            session_id=session_id,
            conversation_id=conversation_id,
            user_message_id="",  # Will be updated via SSE
            stream_url=f"/events/stream/{session_id}",
            is_new_conversation=False,
            connection_locked=False  # Will be updated via SSE
        )
        
    except Exception as e:
        logger.error(f"Failed to start conversation query processing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process query: {str(e)}"
        )

@router.get("/", response_model=list[ConversationResponse])
async def get_user_conversations(
    connection_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's conversations"""
    try:
        conversations = await conversation_service.get_user_conversations(
            current_user, db, connection_id
        )
        
        return conversations
        
    except Exception as e:
        logger.error(f"Failed to get conversations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get conversations: {str(e)}"
        )


@router.post("/query", response_model=ConversationQueryResponse)
async def process_query_new_conversation(
    request: ConversationQueryRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(validate_api_key)
):
    """Process a query - creates new conversation if conversation_id not provided"""
    try:
        if request.conversation_id:
            # Redirect to existing conversation endpoint
            return await process_conversation_query(
                request.conversation_id, request, background_tasks, current_user, db, True
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="conversation_id is required. Create conversation first using POST /conversations/"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process query: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process query: {str(e)}"
        )


@router.get("/{conversation_id}", response_model=ConversationWithMessagesResponse)
async def get_conversation_with_messages(
    conversation_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get conversation with all messages"""
    try:
        conversation = await conversation_service.get_conversation_with_messages(
            conversation_id, current_user, db
        )
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        return conversation
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get conversation: {str(e)}"
        )


@router.get("/{conversation_id}/questions", response_model=SuggestedQuestionsResponse)
async def get_suggested_questions_for_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(validate_api_key)
):
    """Get suggested questions for a conversation's connection"""
    try:
        # Get conversation to find connection
        conversation = await conversation_service.get_conversation(
            conversation_id, current_user, db
        )
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        result = await conversation_service.get_suggested_questions(
            db, str(conversation.connection_id), conversation_id
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get suggested questions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get suggested questions: {str(e)}"
        )


@router.get("/sessions/{session_id}/status")
async def get_session_status(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get conversation query session status"""
    try:
        from sqlalchemy import select
        
        stmt = select(TrainingTask).where(
            TrainingTask.id == session_id,
            TrainingTask.user_id == current_user.id
        )
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        return {
            "session_id": task.id,
            "connection_id": task.connection_id,
            "user_id": str(task.user_id),
            "status": task.status,
            "progress": task.progress,
            "error_message": task.error_message,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "created_at": task.created_at
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session status: {str(e)}"
        )


# ========================
# LEGACY SUPPORT (Optional - for backward compatibility)
# ========================

@router.post("/connections/{connection_id}/questions", response_model=SuggestedQuestionsResponse)
async def get_suggested_questions_for_connection(
    connection_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(validate_api_key)
):
    """Get suggested questions for a connection (legacy endpoint)"""
    try:
        result = await conversation_service.get_suggested_questions(
            db, connection_id, None
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get suggested questions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get suggested questions: {str(e)}"
        )


# ========================
# BACKGROUND TASK
# ========================

async def _run_conversation_query_processing(
    user: User,
    question: str,
    conversation_id: str,
    session_id: str
):
    """Background task for conversation query processing"""
    # Create fresh DB session for background task
    from app.core.database import get_db_session
    
    async with get_db_session() as db:
        try:
            await _update_task_status(db, session_id, "running", 0)
            
            # Process the query with conversation context
            conv_id, user_msg_id, is_new_conv, conn_locked = await conversation_service.process_conversation_query(
                user, question, conversation_id, session_id, db
            )
            
            # Send initial response info
            await sse_manager.send_to_task(session_id, "conversation_info", {
                "conversation_id": conv_id,
                "user_message_id": user_msg_id,
                "is_new_conversation": is_new_conv,
                "connection_locked": conn_locked,
                "session_id": session_id
            })
            
            await _update_task_status(db, session_id, "completed", 100)
                
        except Exception as e:
            error_msg = f"Conversation query processing task failed: {str(e)}"
            logger.error(error_msg)
            await _update_task_status(db, session_id, "failed", 0, error_msg)
            await sse_manager.send_to_task(session_id, "query_error", {
                "error": error_msg,
                "question": question,
                "conversation_id": conversation_id,
                "session_id": session_id,
                "user_id": str(user.id),
                "user_email": user.email
            })

async def _update_task_status(
    db: AsyncSession, 
    task_id: str, 
    status: str, 
    progress: int, 
    error_message: str = None
):
    """Update task status in database"""
    try:
        from sqlalchemy import select
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