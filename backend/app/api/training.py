from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import uuid
import logging

from app.dependencies import get_db, get_current_active_user, validate_api_key
from app.services.connection_service import connection_service
from app.models.database import TrainingTask,  User
from app.core.sse_manager import sse_manager
from app.config import settings

router = APIRouter(prefix="/training", tags=["Training"])
logger = logging.getLogger(__name__)


@router.get("/tasks/{task_id}/status")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get training task status (must belong to current user)"""
    try:
        stmt = select(TrainingTask).where(
            TrainingTask.id == task_id,
            TrainingTask.user_id == current_user.id  # Ensure user owns the task
        )
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found or access denied"
            )
        
        return {
            "task_id": task.id,
            "connection_id": task.connection_id,
            "user_id": str(task.user_id),
            "task_type": task.task_type,
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
        logger.error(f"Failed to get task status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task status: {str(e)}"
        )

@router.get("/tasks")
async def list_user_tasks(
    task_type: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List current user's training tasks"""
    try:
        query = select(TrainingTask).where(TrainingTask.user_id == current_user.id)
        
        if task_type:
            query = query.where(TrainingTask.task_type == task_type)
            
        query = query.order_by(TrainingTask.created_at.desc()).limit(50)
        
        result = await db.execute(query)
        tasks = result.scalars().all()
        
        return {
            "tasks": [
                {
                    "task_id": task.id,
                    "connection_id": task.connection_id,
                    "task_type": task.task_type,
                    "status": task.status,
                    "progress": task.progress,
                    "error_message": task.error_message,
                    "started_at": task.started_at,
                    "completed_at": task.completed_at,
                    "created_at": task.created_at
                }
                for task in tasks
            ],
            "total": len(tasks),
            "user_id": str(current_user.id)
        }
        
    except Exception as e:
        logger.error(f"Failed to list user tasks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tasks: {str(e)}"
        )

# ========================
# BACKGROUND TASKS
# ========================


async def _update_task_status(
    db: AsyncSession, 
    task_id: str, 
    status: str, 
    progress: int, 
    error_message: str = None
):
    """Update task status in database"""
    try:
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

async def _update_task_progress(db: AsyncSession, task_id: str, progress: int):
    """Update task progress only"""
    try:
        stmt = select(TrainingTask).where(TrainingTask.id == task_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        
        if task:
            task.progress = progress
            await db.commit()
            
    except Exception as e:
        logger.error(f"Failed to update task progress: {e}")