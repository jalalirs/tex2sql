import json
from typing import Dict, Any, Optional
from datetime import datetime
from app.models.sse_schemas import SSEEvent

def format_sse_data(event_type: str, data: Dict[str, Any], event_id: Optional[str] = None) -> str:
    """Format data as SSE message"""
    lines = []
    
    if event_id:
        lines.append(f"id: {event_id}")
    
    lines.append(f"event: {event_type}")
    
    # Ensure timestamp is included
    if "timestamp" not in data:
        data["timestamp"] = datetime.utcnow().isoformat()
    
    json_data = json.dumps(data, default=str)
    
    # For SSE, we need to prefix each line of JSON data with "data: "
    # Split data into multiple lines if needed (SSE spec)
    for line in json_data.split('\n'):
        lines.append(f"data: {line}")
    
    lines.append("")  # Empty line to end the event
    
    return "\n".join(lines) + "\n"  # Add final newline

def create_progress_event(task_id: str, progress: int, message: str, 
                         event_type: str = "progress") -> str:
    """Create a progress update event"""
    return format_sse_data(event_type, {
        "task_id": task_id,
        "progress": progress,
        "message": message
    })

def create_error_event(task_id: str, error_message: str, 
                      event_type: str = "error") -> str:
    """Create an error event"""
    return format_sse_data(event_type, {
        "task_id": task_id,
        "error": error_message,
        "success": False
    })

def create_completion_event(task_id: str, result_data: Dict[str, Any], 
                           event_type: str = "completed") -> str:
    """Create a completion event"""
    return format_sse_data(event_type, {
        "task_id": task_id,
        "success": True,
        **result_data
    })

def create_log_event_formatted(message: str, level: str = "info", 
                              source: str = "system") -> str:
    """Create a formatted log event"""
    return format_sse_data("log", {
        "message": message,
        "level": level,
        "source": source
    })

class SSELogger:
    """Logger that sends logs via SSE"""
    
    def __init__(self, sse_manager, task_id: str, source: str = "system"):
        self.sse_manager = sse_manager
        self.task_id = task_id
        self.source = source
    
    async def info(self, message: str):
        """Send info log"""
        await self.sse_manager.send_log_to_task(self.task_id, message, "info", self.source)
    
    async def warning(self, message: str):
        """Send warning log"""
        await self.sse_manager.send_log_to_task(self.task_id, message, "warning", self.source)
    
    async def error(self, message: str):
        """Send error log"""
        await self.sse_manager.send_log_to_task(self.task_id, message, "error", self.source)
    
    async def debug(self, message: str):
        """Send debug log"""
        await self.sse_manager.send_log_to_task(self.task_id, message, "debug", self.source)
    
    async def progress(self, progress: int, message: str):
        """Send progress update"""
        await self.sse_manager.send_to_task(self.task_id, "progress", {
            "progress": progress,
            "message": message,
            "source": self.source
        })