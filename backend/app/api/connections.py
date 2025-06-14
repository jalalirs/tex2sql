from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import uuid
import logging

from app.dependencies import get_db, get_current_active_user, validate_api_key
from app.services.connection_service import connection_service
from app.models.schemas import (
    ConnectionCreate, ConnectionResponse, ConnectionTestRequest, ConnectionTestResult,
    ConnectionListResponse, TrainingDataView, ColumnDescriptionItem, TaskResponse,
    ConnectionDeleteResponse
)
from app.models.database import TrainingTask, ConnectionStatus, User
from app.models.schemas import GenerateExamplesRequest, TaskResponse
from app.models.vanna_models import VannaConfig, DatabaseConfig
from app.models.database import TrainingTask, User
from app.core.sse_manager import sse_manager
from app.utils.file_handler import file_handler
from app.utils.validators import validate_connection_data
from app.config import settings
from app.utils.sse_utils import SSELogger
from app.services.training_service import training_service
from app.services.vanna_service import vanna_service
from app.api.training import _update_task_progress




router = APIRouter(prefix="/connections", tags=["Connections"])
logger = logging.getLogger(__name__)

@router.post("/test", response_model=ConnectionTestResult)
async def test_connection(
    request: ConnectionTestRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
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
            user_id=current_user.id,  # Track user
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
            current_user,
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

async def _run_connection_test(connection_data: ConnectionCreate, task_id: str, user: User, db: AsyncSession):
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
    driver: Optional[str] = Form(None),
    column_descriptions_file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(validate_api_key)
):
    """Create a new database connection for the authenticated user"""
    try:
        # Check if user already has a connection with this name
        existing_connection = await connection_service.get_user_connection_by_name(
            db, current_user.id, name
        )
        if existing_connection:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"You already have a connection named '{name}'"
            )
        
        # Build connection data from form fields
        connection_data = ConnectionCreate(
            name=name,
            server=server,
            database_name=database_name,
            username=username,
            password=password,
            table_name=table_name,
            driver=driver
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
        
        # Create connection for user
        connection = await connection_service.create_connection_for_user(
            db, current_user, connection_data, column_descriptions
        )
        
        logger.info(f"Created connection: {connection.id} for user {current_user.email}")
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
async def list_connections(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List current user's connections"""
    try:
        connections = await connection_service.list_user_connections(db, current_user.id)
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
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific connection (must belong to current user)"""
    try:
        connection = await connection_service.get_user_connection(db, current_user.id, connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found or access denied"
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
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get training data view for a user's connection"""
    try:
        # First check if user owns the connection
        connection = await connection_service.get_user_connection(db, current_user.id, connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found or access denied"
            )
        
        training_data = await connection_service.get_training_data_view(db, connection_id)
        if not training_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No training data available"
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
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a connection and all associated data (must belong to current user)"""
    try:
        # Check if connection exists and belongs to user
        connection = await connection_service.get_user_connection(db, current_user.id, connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found or access denied"
            )
        
        # Delete connection (this will also delete conversations and messages via cascade)
        success = await connection_service.delete_user_connection(db, current_user.id, connection_id)
        
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

# Add these new endpoints to app/api/connections.py

@router.post("/{connection_id}/refresh-schema")
async def refresh_connection_schema(
    connection_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(validate_api_key)
):
    """Refresh and store schema information for user's connection"""
    try:
        # Check if connection exists and belongs to user
        connection = await connection_service.get_user_connection(db, current_user.id, connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found or access denied"
            )
        
        # Create task for tracking
        task_id = str(uuid.uuid4())
        task = TrainingTask(
            id=task_id,
            connection_id=connection_id,
            user_id=current_user.id,
            task_type="refresh_schema",
            status="running"
        )
        
        db.add(task)
        await db.commit()
        
        # Start schema refresh in background
        background_tasks.add_task(
            _run_schema_refresh,
            connection_id,
            task_id,
            current_user,
            db
        )
        
        return TaskResponse(
            task_id=task_id,
            connection_id=connection_id,
            task_type="refresh_schema",
            status="running",
            progress=0,
            stream_url=f"/events/stream/{task_id}",
            created_at=task.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start schema refresh: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start schema refresh: {str(e)}"
        )

@router.get("/{connection_id}/schema")
async def get_connection_schema(
    connection_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get stored schema information for user's connection"""
    try:
        # Check if connection exists and belongs to user
        connection = await connection_service.get_user_connection(db, current_user.id, connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found or access denied"
            )
        
        # Get schema from storage
        schema_data = await connection_service.get_connection_schema(connection_id)
        
        if not schema_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Schema not found. Try refreshing the schema first."
            )
        
        return {
            "connection_id": connection_id,
            "connection_name": connection.name,
            "schema": schema_data,
            "last_refreshed": schema_data.get("last_refreshed"),
            "total_columns": len(schema_data.get("columns", {}))
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get schema for connection {connection_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get schema: {str(e)}"
        )

@router.get("/{connection_id}/column-descriptions")
async def get_column_descriptions(
    connection_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get column descriptions for user's connection"""
    try:
        # Check if connection exists and belongs to user
        connection = await connection_service.get_user_connection(db, current_user.id, connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found or access denied"
            )
        
        # Get column descriptions from database and files
        column_descriptions = await connection_service.get_column_descriptions(db, connection_id)
        
        return {
            "connection_id": connection_id,
            "connection_name": connection.name,
            "column_descriptions": column_descriptions,
            "total_columns": len(column_descriptions),
            "has_descriptions": any(desc.get("description") for desc in column_descriptions)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get column descriptions for {connection_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get column descriptions: {str(e)}"
        )

@router.put("/{connection_id}/column-descriptions")
async def update_column_descriptions(
    connection_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(validate_api_key)
):
    """Update column descriptions for user's connection"""
    try:
        # Check if connection exists and belongs to user
        connection = await connection_service.get_user_connection(db, current_user.id, connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found or access denied"
            )
        
        # Process and validate CSV file
        try:
            column_descriptions = await file_handler.process_column_descriptions_csv(file)
            logger.info(f"Processed {len(column_descriptions)} column descriptions")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error processing CSV file: {str(e)}"
            )
        
        # Update column descriptions in database and storage
        success = await connection_service.update_column_descriptions(
            db, connection_id, column_descriptions
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update column descriptions"
            )
        
        # Update connection flag
        await connection_service.update_connection_column_descriptions_flag(
            db, connection_id, True
        )
        
        return {
            "success": True,
            "message": f"Updated descriptions for {len(column_descriptions)} columns",
            "connection_id": connection_id,
            "total_columns": len(column_descriptions)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update column descriptions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update column descriptions: {str(e)}"
        )

# Background task for schema refresh
async def _run_schema_refresh(
    connection_id: str,
    task_id: str,
    user: User,
    db: AsyncSession
):
    """Background task to refresh schema"""
    try:
        await _update_task_status(db, task_id, "running", 0)
        
        # Get connection details
        connection = await connection_service.get_connection_by_id(db, connection_id)
        if not connection:
            raise ValueError("Connection not found")
        
        # Verify user ownership
        if str(connection.user_id) != str(user.id):
            raise ValueError("Access denied: Connection does not belong to user")
        
        # Create connection data for schema analysis
        connection_data = ConnectionCreate(
            name=connection.name,
            server=connection.server,
            database_name=connection.database_name,
            username=connection.username,
            password=connection.password,
            table_name=connection.table_name,
            driver=connection.driver
        )
        
        # Run schema refresh
        result = await connection_service.refresh_connection_schema(
            connection_data, connection_id, task_id
        )
        
        if result.success:
            await _update_task_status(db, task_id, "completed", 100)
            await sse_manager.send_to_task(task_id, "schema_refresh_completed", {
                "success": True,
                "connection_id": connection_id,
                "total_columns": len(result.column_info) if result.column_info else 0,
                "task_id": task_id
            })
        else:
            await _update_task_status(db, task_id, "failed", 0, result.error_message)
            await sse_manager.send_to_task(task_id, "schema_refresh_failed", {
                "success": False,
                "error": result.error_message,
                "task_id": task_id
            })
            
    except Exception as e:
        error_msg = f"Schema refresh failed: {str(e)}"
        logger.error(error_msg)
        await _update_task_status(db, task_id, "failed", 0, error_msg)
        await sse_manager.send_to_task(task_id, "schema_refresh_failed", {
            "success": False,
            "error": error_msg,
            "task_id": task_id
        })


@router.post("/{connection_id}/generate-data", response_model=TaskResponse)
async def generate_training_data(
    connection_id: str,
    request: GenerateExamplesRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(validate_api_key)
):
    """Generate training data for a user's connection"""
    try:
        # Validate connection exists and belongs to user
        connection = await connection_service.get_user_connection(db, str(current_user.id), connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found or access denied"
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
            user_id=current_user.id,  # Track user
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
            current_user,
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

# In app/api/training.py, replace the train_model function with this fixed version:

@router.post("{connection_id}/train", response_model=TaskResponse)
async def train_model(
    connection_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(validate_api_key)
):
    """Train Vanna model for a user's connection"""
    try:
        # Validate connection exists and belongs to user
        connection = await connection_service.get_user_connection(db, str(current_user.id), connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found or access denied"
            )
        
        # FIXED: Allow training with test_success status (no data generation required)
        if connection.status not in [ConnectionStatus.TEST_SUCCESS, ConnectionStatus.DATA_GENERATED, ConnectionStatus.TRAINED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Connection must be successfully tested first, currently: {connection.status}"
            )
        
        # Create task for tracking
        task_id = str(uuid.uuid4())
        task = TrainingTask(
            id=task_id,
            connection_id=connection_id,
            user_id=current_user.id,
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
            current_user,
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

@router.post("/{connection_id}/validate-csv")
async def validate_column_descriptions_csv(
    connection_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Validate column descriptions CSV file format for user's connection"""
    try:
        # Check if connection exists and belongs to user
        connection = await connection_service.get_user_connection(db, current_user.id, connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found or access denied"
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


async def _run_data_generation(
    connection_id: str, 
    num_examples: int, 
    task_id: str,
    user: User,
    db: AsyncSession
):
    """Background task for data generation"""
    sse_logger = SSELogger(sse_manager, task_id, "data_generation")
    
    try:
        await _update_task_status(db, task_id, "running", 0)
        await sse_logger.info(f"Starting data generation for {num_examples} examples")
        await sse_manager.send_to_task(task_id, "data_generation_started", {
            "user_id": str(user.id),
            "connection_id": connection_id,
            "num_examples": num_examples,
            "task_id": task_id
        })
        
        # Run data generation
        result = await training_service.generate_training_data(
            db, user, connection_id, num_examples, task_id
        )
                
        if result.success:
            await _update_task_status(db, task_id, "completed", 100)
            await sse_manager.send_to_task(task_id, "data_generation_completed", {
                "success": True,
                "total_generated": result.total_generated,
                "failed_count": result.failed_count,
                "connection_id": connection_id,
                "user_id": str(user.id),
                "task_id": task_id
            })
            await sse_logger.info("Data generation completed successfully")
        else:
            await _update_task_status(db, task_id, "failed", 0, result.error_message)
            await sse_manager.send_to_task(task_id, "data_generation_error", {
                "success": False,
                "error": result.error_message,
                "connection_id": connection_id,
                "user_id": str(user.id),
                "task_id": task_id
            })
            await sse_logger.error(f"Data generation failed: {result.error_message}")
            
    except Exception as e:
        error_msg = f"Data generation task failed: {str(e)}"
        logger.error(error_msg)
        await _update_task_status(db, task_id, "failed", 0, error_msg)
        await sse_manager.send_to_task(task_id, "data_generation_error", {
            "success": False,
            "error": error_msg,
            "connection_id": connection_id,
            "user_id": str(user.id),
            "task_id": task_id
        })
        await sse_logger.error(error_msg)

async def _run_model_training(
    connection_id: str, 
    task_id: str, 
    user: User,
    db: AsyncSession
):
    """Background task for model training"""
    sse_logger = SSELogger(sse_manager, task_id, "training")
    
    try:
        await _update_task_status(db, task_id, "running", 0)
        await sse_logger.info("Starting model training")
        await sse_manager.send_to_task(task_id, "training_started", {
            "user_id": str(user.id),
            "connection_id": connection_id,
            "task_id": task_id
        })
        
        # Get raw connection details with all fields
        connection = await connection_service.get_connection_by_id(db, connection_id)
        if not connection:
            raise ValueError("Connection not found")
        
        # Verify user ownership
        if str(connection.user_id) != str(user.id):
            raise ValueError("Access denied: Connection does not belong to user")
        
        # Create configurations
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
            driver=connection.driver or "ODBC Driver 17 for SQL Server"
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
                "user_id": str(user.id),
                "task_id": task_id
            })
            await sse_logger.info("Model training completed successfully")
        else:
            raise ValueError("Failed to train Vanna model")
            
    except Exception as e:
        error_msg = f"Model training failed: {str(e)}"
        logger.error(error_msg)
        await _update_task_status(db, task_id, "failed", 0, error_msg)
        await sse_manager.send_to_task(task_id, "training_error", {
            "success": False,
            "error": error_msg,
            "connection_id": connection_id,
            "user_id": str(user.id),
            "task_id": task_id
        })
        await sse_logger.error(error_msg)


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