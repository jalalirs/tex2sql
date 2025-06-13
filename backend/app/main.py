from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.config import settings, validate_settings
from app.core.database import create_tables, close_database
from app.core.sse_manager import sse_manager
from app.api import events, connections, training, chat, health  # Add health import

# Configure logging
logging.basicConfig(level=logging.INFO if not settings.DEBUG else logging.DEBUG)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Tex2SQL API")
    
    # Validate settings
    validate_settings()
    
    # Create database tables
    await create_tables()
    
    # Start SSE manager
    await sse_manager.start()
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Tex2SQL API")
    
    # Stop SSE manager
    await sse_manager.stop()
    
    # Close database connections
    await close_database()
    
    logger.info("Application shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="Tex2SQL API",
    description="Text-to-SQL AI Platform with real-time training and querying",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(events.router)
app.include_router(connections.router)
app.include_router(training.router)
app.include_router(chat.router)
app.include_router(health.router)  # Add health router

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Tex2SQL API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Basic health check endpoint (legacy)"""
    from app.core.database import check_database_health
    
    db_healthy = await check_database_health()
    sse_stats = sse_manager.get_stats()
    
    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "database": "connected" if db_healthy else "disconnected",
        "sse_connections": sse_stats["total_connections"],
        "sse_tasks": sse_stats["total_tasks"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )