from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Tex2SQL API"
    DEBUG: bool = False
    SECRET_KEY: str = "your-secret-key-change-in-production"
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/tex2sql"
    
    # For future GCP deployment (commented out for now)
    # DATABASE_URL: str = "postgresql+asyncpg://user:password@/dbname?host=/cloudsql/project:region:instance"
    
    # OpenAI/LLM Configuration
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4"
    
    # File Upload
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    UPLOAD_DIR: str = "uploads"
    
    # Training Data Storage
    DATA_DIR: str = "data"
    
    # SSE Configuration
    SSE_HEARTBEAT_INTERVAL: int = 30  # seconds
    SSE_CONNECTION_TIMEOUT: int = 300  # 5 minutes
    
    # Security
    ALLOWED_HOSTS: list = ["*"]  # Restrict in production
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:8080"]  # Frontend URLs
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

# Validate required settings
def validate_settings():
    """Validate critical settings on startup"""
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY must be set")
    
    # Create necessary directories
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)