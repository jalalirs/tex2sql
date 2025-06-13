import asyncio
import json
import uuid
from typing import Dict, Set, Optional, Any
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from fastapi import Request
from sse_starlette import EventSourceResponse
import logging

from app.models.sse_schemas import SSEEvent, create_sse_event, create_log_event
from app.config import settings

logger = logging.getLogger(__name__)

class SSEConnection:
    """Represents a single SSE connection"""
    
    def __init__(self, connection_id: str, queue: asyncio.Queue, request: Request):
        self.connection_id = connection_id
        self.queue = queue
        self.request = request
        self.created_at = datetime.utcnow()
        self.last_ping = datetime.utcnow()
        self.is_active = True
        self.metadata: Dict[str, Any] = {}
    
    async def send_event(self, event_type: str, data: Dict[str, Any]) -> bool:
        """Send an event to this connection"""
        if not self.is_active:
            return False
        
        try:
            # Create a proper SSE event dict that sse_starlette can handle
            # Add timestamp if not present
            if "timestamp" not in data:
                data["timestamp"] = datetime.utcnow().isoformat()
            
            # Create the event dict for sse_starlette
            event_dict = {
                "event": event_type,
                "data": json.dumps(data, default=str)
            }
            
            await self.queue.put(event_dict)
            return True
        except Exception as e:
            logger.error(f"Failed to send event to connection {self.connection_id}: {e}")
            self.is_active = False
            return False
        
    async def send_log(self, message: str, level: str = "info", source: str = "system") -> bool:
        """Send a log event to this connection"""
        return await self.send_event("log", {
            "message": message,
            "level": level,
            "source": source
        })
    
    def is_expired(self) -> bool:
        """Check if connection has expired"""
        timeout = timedelta(seconds=settings.SSE_CONNECTION_TIMEOUT)
        return datetime.utcnow() - self.last_ping > timeout
    
    def update_ping(self):
        """Update last ping time"""
        self.last_ping = datetime.utcnow()

