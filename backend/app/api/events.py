from fastapi import APIRouter, Request, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from sse_starlette import EventSourceResponse
from typing import Optional
import logging

from app.core.sse_manager import sse_manager
from app.models.schemas import TaskResponse
from app.dependencies import get_current_user_optional, get_current_active_user
from app.models.database import User

router = APIRouter(prefix="/events", tags=["Server-Sent Events"])
logger = logging.getLogger(__name__)


@router.get("/stream/{task_id}")
async def stream_task_events(
    request: Request,
    task_id: str,
    connection_name: Optional[str] = Query(None, description="Optional connection name for context"),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Stream events for a specific task"""
    try:
        # Create metadata with user context if available
        metadata = {"connection_name": connection_name} if connection_name else {}
        if current_user:
            metadata.update({
                "user_id": str(current_user.id),
                "user_email": current_user.email
            })
        
        # Create SSE connection
        connection_id = await sse_manager.create_connection(
            request, 
            task_id=task_id,
            metadata=metadata if metadata else None
        )
        
        # Get event stream
        event_stream = await sse_manager.get_event_stream(connection_id)
        
        return EventSourceResponse(
            event_stream,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to create event stream for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create event stream: {str(e)}")


@router.get("/stream/connection/{connection_id}")
async def stream_connection_events(
    request: Request,
    connection_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Stream events for a specific connection (for training flow) - requires authentication"""
    try:
        # Verify user owns the connection
        from app.services.connection_service import connection_service
        from app.dependencies import get_db
        from sqlalchemy.ext.asyncio import AsyncSession
        
        # Get database session to verify connection ownership
        db_gen = get_db()
        db = await anext(db_gen)
        
        try:
            # Verify user owns this connection
            connection_response = await connection_service.get_user_connection(db, str(current_user.id), connection_id)
            if not connection_response:
                raise HTTPException(
                    status_code=403, 
                    detail="Access denied: Connection not found or does not belong to user"
                )
        finally:
            await db.close()
        
        # Create SSE connection with user metadata
        sse_connection_id = await sse_manager.create_connection(
            request,
            metadata={
                "user_id": str(current_user.id),
                "user_email": current_user.email,
                "connection_id": connection_id,
                "connection_name": connection_response.name
            }
        )
        
        # Get event stream
        event_stream = await sse_manager.get_event_stream(sse_connection_id)
        
        return EventSourceResponse(
            event_stream,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
                "X-Accel-Buffering": "no"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create event stream for connection {connection_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create event stream: {str(e)}")


@router.get("/stream/conversation/{conversation_id}")
async def stream_conversation_events(
    request: Request,
    conversation_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Stream events for a specific conversation - requires authentication and ownership"""
    try:
        # Verify user owns the conversation
        from app.services.conversation_service import conversation_service
        from app.dependencies import get_db
        from sqlalchemy.ext.asyncio import AsyncSession
        
        # Get database session to verify conversation ownership
        db_gen = get_db()
        db = await anext(db_gen)
        
        try:
            # Verify user owns this conversation
            conversation = await conversation_service.get_conversation(conversation_id, current_user, db)
            if not conversation:
                raise HTTPException(
                    status_code=403, 
                    detail="Access denied: Conversation not found or does not belong to user"
                )
        finally:
            await db.close()
        
        # Create SSE connection with conversation context
        sse_connection_id = await sse_manager.create_connection(
            request,
            metadata={
                "user_id": str(current_user.id),
                "user_email": current_user.email,
                "conversation_id": conversation_id,
                "event_type": "conversation"
            }
        )
        
        # Get event stream
        event_stream = await sse_manager.get_event_stream(sse_connection_id)
        
        return EventSourceResponse(
            event_stream,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
                "X-Accel-Buffering": "no"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create event stream for conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create event stream: {str(e)}")


@router.get("/stats")
async def get_sse_stats(
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Get SSE manager statistics"""
    try:
        stats = sse_manager.get_stats()
        
        # Add user context if authenticated
        response = {
            "success": True,
            "stats": stats
        }
        
        if current_user:
            response["user_context"] = {
                "user_id": str(current_user.id),
                "user_email": current_user.email
            }
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to get SSE stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.post("/test/{task_id}")
async def test_sse_events(
    task_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Test endpoint to send sample events to a task"""
    try:
        # Include user context in test events if available
        base_event_data = {"task_id": task_id}
        if current_user:
            base_event_data.update({
                "user_id": str(current_user.id),
                "user_email": current_user.email
            })
        
        # Send a series of test events
        await sse_manager.send_to_task(task_id, "test_started", {
            **base_event_data,
            "message": "Starting test events"
        })
        
        import asyncio
        for i in range(5):
            await asyncio.sleep(1)
            await sse_manager.send_to_task(task_id, "test_progress", {
                **base_event_data,
                "message": f"Test progress step {i+1}/5",
                "progress": (i+1) * 20
            })
        
        await sse_manager.send_to_task(task_id, "test_completed", {
            **base_event_data,
            "message": "Test events completed",
            "success": True
        })
        
        response = {"success": True, "message": f"Test events sent to task {task_id}"}
        if current_user:
            response["user_id"] = str(current_user.id)
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to send test events: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send test events: {str(e)}")


@router.post("/test/conversation/{conversation_id}")
async def test_conversation_events(
    conversation_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Test conversation-specific events"""
    try:
        # Verify user owns the conversation first
        from app.services.conversation_service import conversation_service
        from app.dependencies import get_db
        from sqlalchemy.ext.asyncio import AsyncSession
        
        # Get database session to verify conversation ownership
        db_gen = get_db()
        db = await anext(db_gen)
        
        try:
            # Verify user owns this conversation
            conversation = await conversation_service.get_conversation(conversation_id, current_user, db)
            if not conversation:
                raise HTTPException(
                    status_code=403, 
                    detail="Access denied: Conversation not found or does not belong to user"
                )
        finally:
            await db.close()
        
        # Send conversation-specific test events
        base_event_data = {
            "conversation_id": conversation_id,
            "user_id": str(current_user.id),
            "user_email": current_user.email
        }
        
        # Simulate conversation query events
        await sse_manager.send_to_task(conversation_id, "query_started", {
            **base_event_data,
            "question": "Test question",
            "message": "Starting test query processing"
        })
        
        import asyncio
        await asyncio.sleep(1)
        
        await sse_manager.send_to_task(conversation_id, "sql_generated", {
            **base_event_data,
            "sql": "SELECT * FROM test_table WHERE id = 1",
            "message": "SQL generated successfully"
        })
        
        await asyncio.sleep(1)
        
        await sse_manager.send_to_task(conversation_id, "data_fetched", {
            **base_event_data,
            "row_count": 5,
            "message": "Data retrieved successfully"
        })
        
        await asyncio.sleep(1)
        
        await sse_manager.send_to_task(conversation_id, "query_completed", {
            **base_event_data,
            "message": "Query processing completed",
            "success": True,
            "has_data": True,
            "has_chart": False,
            "has_summary": True
        })
        
        return {
            "success": True, 
            "message": f"Test conversation events sent to {conversation_id}",
            "user_id": str(current_user.id)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send test conversation events: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send test events: {str(e)}")