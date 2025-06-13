from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import StreamingResponse
from sse_starlette import EventSourceResponse
from typing import Optional
import logging

from app.core.sse_manager import sse_manager
from app.models.schemas import TaskResponse

router = APIRouter(prefix="/events", tags=["Server-Sent Events"])
logger = logging.getLogger(__name__)


@router.get("/stream/{task_id}")
async def stream_task_events(
    request: Request,
    task_id: str,
    connection_name: Optional[str] = Query(None, description="Optional connection name for context")
):
    """Stream events for a specific task"""
    try:
        # Create SSE connection
        connection_id = await sse_manager.create_connection(
            request, 
            task_id=task_id,
            metadata={"connection_name": connection_name} if connection_name else None
        )
        
        # DON'T send initial connection event here - it's handled in get_event_stream
        # This was causing the race condition
        
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
    connection_id: str
):
    """Stream events for a specific connection (for training flow)"""
    try:
        # This endpoint is for when we have a connection_id instead of task_id
        # Create SSE connection without task subscription initially
        sse_connection_id = await sse_manager.create_connection(request)
        
        # Get event stream (connection event will be sent automatically)
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
        
    except Exception as e:
        logger.error(f"Failed to create event stream for connection {connection_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create event stream: {str(e)}")

@router.get("/stats")
async def get_sse_stats():
    """Get SSE manager statistics"""
    try:
        stats = sse_manager.get_stats()
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Failed to get SSE stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

@router.post("/test/{task_id}")
async def test_sse_events(task_id: str):
    """Test endpoint to send sample events to a task"""
    try:
        # Send a series of test events
        await sse_manager.send_to_task(task_id, "test_started", {
            "message": "Starting test events",
            "task_id": task_id
        })
        
        import asyncio
        for i in range(5):
            await asyncio.sleep(1)
            await sse_manager.send_to_task(task_id, "test_progress", {
                "message": f"Test progress step {i+1}/5",
                "progress": (i+1) * 20,
                "task_id": task_id
            })
        
        await sse_manager.send_to_task(task_id, "test_completed", {
            "message": "Test events completed",
            "task_id": task_id,
            "success": True
        })
        
        return {"success": True, "message": f"Test events sent to task {task_id}"}
        
    except Exception as e:
        logger.error(f"Failed to send test events: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send test events: {str(e)}")