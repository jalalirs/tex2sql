from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator
import logging

from app.core.database import get_async_db
from app.config import settings

logger = logging.getLogger(__name__)

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

# Common dependencies
CommonDeps = Depends(get_db)
APIKeyDeps = Depends(validate_api_key)