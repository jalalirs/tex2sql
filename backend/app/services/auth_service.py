import jwt
import bcrypt
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from fastapi import HTTPException, status
import logging

from app.config import settings
from app.models.database import User, UserSession, EmailVerificationToken, PasswordResetToken
from app.models.schemas import UserCreate, UserLogin, TokenResponse, UserResponse

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication and authorization service"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
    
    @staticmethod
    def generate_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Generate a JWT token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        
        # Add issued at time
        to_encode.update({"iat": datetime.now(timezone.utc)})
        
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def generate_refresh_token() -> str:
        """Generate a secure refresh token"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def generate_verification_token() -> str:
        """Generate a secure verification token"""
        return secrets.token_urlsafe(32)
    
    async def register_user(self, user_data: UserCreate, db: AsyncSession) -> User:
        """Register a new user"""
        # Check if user already exists
        existing_user = await db.execute(
            select(User).where(
                (User.email == user_data.email) | (User.username == user_data.username)
            )
        )
        if existing_user.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email or username already exists"
            )
        
        # Hash password
        hashed_password = self.hash_password(user_data.password)
        
        # Create user
        user = User(
            email=user_data.email,
            username=user_data.username,
            full_name=user_data.full_name,
            hashed_password=hashed_password,
            company=user_data.company,
            job_title=user_data.job_title,
            is_verified=not settings.ENABLE_EMAIL_VERIFICATION,  # Auto-verify if email verification disabled
            preferences={}
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        # Generate email verification token if enabled
        if settings.ENABLE_EMAIL_VERIFICATION:
            await self.create_email_verification_token(user.id, db)
        
        logger.info(f"User registered: {user.email}")
        return user
    
    async def authenticate_user(self, login_data: UserLogin, db: AsyncSession) -> User:
        """Authenticate a user by email and password"""
        # Get user by email
        result = await db.execute(
            select(User).where(User.email == login_data.email)
        )
        user = result.scalar_one_or_none()
        
        if not user or not self.verify_password(login_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User account is disabled"
            )
        
        # Update last login
        user.last_login_at = datetime.now(timezone.utc)
        await db.commit()
        
        return user
    
    async def create_user_session(
        self, 
        user: User, 
        db: AsyncSession,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> TokenResponse:
        """Create a new user session with tokens"""
        
        # Clean up old sessions if user has too many
        await self.cleanup_user_sessions(user.id, db)
        
        # Generate tokens
        token_jti = secrets.token_urlsafe(32)
        refresh_token = self.generate_refresh_token()
        
        # Create access token
        access_token_data = {
            "sub": str(user.id),
            "jti": token_jti,
            "email": user.email,
            "username": user.username,
            "role": user.role
        }
        
        access_token = self.generate_token(
            access_token_data,
            timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        # Create session record
        session = UserSession(
            user_id=user.id,
            token_jti=token_jti,
            refresh_token=refresh_token,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
        
        db.add(session)
        await db.commit()
        
        # Create user response
        user_response = UserResponse(
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
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_response
        )
    
    async def refresh_access_token(self, refresh_token: str, db: AsyncSession) -> TokenResponse:
        """Refresh an access token using a refresh token"""
        
        # Find session with this refresh token
        result = await db.execute(
            select(UserSession, User).join(User).where(
                and_(
                    UserSession.refresh_token == refresh_token,
                    UserSession.is_active == True,
                    UserSession.expires_at > datetime.now(timezone.utc),
                    User.is_active == True
                )
            )
        )
        
        session_user = result.first()
        if not session_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )
        
        session, user = session_user
        
        # Generate new tokens
        new_token_jti = secrets.token_urlsafe(32)
        new_refresh_token = self.generate_refresh_token()
        
        # Create new access token
        access_token_data = {
            "sub": str(user.id),
            "jti": new_token_jti,
            "email": user.email,
            "username": user.username,
            "role": user.role
        }
        
        access_token = self.generate_token(
            access_token_data,
            timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        # Update session
        session.token_jti = new_token_jti
        session.refresh_token = new_refresh_token
        session.last_used_at = datetime.now(timezone.utc)
        session.expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        await db.commit()
        
        # Create user response
        user_response = UserResponse(
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
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_response
        )
    
    async def logout_user(self, token_jti: str, db: AsyncSession) -> bool:
        """Logout a user by invalidating their session"""
        result = await db.execute(
            select(UserSession).where(UserSession.token_jti == token_jti)
        )
        session = result.scalar_one_or_none()
        
        if session:
            session.is_active = False
            await db.commit()
            return True
        
        return False
    
    async def logout_all_sessions(self, user_id: str, db: AsyncSession) -> int:
        """Logout all sessions for a user"""
        result = await db.execute(
            select(UserSession).where(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.is_active == True
                )
            )
        )
        sessions = result.scalars().all()
        
        for session in sessions:
            session.is_active = False
        
        await db.commit()
        return len(sessions)
    
    async def cleanup_user_sessions(self, user_id: str, db: AsyncSession):
        """Clean up old sessions for a user"""
        # Get active sessions count
        result = await db.execute(
            select(func.count(UserSession.id)).where(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.is_active == True,
                    UserSession.expires_at > datetime.now(timezone.utc)
                )
            )
        )
        active_count = result.scalar()
        
        # If user has too many sessions, deactivate oldest ones
        if active_count >= settings.MAX_SESSIONS_PER_USER:
            sessions_to_remove = active_count - settings.MAX_SESSIONS_PER_USER + 1
            
            old_sessions = await db.execute(
                select(UserSession).where(
                    and_(
                        UserSession.user_id == user_id,
                        UserSession.is_active == True
                    )
                ).order_by(UserSession.last_used_at.asc()).limit(sessions_to_remove)
            )
            
            for session in old_sessions.scalars():
                session.is_active = False
            
            await db.commit()
    
    async def create_email_verification_token(self, user_id: str, db: AsyncSession) -> str:
        """Create email verification token"""
        token = self.generate_verification_token()
        
        verification_token = EmailVerificationToken(
            user_id=user_id,
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.EMAIL_VERIFICATION_EXPIRE_HOURS)
        )
        
        db.add(verification_token)
        await db.commit()
        
        return token
    
    async def verify_email_token(self, token: str, db: AsyncSession) -> User:
        """Verify email using token"""
        result = await db.execute(
            select(EmailVerificationToken, User).join(User).where(
                and_(
                    EmailVerificationToken.token == token,
                    EmailVerificationToken.is_used == False,
                    EmailVerificationToken.expires_at > datetime.now(timezone.utc)
                )
            )
        )
        
        token_user = result.first()
        if not token_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification token"
            )
        
        verification_token, user = token_user
        
        # Mark token as used
        verification_token.is_used = True
        
        # Mark user as verified
        user.is_verified = True
        user.email_verified_at = datetime.now(timezone.utc)
        
        await db.commit()
        
        logger.info(f"Email verified for user: {user.email}")
        return user
    
    async def create_password_reset_token(self, email: str, db: AsyncSession) -> str:
        """Create password reset token"""
        # Check if user exists
        result = await db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            # Don't reveal if user exists or not
            raise HTTPException(
                status_code=status.HTTP_200_OK,
                detail="If an account with this email exists, a password reset link has been sent"
            )
        
        token = self.generate_verification_token()
        
        reset_token = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.PASSWORD_RESET_EXPIRE_HOURS)
        )
        
        db.add(reset_token)
        await db.commit()
        
        return token
    
    async def reset_password_with_token(self, token: str, new_password: str, db: AsyncSession) -> User:
        """Reset password using token"""
        result = await db.execute(
            select(PasswordResetToken, User).join(User).where(
                and_(
                    PasswordResetToken.token == token,
                    PasswordResetToken.is_used == False,
                    PasswordResetToken.expires_at > datetime.now(timezone.utc)
                )
            )
        )
        
        token_user = result.first()
        if not token_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )
        
        reset_token, user = token_user
        
        # Hash new password
        hashed_password = self.hash_password(new_password)
        
        # Update user password
        user.hashed_password = hashed_password
        
        # Mark token as used
        reset_token.is_used = True
        
        # Invalidate all user sessions (force re-login)
        await self.logout_all_sessions(str(user.id), db)
        
        await db.commit()
        
        logger.info(f"Password reset for user: {user.email}")
        return user
    
    async def change_password(self, user: User, current_password: str, new_password: str, db: AsyncSession) -> bool:
        """Change user password"""
        # Verify current password
        if not self.verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Hash new password
        hashed_password = self.hash_password(new_password)
        
        # Update password
        user.hashed_password = hashed_password
        
        # Invalidate all other sessions (keep current one)
        result = await db.execute(
            select(UserSession).where(
                and_(
                    UserSession.user_id == user.id,
                    UserSession.is_active == True
                )
            )
        )
        sessions = result.scalars().all()
        
        # Keep only the most recently used session (current one)
        if len(sessions) > 1:
            sessions_sorted = sorted(sessions, key=lambda s: s.last_used_at, reverse=True)
            for session in sessions_sorted[1:]:  # All except the most recent
                session.is_active = False
        
        await db.commit()
        
        logger.info(f"Password changed for user: {user.email}")
        return True


# Create auth service instance
auth_service = AuthService()