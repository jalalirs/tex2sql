from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any
import logging

from app.dependencies import (
    get_db, get_current_active_user, get_current_admin_user
)
from app.services.user_service import user_service
from app.models.schemas import (
    UserUpdate, UserResponse, UserStatsResponse,
    ConnectionResponse, ConversationResponse, ErrorResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
    description="Get current authenticated user's profile information"
)
async def get_my_profile(
    current_user = Depends(get_current_active_user)
):
    """Get current user profile"""
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        profile_picture_url=current_user.profile_picture_url,
        bio=current_user.bio,
        company=current_user.company,
        job_title=current_user.job_title,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at
    )


@router.put(
    "/me",
    response_model=UserResponse,
    summary="Update user profile",
    description="Update current user's profile information"
)
async def update_my_profile(
    update_data: UserUpdate,
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user profile"""
    try:
        updated_user = await user_service.update_user_profile(current_user, update_data, db)
        
        return UserResponse(
            id=str(updated_user.id),
            email=updated_user.email,
            username=updated_user.username,
            full_name=updated_user.full_name,
            role=updated_user.role,
            is_active=updated_user.is_active,
            is_verified=updated_user.is_verified,
            profile_picture_url=updated_user.profile_picture_url,
            bio=updated_user.bio,
            company=updated_user.company,
            job_title=updated_user.job_title,
            created_at=updated_user.created_at,
            last_login_at=updated_user.last_login_at
        )
        
    except Exception as e:
        logger.error(f"Error updating user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )


@router.get(
    "/me/stats",
    response_model=UserStatsResponse,
    summary="Get user statistics",
    description="Get current user's usage statistics"
)
async def get_my_stats(
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user statistics"""
    try:
        return await user_service.get_user_stats(current_user, db)
        
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user statistics"
        )


@router.get(
    "/me/connections",
    response_model=list[ConnectionResponse],
    summary="Get user connections",
    description="Get current user's database connections"
)
async def get_my_connections(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's connections"""
    try:
        return await user_service.get_user_connections(current_user, db, limit, offset)
        
    except Exception as e:
        logger.error(f"Error getting user connections: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get connections"
        )


@router.get(
    "/me/conversations",
    response_model=list[ConversationResponse],
    summary="Get user conversations",
    description="Get current user's conversations"
)
async def get_my_conversations(
    connection_id: Optional[str] = Query(None, description="Filter by connection ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    include_inactive: bool = Query(False, description="Include inactive conversations"),
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's conversations"""
    try:
        return await user_service.get_user_conversations(
            current_user, db, connection_id, limit, offset, include_inactive
        )
        
    except Exception as e:
        logger.error(f"Error getting user conversations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get conversations"
        )


@router.get(
    "/me/activity",
    summary="Get recent activity",
    description="Get current user's recent activity"
)
async def get_my_activity(
    days: int = Query(30, ge=1, le=90, description="Number of days to look back"),
    limit: int = Query(20, ge=1, le=100),
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's recent activity"""
    try:
        return await user_service.get_recent_activity(current_user, db, days, limit)
        
    except Exception as e:
        logger.error(f"Error getting user activity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get activity"
        )


@router.put(
    "/me/preferences",
    summary="Update user preferences",
    description="Update current user's preferences"
)
async def update_my_preferences(
    preferences: Dict[str, Any],
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user preferences"""
    try:
        updated_user = await user_service.update_user_preferences(
            current_user, preferences, db
        )
        
        return {
            "message": "Preferences updated successfully",
            "preferences": updated_user.preferences
        }
        
    except Exception as e:
        logger.error(f"Error updating user preferences: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences"
        )


@router.delete(
    "/me",
    summary="Delete user account",
    description="Permanently delete current user account and all data"
)
async def delete_my_account(
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete current user account"""
    try:
        success = await user_service.delete_user_account(current_user, db)
        
        if success:
            return {"message": "Account deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete account"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user account: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account"
        )


@router.post(
    "/me/deactivate",
    summary="Deactivate user account",
    description="Deactivate current user account (can be reactivated by admin)"
)
async def deactivate_my_account(
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Deactivate current user account"""
    try:
        success = await user_service.deactivate_user(current_user, db)
        
        if success:
            return {"message": "Account deactivated successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to deactivate account"
            )
        
    except Exception as e:
        logger.error(f"Error deactivating user account: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate account"
        )


# Admin-only endpoints
@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID (Admin)",
    description="Get user information by ID (admin only)"
)
async def get_user(
    user_id: str,
    current_user = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user by ID (admin only)"""
    try:
        user = await user_service.get_user_by_id(user_id, db)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return UserResponse(
            id=str(user.id),
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            is_verified=user.is_verified,
            profile_picture_url=user.profile_picture_url,
            bio=user.bio,
            company=user.company,
            job_title=user.job_title,
            created_at=user.created_at,
            last_login_at=user.last_login_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user"
        )


@router.get(
    "/{user_id}/stats",
    response_model=UserStatsResponse,
    summary="Get user statistics (Admin)",
    description="Get user statistics by ID (admin only)"
)
async def get_user_stats(
    user_id: str,
    current_user = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user statistics (admin only)"""
    try:
        user = await user_service.get_user_by_id(user_id, db)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return await user_service.get_user_stats(user, db)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user stats for {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user statistics"
        )


@router.post(
    "/{user_id}/reactivate",
    summary="Reactivate user account (Admin)",
    description="Reactivate a deactivated user account (admin only)"
)
async def reactivate_user(
    user_id: str,
    current_user = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Reactivate user account (admin only)"""
    try:
        user = await user_service.get_user_by_id(user_id, db)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        success = await user_service.reactivate_user(user, db)
        
        if success:
            return {"message": f"User {user.email} reactivated successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reactivate user"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reactivating user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reactivate user"
        )


@router.post(
    "/{user_id}/deactivate",
    summary="Deactivate user account (Admin)",
    description="Deactivate a user account (admin only)"
)
async def admin_deactivate_user(
    user_id: str,
    current_user = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Deactivate user account (admin only)"""
    try:
        user = await user_service.get_user_by_id(user_id, db)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if user.id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate your own account"
            )
        
        success = await user_service.deactivate_user(user, db)
        
        if success:
            return {"message": f"User {user.email} deactivated successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to deactivate user"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate user"
        )