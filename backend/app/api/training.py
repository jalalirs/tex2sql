from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select  # ADD THIS IMPORT
from typing import Optional
import uuid
import logging

from app.dependencies import get_db, validate_api_key
from app.services.training_service import training_service
from app.core.vanna_wrapper import vanna_service
from app.services.connection_service import connection_service
from app.models.schemas import GenerateExamplesRequest, TaskResponse
from app.models.database import TrainingTask, Connection, ConnectionStatus  # Connection is already imported
from app.models.vanna_models import VannaConfig, DatabaseConfig
from app.core.sse_manager import sse_manager
from app.utils.sse_utils import SSELogger
from app.config import settings

router = APIRouter(prefix="/training", tags=["Training"])
logger = logging.getLogger(__name__)

@router.post("/connections/{connection_id}/generate-data", response_model=TaskResponse)
async def generate_training_data(
    connection_id: str,
    request: GenerateExamplesRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(validate_api_key)
):
    """Generate training data for a connection"""
    try:
        # Validate connection exists
        connection = await connection_service.get_connection(db, connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found"
            )
        
        # Check connection status
        if connection.status not in [ConnectionStatus.TEST_SUCCESS, ConnectionStatus.DATA_GENERATED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Connection must be in TEST_SUCCESS status, currently: {connection.status}"
            )
        
        # Create task for tracking
        task_id = str(uuid.uuid4())
        task = TrainingTask(
            id=task_id,
            connection_id=connection_id,
            task_type="generate_data",
            status="running"
        )
        
        db.add(task)
        await db.commit()
        
        # Start data generation in background
        background_tasks.add_task(
            _run_data_generation,
            connection_id,
            request.num_examples,
            task_id,
            db
        )
        
        return TaskResponse(
            task_id=task_id,
            connection_id=connection_id,
            task_type="generate_data",
            status="running",
            progress=0,
            stream_url=f"/events/stream/{task_id}",
            created_at=task.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start data generation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start data generation: {str(e)}"
        )

@router.post("/connections/{connection_id}/train", response_model=TaskResponse)
async def train_model(
    connection_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(validate_api_key)
):
    """Train Vanna model for a connection"""
    try:
        # Validate connection exists
        connection = await connection_service.get_connection(db, connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found"
            )
        
        # Check connection status
        if connection.status != ConnectionStatus.DATA_GENERATED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Connection must have generated data first, currently: {connection.status}"
            )
        
        # Create task for tracking
        task_id = str(uuid.uuid4())
        task = TrainingTask(
            id=task_id,
            connection_id=connection_id,
            task_type="train_model",
            status="running"
        )
        
        db.add(task)
        await db.commit()
        
        # Start training in background
        background_tasks.add_task(
            _run_model_training,
            connection_id,
            task_id,
            db
        )
        
        return TaskResponse(
            task_id=task_id,
            connection_id=connection_id,
            task_type="train_model",
            status="running",
            progress=0,
            stream_url=f"/events/stream/{task_id}",
            created_at=task.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start model training: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start model training: {str(e)}"
        )

@router.get("/tasks/{task_id}/status")
async def get_task_status(
    task_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get training task status"""
    try:
        stmt = select(TrainingTask).where(TrainingTask.id == task_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        return {
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
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task status: {str(e)}"
        )

async def _run_data_generation(
    connection_id: str, 
    num_examples: int, 
    task_id: str, 
    db: AsyncSession
):
    """Background task for data generation"""
    sse_logger = SSELogger(sse_manager, task_id, "data_generation")
    
    try:
        await _update_task_status(db, task_id, "running", 0)
        await sse_logger.info(f"Starting data generation for {num_examples} examples")
        
        # Run data generation
        result = await training_service.generate_training_data(
            db, connection_id, num_examples, task_id
        )
        
        if result.success:
            await _update_task_status(db, task_id, "completed", 100)
            await sse_manager.send_to_task(task_id, "generation_completed", {
                "success": True,
                "total_generated": result.total_generated,
                "failed_count": result.failed_count,
                "connection_id": connection_id,
                "task_id": task_id
            })
            await sse_logger.info("Data generation completed successfully")
        else:
            await _update_task_status(db, task_id, "failed", 0, result.error_message)
            await sse_manager.send_to_task(task_id, "generation_failed", {
                "success": False,
                "error": result.error_message,
                "connection_id": connection_id,
                "task_id": task_id
            })
            await sse_logger.error(f"Data generation failed: {result.error_message}")
            
    except Exception as e:
        error_msg = f"Data generation task failed: {str(e)}"
        logger.error(error_msg)
        await _update_task_status(db, task_id, "failed", 0, error_msg)
        await sse_manager.send_to_task(task_id, "generation_failed", {
            "success": False,
            "error": error_msg,
            "connection_id": connection_id,
            "task_id": task_id
        })
        await sse_logger.error(error_msg)

async def _run_model_training(connection_id: str, task_id: str, db: AsyncSession):
    """Background task for model training"""
    sse_logger = SSELogger(sse_manager, task_id, "training")
    
    try:
        await _update_task_status(db, task_id, "running", 0)
        await sse_logger.info("Starting model training")
        
        # FIXED: Get raw connection details with all fields (including username/password)
        stmt = select(Connection).where(Connection.id == uuid.UUID(connection_id))
        result = await db.execute(stmt)
        connection = result.scalar_one_or_none()
        
        if not connection:
            raise ValueError("Connection not found")
        
        # Create configurations
        vanna_config = VannaConfig(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            model=settings.OPENAI_MODEL
        )
        
        db_config = DatabaseConfig(
            server=connection.server,
            database_name=connection.database_name,
            username=connection.username,  # NOW WORKS: Raw Connection has username
            password=connection.password,  # NOW WORKS: Raw Connection has password
            table_name=connection.table_name
        )
        
        # Progress callback for SSE updates
        async def progress_callback(progress: int, message: str):
            await sse_logger.progress(progress, message)
            await _update_task_progress(db, task_id, progress)
        
        # Train model
        vanna_instance = await vanna_service.setup_and_train_vanna(
            connection_id, db_config, vanna_config, retrain=True, progress_callback=progress_callback
        )
        
        if vanna_instance:
            # Update connection status to trained
            await connection_service.update_connection_status(db, connection_id, ConnectionStatus.TRAINED)
            
            await _update_task_status(db, task_id, "completed", 100)
            await sse_manager.send_to_task(task_id, "training_completed", {
                "success": True,
                "connection_id": connection_id,
                "connection_name": connection.name,
                "task_id": task_id
            })
            await sse_logger.info("Model training completed successfully")
        else:
            raise ValueError("Failed to train Vanna model")
            
    except Exception as e:
        error_msg = f"Model training failed: {str(e)}"
        logger.error(error_msg)
        await _update_task_status(db, task_id, "failed", 0, error_msg)
        await sse_manager.send_to_task(task_id, "training_failed", {
            "success": False,
            "error": error_msg,
            "connection_id": connection_id,
            "task_id": task_id
        })
        await sse_logger.error(error_msg)

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