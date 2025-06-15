from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import AsyncGenerator, Optional
import logging
import jwt
from jwt import PyJWTError as JWTError

from datetime import datetime, timezone

from app.core.database import get_async_db
from app.config import settings
from app.models.database import User, UserSession
from app.models.schemas import UserResponse

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)

# Database dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency"""
    async for session in get_async_db():
        yield session

# Validate API key dependency
async def validate_api_key():
    """Validate that OpenAI API key is configured"""
    if not settings.OPENAI_API_KEY:
        logger.error("OpenAI API key not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LLM API key not configured"
        )
    return True

# Authentication dependencies
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Get current user from JWT token (optional - returns None if not authenticated)"""
    if not credentials:
        return None
    
    try:
        # Decode JWT token
        payload = jwt.decode(
            credentials.credentials, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        
        user_id: str = payload.get("sub")
        token_jti: str = payload.get("jti")
        
        if not user_id or not token_jti:
            return None
            
    except jwt.ExpiredSignatureError:
        return None
    except JWTError:
        return None
    
    # Get user from database
    try:
        result = await db.execute(
            select(User).where(
                User.id == user_id,
                User.is_active == True
            )
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return None
        
        # Verify session is still active
        session_result = await db.execute(
            select(UserSession).where(
                UserSession.user_id == user_id,
                UserSession.token_jti == token_jti,
                UserSession.is_active == True,
                UserSession.expires_at > datetime.now(timezone.utc)
            )
        )
        session = session_result.scalar_one_or_none()
        
        if not session:
            return None
            
        # Update last used timestamp
        session.last_used_at = datetime.now(timezone.utc)
        await db.commit()
        
        return user
        
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        return None

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current user from JWT token (required - raises exception if not authenticated)"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Decode JWT token
        payload = jwt.decode(
            credentials.credentials, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        
        user_id: str = payload.get("sub")
        token_jti: str = payload.get("jti")
        
        if not user_id or not token_jti:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from database
    try:
        result = await db.execute(
            select(User).where(
                User.id == user_id,
                User.is_active == True
            )
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verify session is still active
        session_result = await db.execute(
            select(UserSession).where(
                UserSession.user_id == user_id,
                UserSession.token_jti == token_jti,
                UserSession.is_active == True,
                UserSession.expires_at > datetime.now(timezone.utc)
            )
        )
        session = session_result.scalar_one_or_none()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired or invalid",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        # Update last used timestamp
        session.last_used_at = datetime.now(timezone.utc)
        await db.commit()
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication error"
        )

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user (must be active and verified if verification is enabled)"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Inactive user"
        )
    
    # Check email verification if enabled
    if settings.ENABLE_EMAIL_VERIFICATION and not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email verification required"
        )
    
    return current_user

async def get_current_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Get current user and verify admin privileges"""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user

async def get_current_super_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Get current user and verify super admin privileges"""
    if current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin privileges required"
        )
    return current_user

# Rate limiting dependency (placeholder for future implementation)
async def rate_limit_check(request: Request):
    """Rate limiting check (placeholder for future Redis-based implementation)"""
    # TODO: Implement Redis-based rate limiting
    # For now, just return True
    return True

# Permission dependencies
async def check_connection_ownership(
    connection_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> bool:
    """Check if current user owns the specified connection"""
    from app.models.database import Connection
    
    result = await db.execute(
        select(Connection).where(
            Connection.id == connection_id,
            Connection.user_id == current_user.id
        )
    )
    connection = result.scalar_one_or_none()
    
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found or access denied"
        )
    
    return True

async def check_conversation_ownership(
    conversation_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> bool:
    """Check if current user owns the specified conversation"""
    from app.models.database import Conversation
    
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        )
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or access denied"
        )
    
    return True

# Feature flag dependencies
async def require_user_registration_enabled():
    """Check if user registration is enabled"""
    if not settings.ENABLE_USER_REGISTRATION:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User registration is currently disabled"
        )
    return True

async def require_email_verification_enabled():
    """Check if email verification is enabled"""
    if not settings.ENABLE_EMAIL_VERIFICATION:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email verification is not enabled"
        )
    return True

async def require_password_reset_enabled():
    """Check if password reset is enabled"""
    if not settings.ENABLE_PASSWORD_RESET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset is not enabled"
        )
    return True

# Common dependency combinations
CommonDeps = Depends(get_db)
AuthDeps = Depends(get_current_active_user)
AdminDeps = Depends(get_current_admin_user)
SuperAdminDeps = Depends(get_current_super_admin_user)
APIKeyDeps = Depends(validate_api_key)
RateLimitDeps = Depends(rate_limit_check)

# Optional auth (for endpoints that work with or without auth)
OptionalAuthDeps = Depends(get_current_user_optional)

# Combined dependencies for common use cases
class AuthenticatedDeps:
    """Common authenticated dependencies"""
    def __init__(
        self, 
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
        _: bool = Depends(validate_api_key)
    ):
        self.db = db
        self.current_user = current_user

class AdminDeps:
    """Admin-only dependencies"""
    def __init__(
        self,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_admin_user),
        _: bool = Depends(validate_api_key)
    ):
        self.db = db
        self.current_user = current_user

# Export commonly used dependencies
__all__ = [
    "get_db",
    "get_current_user",
    "get_current_user_optional", 
    "get_current_active_user",
    "get_current_admin_user",
    "get_current_super_admin_user",
    "check_connection_ownership",
    "check_conversation_ownership",
    "validate_api_key",
    "rate_limit_check",
    "CommonDeps",
    "AuthDeps", 
    "AdminDeps",
    "SuperAdminDeps",
    "APIKeyDeps",
    "RateLimitDeps",
    "OptionalAuthDeps",
    "AuthenticatedDeps",
    "require_user_registration_enabled",
    "require_email_verification_enabled",
    "require_password_reset_enabled"
]