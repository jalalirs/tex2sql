from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
import logging
import os

from app.dependencies import get_db
from app.core.database import check_database_health
from app.core.sse_manager import sse_manager
from app.services.event_service import event_service
from app.services.vanna_service import vanna_service
from app.config import settings

router = APIRouter(prefix="/health", tags=["Health"])
logger = logging.getLogger(__name__)

@router.get("/")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "service": "Tex2SQL API",
        "version": "1.0.0"
    }

@router.get("/detailed")
async def detailed_health_check(db: AsyncSession = Depends(get_db)):
    """Detailed health check with component status"""
    health_status = {
        "overall_status": "healthy",
        "timestamp": None,
        "components": {},
        "system_info": {}
    }
    
    try:
        from datetime import datetime
        health_status["timestamp"] = datetime.utcnow().isoformat()
        
        # Database health
        db_healthy = await check_database_health()
        health_status["components"]["database"] = {
            "status": "healthy" if db_healthy else "unhealthy",
            "message": "Database connection successful" if db_healthy else "Database connection failed"
        }
        
        # SSE Manager health
        sse_stats = sse_manager.get_stats()
        health_status["components"]["sse_manager"] = {
            "status": "healthy",
            "active_connections": sse_stats["total_connections"],
            "active_tasks": sse_stats["total_tasks"],
            "connection_details": sse_stats.get("connections_by_task", {})
        }
        
        # Event Service health
        event_stats = event_service.get_statistics()
        health_status["components"]["event_service"] = {
            "status": "healthy",
            "tasks_with_history": event_stats["total_tasks_with_history"],
            "total_events": event_stats["total_events_stored"],
            "average_events_per_task": event_stats["average_events_per_task"]
        }
        
        # LLM Configuration
        health_status["components"]["llm_config"] = {
            "status": "healthy" if settings.OPENAI_API_KEY else "unhealthy",
            "api_key_configured": bool(settings.OPENAI_API_KEY),
            "base_url": settings.OPENAI_BASE_URL,
            "model": settings.OPENAI_MODEL,
            "message": "LLM configuration is valid" if settings.OPENAI_API_KEY else "OpenAI API key not configured"
        }
        
        # File System Health
        data_dir_exists = os.path.exists(settings.DATA_DIR)
        upload_dir_exists = os.path.exists(settings.UPLOAD_DIR)
        
        health_status["components"]["file_system"] = {
            "status": "healthy" if (data_dir_exists and upload_dir_exists) else "unhealthy",
            "data_directory": {
                "path": settings.DATA_DIR,
                "exists": data_dir_exists,
                "writable": os.access(settings.DATA_DIR, os.W_OK) if data_dir_exists else False
            },
            "upload_directory": {
                "path": settings.UPLOAD_DIR,
                "exists": upload_dir_exists,
                "writable": os.access(settings.UPLOAD_DIR, os.W_OK) if upload_dir_exists else False
            }
        }
        
        # System Information
        health_status["system_info"] = {
            "debug_mode": settings.DEBUG,
            "max_upload_size": settings.MAX_UPLOAD_SIZE,
            "sse_heartbeat_interval": settings.SSE_HEARTBEAT_INTERVAL,
            "sse_connection_timeout": settings.SSE_CONNECTION_TIMEOUT
        }
        
        # Overall status determination
        component_statuses = [comp["status"] for comp in health_status["components"].values()]
        if "unhealthy" in component_statuses:
            health_status["overall_status"] = "degraded"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        health_status["overall_status"] = "unhealthy"
        health_status["error"] = str(e)
        return health_status

@router.get("/database")
async def database_health():
    """Database-specific health check"""
    try:
        db_healthy = await check_database_health()
        
        return {
            "status": "healthy" if db_healthy else "unhealthy",
            "database_connected": db_healthy,
            "database_url_configured": bool(settings.DATABASE_URL),
            "message": "Database is accessible" if db_healthy else "Database connection failed"
        }
        
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "database_connected": False,
            "error": str(e)
        }

@router.get("/sse")
async def sse_health():
    """SSE Manager health check"""
    try:
        stats = sse_manager.get_stats()
        
        return {
            "status": "healthy",
            "manager_running": True,
            "active_connections": stats["total_connections"],
            "active_tasks": stats["total_tasks"],
            "connection_details": stats.get("connections_by_task", {}),
            "oldest_connection": stats.get("oldest_connection"),
            "newest_connection": stats.get("newest_connection")
        }
        
    except Exception as e:
        logger.error(f"SSE health check failed: {e}")
        return {
            "status": "unhealthy",
            "manager_running": False,
            "error": str(e)
        }

