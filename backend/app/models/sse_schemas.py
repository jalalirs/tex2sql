from pydantic import BaseModel
from typing import Optional, Dict, Any, List, Union
from datetime import datetime

class SSEEvent(BaseModel):
    event: str
    data: Dict[str, Any]
    timestamp: datetime = None

    def __init__(self, **data):
        if 'timestamp' not in data:
            data['timestamp'] = datetime.utcnow()
        super().__init__(**data)

    def to_sse_format(self) -> str:
        """Convert to SSE format string"""
        import json
        return f"event: {self.event}\ndata: {json.dumps(self.data)}\n\n"

# Test Connection Events
class TestConnectionStarted(SSEEvent):
    event: str = "test_connection_started"

class TestConnectionProgress(SSEEvent):
    event: str = "test_connection_progress"
    # data should contain: {"message": str, "progress": int, "step": str}

class TestConnectionCompleted(SSEEvent):
    event: str = "test_connection_completed"
    # data should contain: {
    #   "success": bool, 
    #   "sample_data": list, 
    #   "column_info": dict,
    #   "connection_id": str  # UUID
    # }

class TestConnectionError(SSEEvent):
    event: str = "test_connection_error"
    # data should contain: {"error": str, "task_id": str}

# Data Generation Events
class DataGenerationStarted(SSEEvent):
    event: str = "data_generation_started"
    # data should contain: {"connection_id": str, "num_examples": int}

class DataGenerationProgress(SSEEvent):
    event: str = "data_generation_progress"
    # data should contain: {
    #   "message": str, 
    #   "progress": int, 
    #   "current_example": int, 
    #   "total_examples": int,
    #   "connection_id": str
    # }

class DataGenerationExampleGenerated(SSEEvent):
    event: str = "data_generation_example"
    # data should contain: {
    #   "question": str,
    #   "sql": str,
    #   "example_number": int,
    #   "connection_id": str
    # }

class DataGenerationCompleted(SSEEvent):
    event: str = "data_generation_completed"
    # data should contain: {
    #   "examples": list, 
    #   "total_generated": int,
    #   "connection_id": str,
    #   "success": bool
    # }

class DataGenerationError(SSEEvent):
    event: str = "data_generation_error"
    # data should contain: {"error": str, "connection_id": str}

# Training Events
class TrainingStarted(SSEEvent):
    event: str = "training_started"
    # data should contain: {"connection_id": str, "connection_name": str}

class TrainingProgress(SSEEvent):
    event: str = "training_progress"
    # data should contain: {
    #   "message": str, 
    #   "progress": int, 
    #   "step": str,
    #   "connection_id": str
    # }

class TrainingCompleted(SSEEvent):
    event: str = "training_completed"
    # data should contain: {
    #   "connection_id": str, 
    #   "training_time": float,
    #   "success": bool
    # }

class TrainingError(SSEEvent):
    event: str = "training_error"
    # data should contain: {"error": str, "connection_id": str}

# Generic Events
class LogEvent(SSEEvent):
    event: str = "log"
    # data should contain: {
    #   "message": str, 
    #   "level": str,  # "info", "warning", "error", "debug"
    #   "timestamp": str,
    #   "source": str  # "test", "generation", "training"
    # }

class TaskStatusUpdate(SSEEvent):
    event: str = "task_status"
    # data should contain: {
    #   "task_id": str,
    #   "status": str,
    #   "progress": int,
    #   "message": str
    # }

# Utility functions for SSE
def create_sse_event(event_type: str, data: Dict[str, Any]) -> str:
    """Helper function to create SSE formatted string"""
    import json
    timestamp = datetime.utcnow().isoformat()
    
    event_data = {
        **data,
        "timestamp": timestamp
    }
    
    return f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n"

def create_log_event(message: str, level: str = "info", source: str = "system") -> str:
    """Helper to create log events"""
    return create_sse_event("log", {
        "message": message,
        "level": level,
        "source": source
    })