from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import joinedload
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status
import logging
from datetime import datetime, timezone, timedelta

from app.models.database import User, Connection, Conversation, Message
from app.models.schemas import (
    UserUpdate, UserResponse, UserStatsResponse,
    ConnectionResponse, ConversationResponse
)

logger = logging.getLogger(__name__)


class UserService:
    """Service for user management operations"""
    
    async def get_user_by_id(self, user_id: str, db: AsyncSession) -> Optional[User]:
        """Get user by ID"""
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_email(self, email: str, db: AsyncSession) -> Optional[User]:
        """Get user by email"""
        result = await db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_username(self, username: str, db: AsyncSession) -> Optional[User]:
        """Get user by username"""
        result = await db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()
    
    async def update_user_profile(
        self, 
        user: User, 
        update_data: UserUpdate, 
        db: AsyncSession
    ) -> User:
        """Update user profile"""
        
        # Update only provided fields
        update_dict = update_data.dict(exclude_unset=True)
        
        for field, value in update_dict.items():
            setattr(user, field, value)
        
        user.updated_at = datetime.now(timezone.utc)
        
        await db.commit()
        await db.refresh(user)
        
        logger.info(f"Profile updated for user: {user.email}")
        return user
    
    async def deactivate_user(self, user: User, db: AsyncSession) -> bool:
        """Deactivate user account"""
        user.is_active = False
        user.updated_at = datetime.now(timezone.utc)
        
        # Also deactivate all user sessions
        from app.services.auth_service import auth_service
        await auth_service.logout_all_sessions(str(user.id), db)
        
        await db.commit()
        
        logger.info(f"User deactivated: {user.email}")
        return True
    
    async def reactivate_user(self, user: User, db: AsyncSession) -> bool:
        """Reactivate user account"""
        user.is_active = True
        user.updated_at = datetime.now(timezone.utc)
        
        await db.commit()
        
        logger.info(f"User reactivated: {user.email}")
        return True
    
    async def delete_user_account(self, user: User, db: AsyncSession) -> bool:
        """Permanently delete user account and all associated data"""
        
        try:
            # Note: Due to cascade deletes in the database models,
            # deleting the user will automatically delete:
            # - All connections
            # - All conversations 
            # - All messages
            # - All training examples
            # - All sessions
            # - All verification tokens
            
            user_email = user.email
            await db.delete(user)
            await db.commit()
            
            logger.info(f"User account deleted: {user_email}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting user account {user.email}: {e}")
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete user account"
            )
    
    async def get_user_stats(self, user: User, db: AsyncSession) -> UserStatsResponse:
        """Get user statistics"""
        
        # Get connection count
        connection_count = await db.execute(
            select(func.count(Connection.id)).where(Connection.user_id == user.id)
        )
        total_connections = connection_count.scalar() or 0
        
        # Get conversation count
        conversation_count = await db.execute(
            select(func.count(Conversation.id)).where(Conversation.user_id == user.id)
        )
        total_conversations = conversation_count.scalar() or 0
        
        # Get active conversation count
        active_conversation_count = await db.execute(
            select(func.count(Conversation.id)).where(
                and_(
                    Conversation.user_id == user.id,
                    Conversation.is_active == True
                )
            )
        )
        active_conversations = active_conversation_count.scalar() or 0
        
        # Get message count
        message_count = await db.execute(
            select(func.count(Message.id)).join(Conversation).where(
                Conversation.user_id == user.id
            )
        )
        total_messages = message_count.scalar() or 0
        
        # Get query count (assistant messages)
        query_count = await db.execute(
            select(func.count(Message.id)).join(Conversation).where(
                and_(
                    Conversation.user_id == user.id,
                    Message.message_type == 'assistant'
                )
            )
        )
        total_queries = query_count.scalar() or 0
        
        # Get last activity (most recent message)
        last_activity_result = await db.execute(
            select(func.max(Message.created_at)).join(Conversation).where(
                Conversation.user_id == user.id
            )
        )
        last_activity = last_activity_result.scalar()
        
        return UserStatsResponse(
            user_id=str(user.id),
            total_connections=total_connections,
            total_conversations=total_conversations,
            total_messages=total_messages,
            total_queries=total_queries,
            active_conversations=active_conversations,
            last_activity=last_activity
        )
    
    async def get_user_connections(
        self, 
        user: User, 
        db: AsyncSession,
        limit: int = 50,
        offset: int = 0
    ) -> List[ConnectionResponse]:
        """Get user's connections"""
        
        result = await db.execute(
            select(Connection).where(
                Connection.user_id == user.id
            ).order_by(desc(Connection.created_at)).limit(limit).offset(offset)
        )
        
        connections = result.scalars().all()
        
        return [
            ConnectionResponse(
                id=str(conn.id),
                name=conn.name,
                server=conn.server,
                database_name=conn.database_name,
                table_name=conn.table_name,
                driver=conn.driver,
                status=conn.status,
                test_successful=conn.test_successful,
                column_descriptions_uploaded=conn.column_descriptions_uploaded,
                generated_examples_count=conn.generated_examples_count,
                total_queries=conn.total_queries or 0,
                last_queried_at=conn.last_queried_at,
                created_at=conn.created_at,
                trained_at=conn.trained_at
            )
            for conn in connections
        ]
    
    async def get_user_conversations(
        self,
        user: User,
        db: AsyncSession,
        connection_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        include_inactive: bool = False
    ) -> List[ConversationResponse]:
        """Get user's conversations"""
        
        query = select(Conversation, Connection.name.label('connection_name')).join(Connection).where(
            Conversation.user_id == user.id
        )
        
        if connection_id:
            query = query.where(Conversation.connection_id == connection_id)
        
        if not include_inactive:
            query = query.where(Conversation.is_active == True)
        
        query = query.order_by(desc(Conversation.last_message_at)).limit(limit).offset(offset)
        
        result = await db.execute(query)
        conversation_data = result.all()
        
        conversations = []
        for conv, connection_name in conversation_data:
            # Get latest message preview
            latest_message_result = await db.execute(
                select(Message.content).where(
                    Message.conversation_id == conv.id
                ).order_by(desc(Message.created_at)).limit(1)
            )
            latest_message = latest_message_result.scalar()
            
            # Truncate latest message for preview
            latest_message_preview = None
            if latest_message:
                latest_message_preview = latest_message[:100] + "..." if len(latest_message) > 100 else latest_message
            
            conversations.append(
                ConversationResponse(
                    id=str(conv.id),
                    connection_id=str(conv.connection_id),
                    connection_name=connection_name,
                    title=conv.title,
                    description=conv.description,
                    is_active=conv.is_active,
                    is_pinned=conv.is_pinned,
                    message_count=conv.message_count,
                    total_queries=conv.total_queries,
                    created_at=conv.created_at,
                    updated_at=conv.updated_at,
                    last_message_at=conv.last_message_at,
                    latest_message=latest_message_preview
                )
            )
        
        return conversations
    
    async def update_user_preferences(
        self,
        user: User,
        preferences: Dict[str, Any],
        db: AsyncSession
    ) -> User:
        """Update user preferences"""
        
        # Merge with existing preferences
        current_prefs = user.preferences or {}
        current_prefs.update(preferences)
        
        user.preferences = current_prefs
        user.updated_at = datetime.now(timezone.utc)
        
        await db.commit()
        await db.refresh(user)
        
        return user
    
    async def get_recent_activity(
        self,
        user: User,
        db: AsyncSession,
        days: int = 30,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get user's recent activity"""
        
        since_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Get recent conversations
        recent_conversations = await db.execute(
            select(Conversation, Connection.name.label('connection_name')).join(Connection).where(
                and_(
                    Conversation.user_id == user.id,
                    Conversation.last_message_at >= since_date
                )
            ).order_by(desc(Conversation.last_message_at)).limit(limit)
        )
        
        activity = []
        for conv, connection_name in recent_conversations.all():
            activity.append({
                "type": "conversation",
                "id": str(conv.id),
                "title": conv.title,
                "connection_name": connection_name,
                "timestamp": conv.last_message_at,
                "message_count": conv.message_count
            })
        
        # Get recent connections
        recent_connections = await db.execute(
            select(Connection).where(
                and_(
                    Connection.user_id == user.id,
                    Connection.created_at >= since_date
                )
            ).order_by(desc(Connection.created_at)).limit(limit)
        )
        
        for conn in recent_connections.scalars():
            activity.append({
                "type": "connection",
                "id": str(conn.id),
                "name": conn.name,
                "timestamp": conn.created_at,
                "status": conn.status
            })
        
        # Sort by timestamp
        activity.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return activity[:limit]


# Create user service instance
user_service = UserService()