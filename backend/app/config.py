from pydantic_settings import BaseSettings
from typing import Optional, List
import os
import secrets

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Tex2SQL API"
    DEBUG: bool = False
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "Text-to-SQL AI Platform with real-time training and querying"
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/tex2sql"
    
    # For future GCP deployment (commented out for now)
    # DATABASE_URL: str = "postgresql+asyncpg://user:password@/dbname?host=/cloudsql/project:region:instance"
    
    # OpenAI/LLM Configuration
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4"
    
    # Authentication & Security
    SECRET_KEY: str = secrets.token_urlsafe(32)  # Auto-generate if not provided
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Password security
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_NUMBERS: bool = True
    PASSWORD_REQUIRE_SPECIAL: bool = False
    
    # Email verification
    EMAIL_VERIFICATION_EXPIRE_HOURS: int = 24
    PASSWORD_RESET_EXPIRE_HOURS: int = 2
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 100
    
    # Session management
    MAX_SESSIONS_PER_USER: int = 5
    SESSION_CLEANUP_INTERVAL_HOURS: int = 24
    
    # File Upload
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    UPLOAD_DIR: str = "uploads"
    ALLOWED_FILE_TYPES: List[str] = [".csv", ".xlsx", ".json"]
    
    # Training Data Storage
    DATA_DIR: str = "data"
    
    # SSE Configuration
    SSE_HEARTBEAT_INTERVAL: int = 30  # seconds
    SSE_CONNECTION_TIMEOUT: int = 300  # 5 minutes
    SSE_MAX_CONNECTIONS_PER_USER: int = 10
    
    # Security Headers
    ALLOWED_HOSTS: List[str] = ["*"]  # Restrict in production
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000", 
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080"
    ]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    CORS_ALLOW_HEADERS: List[str] = [
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "User-Agent",
        "DNT",
        "Cache-Control",
        "X-Mx-ReqToken",
        "Keep-Alive",
        "X-Requested-With",
        "If-Modified-Since",
        "X-CSRF-Token"
    ]
    
    # Email Configuration (for future email features)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_TLS: bool = True
    EMAIL_FROM: Optional[str] = None
    EMAIL_FROM_NAME: Optional[str] = "Tex2SQL Platform"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: Optional[str] = None
    
    # Analytics & Monitoring
    ENABLE_ANALYTICS: bool = True
    ANALYTICS_RETENTION_DAYS: int = 90
    
    # Feature Flags
    ENABLE_USER_REGISTRATION: bool = True
    ENABLE_EMAIL_VERIFICATION: bool = False  # Set to True when email is configured
    ENABLE_PASSWORD_RESET: bool = False      # Set to True when email is configured
    ENABLE_CONVERSATION_SHARING: bool = False  # Future feature
    ENABLE_ADMIN_PANEL: bool = True
    
    # Conversation Settings
    MAX_CONVERSATIONS_PER_USER: int = 100
    MAX_MESSAGES_PER_CONVERSATION: int = 1000
    CONVERSATION_TITLE_MAX_LENGTH: int = 500
    MESSAGE_CONTENT_MAX_LENGTH: int = 10000
    
    # Query Settings
    MAX_QUERY_EXECUTION_TIME: int = 300  # 5 minutes
    MAX_RESULT_ROWS: int = 10000
    ENABLE_QUERY_CACHING: bool = False  # Your requirement was no caching
    
    # Development & Testing
    DEVELOPMENT_MODE: bool = False
    TESTING_MODE: bool = False
    MOCK_EXTERNAL_APIS: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        # Allow extra fields for future configuration options
        extra = "allow"

# Create settings instance
settings = Settings()

# Validation functions
def validate_settings():
    """Validate critical settings on startup"""
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY must be set")
    
    if not settings.SECRET_KEY or settings.SECRET_KEY == "your-secret-key-change-in-production":
        if not settings.DEVELOPMENT_MODE:
            raise ValueError("SECRET_KEY must be set to a secure value in production")
    
    # Validate email configuration if email features are enabled
    if settings.ENABLE_EMAIL_VERIFICATION or settings.ENABLE_PASSWORD_RESET:
        if not all([settings.SMTP_HOST, settings.SMTP_USERNAME, settings.SMTP_PASSWORD, settings.EMAIL_FROM]):
            raise ValueError("Email configuration required when email features are enabled")
    
    # Create necessary directories
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    
    # Validate CORS origins in production
    if not settings.DEVELOPMENT_MODE and "*" in settings.ALLOWED_HOSTS:
        raise ValueError("ALLOWED_HOSTS must be restricted in production")

def get_cors_config():
    """Get CORS configuration for FastAPI"""
    return {
        "allow_origins": settings.CORS_ORIGINS,
        "allow_credentials": settings.CORS_ALLOW_CREDENTIALS,
        "allow_methods": settings.CORS_ALLOW_METHODS,
        "allow_headers": settings.CORS_ALLOW_HEADERS,
    }

def get_database_url(async_driver: bool = True) -> str:
    """Get database URL with appropriate driver"""
    if async_driver:
        return settings.DATABASE_URL
    else:
        # Convert async URL to sync for Alembic
        return settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

# Export commonly used settings
__all__ = [
    "settings",
    "validate_settings", 
    "get_cors_config",
    "get_database_url"
]