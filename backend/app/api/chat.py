from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict
from pydantic import BaseModel
import uuid
import logging

from app.dependencies import get_db, validate_api_key
from app.services.chat_service import chat_service
from app.models.schemas import TaskResponse, ChatQueryRequest, ChatQueryResponse, SuggestedQuestionsResponse
from app.models.database import TrainingTask
from app.core.sse_manager import sse_manager
from app.config import settings

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = logging.getLogger(__name__)

@router.post("/connections/{connection_id}/query", response_model=ChatQueryResponse)
async def process_query(
    connection_id: str,
    request: ChatQueryRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(validate_api_key)
):
    """Process a natural language query"""
    try:
        # Create session for this query
        session_id = str(uuid.uuid4())
        
        # Create task for tracking
        task = TrainingTask(
            id=session_id,
            connection_id=connection_id,
            task_type="query",
            status="running"
        )
        
        db.add(task)
        await db.commit()
        
        # Start query processing in background
        background_tasks.add_task(
            _run_query_processing,
            connection_id,
            request.question,
            session_id,
            request.chat_history,
            db
        )
        
        return ChatQueryResponse(
            session_id=session_id,
            stream_url=f"/events/stream/{session_id}"
        )
        
    except Exception as e:
        logger.error(f"Failed to start query processing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process query: {str(e)}"
        )

@router.get("/connections/{connection_id}/questions", response_model=SuggestedQuestionsResponse)
async def get_suggested_questions(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(validate_api_key)
):
    """Get suggested questions for a connection"""
    try:
        result = await chat_service.get_suggested_questions(db, connection_id)
        return SuggestedQuestionsResponse(
            questions=result.questions,
            connection_id=result.connection_id,
            total=len(result.questions)
        )
        
    except Exception as e:
        logger.error(f"Failed to get suggested questions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get suggested questions: {str(e)}"
        )

@router.get("/sessions/{session_id}/status")
async def get_session_status(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get chat session status"""
    try:
        from sqlalchemy import select
        
        stmt = select(TrainingTask).where(TrainingTask.id == session_id)
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

async def _run_query_processing(
    connection_id: str,
    question: str,
    session_id: str,
    chat_history: Optional[List[Dict[str, str]]],
    db: AsyncSession
):
    """Background task for query processing"""
    try:
        await _update_task_status(db, session_id, "running", 0)
        
        # Process the query
        result = await chat_service.process_query(
            db, connection_id, question, session_id, chat_history
        )
        
        # Send final result
        if result.error_message:
            await _update_task_status(db, session_id, "failed", 0, result.error_message)
            await sse_manager.send_to_task(session_id, "query_failed", {
                "error": result.error_message,
                "question": question,
                "session_id": session_id
            })
        else:
            await _update_task_status(db, session_id, "completed", 100)
            await sse_manager.send_to_task(session_id, "query_result", {
                "question": result.question,
                "sql": result.sql,
                "is_sql_valid": result.is_sql_valid,
                "data_rows": len(result.data) if result.data else 0,
                "has_chart": bool(result.chart_data),
                "summary": result.summary,
                "followup_questions": result.followup_questions,
                "session_id": session_id
            })
            
    except Exception as e:
        error_msg = f"Query processing task failed: {str(e)}"
        logger.error(error_msg)
        await _update_task_status(db, session_id, "failed", 0, error_msg)
        await sse_manager.send_to_task(session_id, "query_failed", {
            "error": error_msg,
            "question": question,
            "session_id": session_id
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