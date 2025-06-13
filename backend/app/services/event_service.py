import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from app.core.sse_manager import sse_manager
from app.models.sse_schemas import (
    SSEEvent, TestConnectionStarted, TestConnectionProgress, TestConnectionCompleted,
    DataGenerationStarted, DataGenerationProgress, TrainingStarted, TrainingProgress,
    LogEvent, TaskStatusUpdate
)

logger = logging.getLogger(__name__)

class EventService:
    """Centralized service for managing and broadcasting events"""
    
    def __init__(self):
        self.event_history: Dict[str, List[Dict[str, Any]]] = {}
        self.max_history_per_task = 100
    
    async def broadcast_connection_test_started(self, task_id: str, connection_name: str):
        """Broadcast connection test started event"""
        event_data = {
            "task_id": task_id,
            "connection_name": connection_name,
            "message": f"Starting connection test for '{connection_name}'"
        }
        
        await sse_manager.send_to_task(task_id, "test_connection_started", event_data)
        await self._store_event(task_id, "test_connection_started", event_data)
        logger.info(f"Connection test started for task {task_id}")
    
    async def broadcast_connection_test_progress(
        self, 
        task_id: str, 
        progress: int, 
        message: str,
        step: str = None
    ):
        """Broadcast connection test progress"""
        event_data = {
            "task_id": task_id,
            "progress": progress,
            "message": message,
            "step": step or "testing"
        }
        
        await sse_manager.send_to_task(task_id, "test_connection_progress", event_data)
        await self._store_event(task_id, "test_connection_progress", event_data)
    
    async def broadcast_connection_test_completed(
        self, 
        task_id: str, 
        success: bool,
        sample_data: Optional[List[Dict[str, Any]]] = None,
        column_info: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ):
        """Broadcast connection test completion"""
        event_data = {
            "task_id": task_id,
            "success": success,
            "sample_data": sample_data,
            "column_info": column_info,
            "error_message": error_message
        }
        
        event_type = "test_connection_completed" if success else "test_connection_failed"
        await sse_manager.send_to_task(task_id, event_type, event_data)
        await self._store_event(task_id, event_type, event_data)
        logger.info(f"Connection test {'completed' if success else 'failed'} for task {task_id}")
    
    async def broadcast_data_generation_started(
        self, 
        task_id: str, 
        connection_id: str,
        num_examples: int
    ):
        """Broadcast data generation started"""
        event_data = {
            "task_id": task_id,
            "connection_id": connection_id,
            "num_examples": num_examples,
            "message": f"Starting generation of {num_examples} training examples"
        }
        
        await sse_manager.send_to_task(task_id, "data_generation_started", event_data)
        await self._store_event(task_id, "data_generation_started", event_data)
        logger.info(f"Data generation started for task {task_id}")
    
    async def broadcast_data_generation_progress(
        self,
        task_id: str,
        current_example: int,
        total_examples: int,
        progress: int,
        message: str,
        example_data: Optional[Dict[str, str]] = None
    ):
        """Broadcast data generation progress"""
        event_data = {
            "task_id": task_id,
            "current_example": current_example,
            "total_examples": total_examples,
            "progress": progress,
            "message": message
        }
        
        if example_data:
            event_data["example"] = example_data
            await sse_manager.send_to_task(task_id, "example_generated", event_data)
        else:
            await sse_manager.send_to_task(task_id, "data_generation_progress", event_data)
        
        await self._store_event(task_id, "data_generation_progress", event_data)
    
    async def broadcast_data_generation_completed(
        self,
        task_id: str,
        connection_id: str,
        total_generated: int,
        failed_count: int,
        success: bool,
        error_message: Optional[str] = None
    ):
        """Broadcast data generation completion"""
        event_data = {
            "task_id": task_id,
            "connection_id": connection_id,
            "total_generated": total_generated,
            "failed_count": failed_count,
            "success": success,
            "error_message": error_message
        }
        
        event_type = "data_generation_completed" if success else "data_generation_failed"
        await sse_manager.send_to_task(task_id, event_type, event_data)
        await self._store_event(task_id, event_type, event_data)
        logger.info(f"Data generation {'completed' if success else 'failed'} for task {task_id}")
    
    async def broadcast_training_started(
        self,
        task_id: str,
        connection_id: str,
        connection_name: str
    ):
        """Broadcast model training started"""
        event_data = {
            "task_id": task_id,
            "connection_id": connection_id,
            "connection_name": connection_name,
            "message": f"Starting model training for '{connection_name}'"
        }
        
        await sse_manager.send_to_task(task_id, "training_started", event_data)
        await self._store_event(task_id, "training_started", event_data)
        logger.info(f"Model training started for task {task_id}")
    
    async def broadcast_training_progress(
        self,
        task_id: str,
        progress: int,
        message: str,
        step: str,
        connection_id: str
    ):
        """Broadcast training progress"""
        event_data = {
            "task_id": task_id,
            "progress": progress,
            "message": message,
            "step": step,
            "connection_id": connection_id
        }
        
        await sse_manager.send_to_task(task_id, "training_progress", event_data)
        await self._store_event(task_id, "training_progress", event_data)
    
    async def broadcast_training_completed(
        self,
        task_id: str,
        connection_id: str,
        success: bool,
        training_time: Optional[float] = None,
        error_message: Optional[str] = None
    ):
        """Broadcast training completion"""
        event_data = {
            "task_id": task_id,
            "connection_id": connection_id,
            "success": success,
            "training_time": training_time,
            "error_message": error_message
        }
        
        event_type = "training_completed" if success else "training_failed"
        await sse_manager.send_to_task(task_id, event_type, event_data)
        await self._store_event(task_id, event_type, event_data)
        logger.info(f"Model training {'completed' if success else 'failed'} for task {task_id}")
    
    async def broadcast_query_started(
        self,
        session_id: str,
        connection_id: str,
        question: str
    ):
        """Broadcast query processing started"""
        event_data = {
            "session_id": session_id,
            "connection_id": connection_id,
            "question": question,
            "message": f"Processing query: {question[:50]}..."
        }
        
        await sse_manager.send_to_task(session_id, "query_started", event_data)
        await self._store_event(session_id, "query_started", event_data)
        logger.info(f"Query processing started for session {session_id}")
    
    async def broadcast_sql_generated(
        self,
        session_id: str,
        question: str,
        sql: str
    ):
        """Broadcast SQL generation"""
        event_data = {
            "session_id": session_id,
            "question": question,
            "sql": sql
        }
        
        await sse_manager.send_to_task(session_id, "sql_generated", event_data)
        await self._store_event(session_id, "sql_generated", event_data)
    
    async def broadcast_data_fetched(
        self,
        session_id: str,
        row_count: int,
        preview_data: List[Dict[str, Any]]
    ):
        """Broadcast data fetch completion"""
        event_data = {
            "session_id": session_id,
            "row_count": row_count,
            "preview_data": preview_data[:5] if preview_data else []  # First 5 rows
        }
        
        await sse_manager.send_to_task(session_id, "data_fetched", event_data)
        await self._store_event(session_id, "data_fetched", event_data)
    
    async def broadcast_chart_generated(
        self,
        session_id: str,
        chart_data: Dict[str, Any],
        chart_code: Optional[str] = None
    ):
        """Broadcast chart generation"""
        event_data = {
            "session_id": session_id,
            "chart_data": chart_data,
            "chart_code": chart_code,
            "has_chart": True
        }
        
        await sse_manager.send_to_task(session_id, "chart_generated", event_data)
        await self._store_event(session_id, "chart_generated", event_data)
    
    async def broadcast_summary_generated(
        self,
        session_id: str,
        summary: str
    ):
        """Broadcast summary generation"""
        event_data = {
            "session_id": session_id,
            "summary": summary
        }
        
        await sse_manager.send_to_task(session_id, "summary_generated", event_data)
        await self._store_event(session_id, "summary_generated", event_data)
    
    async def broadcast_followup_generated(
        self,
        session_id: str,
        questions: List[str]
    ):
        """Broadcast follow-up questions"""
        event_data = {
            "session_id": session_id,
            "questions": questions[:5],  # Limit to 5
            "total_questions": len(questions)
        }
        
        await sse_manager.send_to_task(session_id, "followup_generated", event_data)
        await self._store_event(session_id, "followup_generated", event_data)
    
    async def broadcast_query_completed(
        self,
        session_id: str,
        success: bool,
        has_data: bool,
        has_chart: bool,
        has_summary: bool,
        error_message: Optional[str] = None
    ):
        """Broadcast query completion"""
        event_data = {
            "session_id": session_id,
            "success": success,
            "has_data": has_data,
            "has_chart": has_chart,
            "has_summary": has_summary,
            "error_message": error_message
        }
        
        event_type = "query_completed" if success else "query_failed"
        await sse_manager.send_to_task(session_id, event_type, event_data)
        await self._store_event(session_id, event_type, event_data)
        logger.info(f"Query processing {'completed' if success else 'failed'} for session {session_id}")
    
    async def broadcast_log(
        self,
        task_id: str,
        message: str,
        level: str = "info",
        source: str = "system"
    ):
        """Broadcast log message"""
        event_data = {
            "message": message,
            "level": level,
            "source": source,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await sse_manager.send_to_task(task_id, "log", event_data)
        await self._store_event(task_id, "log", event_data)
    
    async def broadcast_task_status_update(
        self,
        task_id: str,
        status: str,
        progress: int,
        message: str
    ):
        """Broadcast task status update"""
        event_data = {
            "task_id": task_id,
            "status": status,
            "progress": progress,
            "message": message
        }
        
        await sse_manager.send_to_task(task_id, "task_status", event_data)
        await self._store_event(task_id, "task_status", event_data)
    
    async def get_task_event_history(self, task_id: str) -> List[Dict[str, Any]]:
        """Get event history for a task"""
        return self.event_history.get(task_id, [])
    
    async def clear_task_history(self, task_id: str):
        """Clear event history for a task"""
        if task_id in self.event_history:
            del self.event_history[task_id]
    
    async def _store_event(self, task_id: str, event_type: str, event_data: Dict[str, Any]):
        """Store event in history"""
        if task_id not in self.event_history:
            self.event_history[task_id] = []
        
        event_record = {
            "event_type": event_type,
            "data": event_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.event_history[task_id].append(event_record)
        
        # Limit history size
        if len(self.event_history[task_id]) > self.max_history_per_task:
            self.event_history[task_id] = self.event_history[task_id][-self.max_history_per_task:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get event service statistics"""
        total_events = sum(len(events) for events in self.event_history.values())
        
        return {
            "total_tasks_with_history": len(self.event_history),
            "total_events_stored": total_events,
            "average_events_per_task": total_events / len(self.event_history) if self.event_history else 0,
            "max_history_per_task": self.max_history_per_task
        }

# Global event service instance
event_service = EventService()