@router.get("/connections/{connection_id}/vanna")
async def vanna_health_check(connection_id: str, db: AsyncSession = Depends(get_db)):
    """Health check for a specific Vanna instance"""
    try:
        # Get Vanna statistics
        vanna_stats = vanna_service.get_vanna_statistics(connection_id)
        
        # Get connection from database
        from sqlalchemy import select
        from app.models.database import Connection
        import uuid
        
        stmt = select(Connection).where(Connection.id == uuid.UUID(connection_id))
        result = await db.execute(stmt)
        connection = result.scalar_one_or_none()
        
        if not connection:
            raise HTTPException(status_code=404, detail="Connection not found")
        
        health_info = {
            "connection_id": connection_id,
            "connection_name": connection.name,
            "connection_status": connection.status.value,
            "is_trained": connection.status.value == "trained",
            "vanna_statistics": vanna_stats
        }
        
        # If trained, try to validate the Vanna instance
        if connection.status.value == "trained":
            try:
                from app.models.vanna_models import VannaConfig, DatabaseConfig
                
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
                    table_name=connection.table_name
                )
                
                vanna_instance = vanna_service.get_vanna_instance(
                    connection_id, db_config, vanna_config
                )
                
                if vanna_instance:
                    validation_result = vanna_service.validate_vanna_instance(vanna_instance)
                    health_info["vanna_validation"] = validation_result
                    health_info["status"] = "healthy" if validation_result["is_valid"] else "unhealthy"
                else:
                    health_info["status"] = "unhealthy"
                    health_info["error"] = "Could not create Vanna instance"
                    
            except Exception as e:
                health_info["status"] = "unhealthy"
                health_info["vanna_error"] = str(e)
        else:
            health_info["status"] = "not_ready"
            health_info["message"] = f"Connection is in '{connection.status.value}' status, not ready for queries"
        
        return health_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vanna health check failed for connection {connection_id}: {e}")
        return {
            "connection_id": connection_id,
            "status": "unhealthy",
            "error": str(e)
        }

@router.get("/system")
async def system_health():
    """System-level health information"""
    try:
        import psutil
        import platform
        
        # Get system information
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        system_info = {
            "status": "healthy",
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "python_version": platform.python_version()
            },
            "resources": {
                "cpu_percent": cpu_percent,
                "memory": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "percent_used": memory.percent
                },
                "disk": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "percent_used": round((disk.used / disk.total) * 100, 2)
                }
            },
            "application": {
                "data_directory_size_mb": _get_directory_size(settings.DATA_DIR),
                "upload_directory_size_mb": _get_directory_size(settings.UPLOAD_DIR)
            }
        }
        
        # Determine health status based on resource usage
        if (cpu_percent > 90 or 
            memory.percent > 90 or 
            (disk.used / disk.total) > 0.95):
            system_info["status"] = "warning"
            system_info["warnings"] = []
            
            if cpu_percent > 90:
                system_info["warnings"].append("High CPU usage")
            if memory.percent > 90:
                system_info["warnings"].append("High memory usage")
            if (disk.used / disk.total) > 0.95:
                system_info["warnings"].append("Low disk space")
        
        return system_info
        
    except ImportError:
        return {
            "status": "limited",
            "message": "psutil not available for detailed system monitoring",
            "basic_info": {
                "data_directory_exists": os.path.exists(settings.DATA_DIR),
                "upload_directory_exists": os.path.exists(settings.UPLOAD_DIR)
            }
        }
    except Exception as e:
        logger.error(f"System health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@router.post("/test/sse/{task_id}")
async def test_sse_functionality(task_id: str):
    """Test SSE functionality with a specific task ID"""
    try:
        import asyncio
        
        # Send test events
        await sse_manager.send_to_task(task_id, "test_started", {
            "message": "SSE test started",
            "task_id": task_id
        })
        
        # Send progress events
        for i in range(5):
            await asyncio.sleep(0.5)
            await sse_manager.send_to_task(task_id, "test_progress", {
                "message": f"Test progress {i+1}/5",
                "progress": (i+1) * 20,
                "task_id": task_id
            })
        
        await sse_manager.send_to_task(task_id, "test_completed", {
            "message": "SSE test completed successfully",
            "task_id": task_id,
            "success": True
        })
        
        return {
            "status": "success",
            "message": f"Test events sent to task {task_id}",
            "task_id": task_id,
            "stream_url": f"/events/stream/{task_id}"
        }
        
    except Exception as e:
        logger.error(f"SSE test failed: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "task_id": task_id
        }

def _get_directory_size(directory_path: str) -> float:
    """Get directory size in MB"""
    try:
        if not os.path.exists(directory_path):
            return 0.0
        
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(directory_path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except (OSError, FileNotFoundError):
                    pass
        
        return round(total_size / (1024 * 1024), 2)  # Convert to MB
        
    except Exception:
        return 0.0