class SSEManager:
    """Manages all SSE connections and event broadcasting"""
    
    def __init__(self):
        self.connections: Dict[str, SSEConnection] = {}
        self.task_connections: Dict[str, Set[str]] = {}  # task_id -> set of connection_ids
        self.connection_tasks: Dict[str, Set[str]] = {}  # connection_id -> set of task_ids
        self._cleanup_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the SSE manager"""
        logger.info("Starting SSE Manager")
        self._cleanup_task = asyncio.create_task(self._cleanup_expired_connections())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
    
    async def stop(self):
        """Stop the SSE manager"""
        logger.info("Stopping SSE Manager")
        
        # Cancel background tasks
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        
        # Close all connections
        for connection in list(self.connections.values()):
            await self._disconnect(connection.connection_id)
        
        logger.info("SSE Manager stopped")
    
    async def create_connection(self, request: Request, task_id: Optional[str] = None, 
                              metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create a new SSE connection"""
        connection_id = str(uuid.uuid4())
        queue = asyncio.Queue()
        
        connection = SSEConnection(connection_id, queue, request)
        if metadata:
            connection.metadata = metadata
        
        self.connections[connection_id] = connection
        self.connection_tasks[connection_id] = set()
        
        # Associate with task if provided
        if task_id:
            await self.subscribe_to_task(connection_id, task_id)
        
        logger.info(f"Created SSE connection {connection_id} for task {task_id}")
        return connection_id
    
    async def subscribe_to_task(self, connection_id: str, task_id: str):
        """Subscribe a connection to a specific task"""
        if connection_id not in self.connections:
            logger.warning(f"Connection {connection_id} not found for task subscription")
            return
        
        # Add to task mapping
        if task_id not in self.task_connections:
            self.task_connections[task_id] = set()
        self.task_connections[task_id].add(connection_id)
        
        # Add to connection mapping
        self.connection_tasks[connection_id].add(task_id)
        
        logger.debug(f"Subscribed connection {connection_id} to task {task_id}")
    
    async def unsubscribe_from_task(self, connection_id: str, task_id: str):
        """Unsubscribe a connection from a task"""
        if task_id in self.task_connections:
            self.task_connections[task_id].discard(connection_id)
            if not self.task_connections[task_id]:
                del self.task_connections[task_id]
        
        if connection_id in self.connection_tasks:
            self.connection_tasks[connection_id].discard(task_id)
        
        logger.debug(f"Unsubscribed connection {connection_id} from task {task_id}")
    
    async def send_to_connection(self, connection_id: str, event_type: str, 
                               data: Dict[str, Any]) -> bool:
        """Send event to a specific connection"""
        if connection_id not in self.connections:
            logger.warning(f"Connection {connection_id} not found")
            return False
        
        connection = self.connections[connection_id]
        return await connection.send_event(event_type, data)
    
    async def send_to_task(self, task_id: str, event_type: str, data: Dict[str, Any]) -> int:
        """Send event to all connections subscribed to a task"""
        if task_id not in self.task_connections:
            logger.debug(f"No connections found for task {task_id}")
            return 0
        
        sent_count = 0
        failed_connections = []
        connections_to_close = []
        
        for connection_id in self.task_connections[task_id].copy():
            success = await self.send_to_connection(connection_id, event_type, data)
            if success:
                sent_count += 1
                
                # Check if this is a completion event - if so, mark connection for closure
                if event_type in ["test_completed", "training_completed", "data_generation_completed", "completed", "error"]:
                    connections_to_close.append(connection_id)
                    
            else:
                failed_connections.append(connection_id)
        
        # Clean up failed connections
        for connection_id in failed_connections:
            await self.unsubscribe_from_task(connection_id, task_id)
        
        # Close connections that received completion events
        for connection_id in connections_to_close:
            if connection_id in self.connections:
                self.connections[connection_id].is_active = False
                logger.debug(f"Marked connection {connection_id} for closure after completion event")
        
        logger.debug(f"Sent event '{event_type}' to {sent_count} connections for task {task_id}")
        return sent_count
    
    async def broadcast(self, event_type: str, data: Dict[str, Any]) -> int:
        """Broadcast event to all active connections"""
        sent_count = 0
        failed_connections = []
        
        for connection_id, connection in self.connections.items():
            success = await connection.send_event(event_type, data)
            if success:
                sent_count += 1
            else:
                failed_connections.append(connection_id)
        
        # Clean up failed connections
        for connection_id in failed_connections:
            await self._disconnect(connection_id)
        
        logger.debug(f"Broadcasted event '{event_type}' to {sent_count} connections")
        return sent_count
    
    async def send_log_to_task(self, task_id: str, message: str, level: str = "info", 
                             source: str = "system") -> int:
        """Send log message to all connections subscribed to a task"""
        return await self.send_to_task(task_id, "log", {
            "message": message,
            "level": level,
            "source": source
        })
    
    async def get_event_stream(self, connection_id: str):
        """Get event stream for a connection"""
        if connection_id not in self.connections:
            raise ValueError(f"Connection {connection_id} not found")
        
        connection = self.connections[connection_id]
        
        async def event_generator():
            try:
                # Send initial connection event
                task_id = next(iter(self.connection_tasks.get(connection_id, [])), None)
                initial_event = {
                    "event": "connected",
                    "data": json.dumps({
                        "connection_id": connection_id,
                        "task_id": task_id,
                        "message": f"Connected to task {task_id or 'unknown'}",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                }
                yield initial_event
                
                while connection.is_active:
                    try:
                        # Wait for event with timeout
                        event_data = await asyncio.wait_for(
                            connection.queue.get(), 
                            timeout=settings.SSE_HEARTBEAT_INTERVAL
                        )
                        yield event_data
                        connection.update_ping()
                        
                        # Check if this was a completion event - if so, close connection after sending
                        if event_data.get("event") in ["test_completed", "training_completed", "data_generation_completed", "completed", "error"]:
                            logger.debug(f"Received completion event, closing connection {connection_id}")
                            break
                        
                    except asyncio.TimeoutError:
                        # Only send heartbeat if connection is still active and not completed
                        if connection.is_active:
                            heartbeat_data = {
                                "event": "heartbeat",
                                "data": json.dumps({"timestamp": datetime.utcnow().isoformat()})
                            }
                            yield heartbeat_data
                            connection.update_ping()
                        
                    except Exception as e:
                        logger.error(f"Error in event stream for {connection_id}: {e}")
                        break
                        
            except Exception as e:
                logger.error(f"Event generator error for {connection_id}: {e}")
            finally:
                await self._disconnect(connection_id)
        
        return event_generator()
    
    async def _disconnect(self, connection_id: str):
        """Disconnect and clean up a connection"""
        if connection_id not in self.connections:
            return
        
        connection = self.connections[connection_id]
        connection.is_active = False
        
        # Unsubscribe from all tasks
        if connection_id in self.connection_tasks:
            tasks = self.connection_tasks[connection_id].copy()
            for task_id in tasks:
                await self.unsubscribe_from_task(connection_id, task_id)
            del self.connection_tasks[connection_id]
        
        # Remove connection
        del self.connections[connection_id]
        
        logger.debug(f"Disconnected and cleaned up connection {connection_id}")
    
    async def _cleanup_expired_connections(self):
        """Background task to clean up expired connections"""
        while True:
            try:
                expired_connections = []
                
                for connection_id, connection in self.connections.items():
                    if connection.is_expired():
                        expired_connections.append(connection_id)
                
                for connection_id in expired_connections:
                    logger.info(f"Cleaning up expired connection {connection_id}")
                    await self._disconnect(connection_id)
                
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(60)
    
    async def _heartbeat_loop(self):
        """Background task to send heartbeats"""
        while True:
            try:
                await asyncio.sleep(settings.SSE_HEARTBEAT_INTERVAL)
                
                # Heartbeats are sent automatically in get_event_stream on timeout
                # This task just ensures the loop keeps running
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(settings.SSE_HEARTBEAT_INTERVAL)
    
    async def send_completion_and_close(self, task_id: str, event_type: str, data: Dict[str, Any]) -> int:
        """Send completion event and close all connections for the task"""
        sent_count = await self.send_to_task(task_id, event_type, data)
        
        # Give a small delay to ensure the event is sent before closing
        await asyncio.sleep(0.1)
        
        # Close all connections for this task
        if task_id in self.task_connections:
            connections_to_close = list(self.task_connections[task_id])
            for connection_id in connections_to_close:
                await self._disconnect(connection_id)
                logger.debug(f"Closed connection {connection_id} after task {task_id} completion")
        
        return sent_count
    
    def get_connection_count(self) -> int:
        """Get total number of active connections"""
        return len(self.connections)
    
    def get_task_connections(self, task_id: str) -> int:
        """Get number of connections for a specific task"""
        return len(self.task_connections.get(task_id, set()))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get SSE manager statistics"""
        return {
            "total_connections": len(self.connections),
            "total_tasks": len(self.task_connections),
            "connections_by_task": {
                task_id: len(connections) 
                for task_id, connections in self.task_connections.items()
            },
            "oldest_connection": min(
                (conn.created_at for conn in self.connections.values()), 
                default=None
            ),
            "newest_connection": max(
                (conn.created_at for conn in self.connections.values()), 
                default=None
            )
        }

# Global SSE manager instance
sse_manager = SSEManager()