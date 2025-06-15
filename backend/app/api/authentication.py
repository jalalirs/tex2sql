from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.dependencies import (
    get_db, get_current_user, require_user_registration_enabled,
    require_email_verification_enabled, require_password_reset_enabled
)
from app.services.auth_service import auth_service
from app.models.schemas import (
    UserCreate, UserLogin, TokenResponse, TokenRefresh,
    PasswordChange, PasswordReset, PasswordResetConfirm,
    EmailVerification, UserResponse, ErrorResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()


@router.post(
    "/register",
    response_model=TokenResponse,  # Change from UserResponse to TokenResponse
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_user_registration_enabled)],
    summary="Register new user",
    description="Register a new user account and return tokens"
)
async def register(
    user_data: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user"""
    try:
        user = await auth_service.register_user(user_data, db)
        
        # Log registration
        ip_address = request.client.host if request.client else None
        logger.info(f"User registered: {user.email} from {ip_address}")
        
        # Auto-login: Create session and return tokens
        user_agent = request.headers.get("user-agent", "")
        token_response = await auth_service.create_user_session(
            user, db, ip_address, user_agent
        )
        
        return token_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User login",
    description="Authenticate user and return access tokens"
)
async def login(
    login_data: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate user and return tokens"""
    try:
        # Authenticate user
        user = await auth_service.authenticate_user(login_data, db)
        
        # Get request info
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "")
        
        # Create session and tokens
        token_response = await auth_service.create_user_session(
            user, db, ip_address, user_agent
        )
        
        logger.info(f"User logged in: {user.email} from {ip_address}")
        return token_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Refresh access token using refresh token"
)
async def refresh_token(
    token_data: TokenRefresh,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token"""
    try:
        return await auth_service.refresh_access_token(token_data.refresh_token, db)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.post(
    "/logout",
    summary="User logout",
    description="Logout user and invalidate current session"
)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """Logout user and invalidate session"""
    try:
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        # Extract JWT token and get JTI
        import jwt
        from app.config import settings
        
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        token_jti = payload.get("jti")
        
        if token_jti:
            await auth_service.logout_user(token_jti, db)
        
        return {"message": "Successfully logged out"}
        
    except jwt.JWTError:
        # Even if token is invalid, return success for security
        return {"message": "Successfully logged out"}
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return {"message": "Successfully logged out"}


@router.post(
    "/logout-all",
    summary="Logout all sessions",
    description="Logout user from all sessions"
)
async def logout_all_sessions(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Logout user from all sessions"""
    try:
        count = await auth_service.logout_all_sessions(str(current_user.id), db)
        return {"message": f"Logged out from {count} sessions"}
        
    except Exception as e:
        logger.error(f"Logout all error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to logout from all sessions"
        )


@router.post(
    "/change-password",
    summary="Change password",
    description="Change user password"
)
async def change_password(
    password_data: PasswordChange,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change user password"""
    try:
        await auth_service.change_password(
            current_user,
            password_data.current_password,
            password_data.new_password,
            db
        )
        
        return {"message": "Password changed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )


@router.post(
    "/forgot-password",
    dependencies=[Depends(require_password_reset_enabled)],
    summary="Request password reset",
    description="Request password reset link"
)
async def forgot_password(
    reset_data: PasswordReset,
    db: AsyncSession = Depends(get_db)
):
    """Request password reset"""
    try:
        token = await auth_service.create_password_reset_token(reset_data.email, db)
        
        # TODO: Send email with reset link
        # For now, just log the token (remove in production)
        logger.info(f"Password reset token for {reset_data.email}: {token}")
        
        return {"message": "If an account with this email exists, a password reset link has been sent"}
        
    except HTTPException:
        # Always return success message for security
        return {"message": "If an account with this email exists, a password reset link has been sent"}
    except Exception as e:
        logger.error(f"Password reset request error: {e}")
        # Always return success message for security
        return {"message": "If an account with this email exists, a password reset link has been sent"}


@router.post(
    "/reset-password",
    dependencies=[Depends(require_password_reset_enabled)],
    summary="Reset password",
    description="Reset password using token"
)
async def reset_password(
    reset_data: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db)
):
    """Reset password using token"""
    try:
        await auth_service.reset_password_with_token(
            reset_data.token,
            reset_data.new_password,
            db
        )
        
        return {"message": "Password reset successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password reset error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset failed"
        )


@router.post(
    "/verify-email",
    dependencies=[Depends(require_email_verification_enabled)],
    summary="Verify email",
    description="Verify email address using token"
)
async def verify_email(
    verification_data: EmailVerification,
    db: AsyncSession = Depends(get_db)
):
    """Verify email address"""
    try:
        user = await auth_service.verify_email_token(verification_data.token, db)
        
        return {"message": "Email verified successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Email verification failed"
        )


@router.post(
    "/resend-verification",
    dependencies=[Depends(require_email_verification_enabled)],
    summary="Resend verification email",
    description="Resend email verification link"
)
async def resend_verification(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Resend email verification"""
    try:
        if current_user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already verified"
            )
        
        token = await auth_service.create_email_verification_token(str(current_user.id), db)
        
        # TODO: Send email with verification link
        # For now, just log the token (remove in production)
        logger.info(f"Email verification token for {current_user.email}: {token}")
        
        return {"message": "Verification email sent"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resend verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification email"
        )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get current authenticated user information"
)
async def get_me(current_user = Depends(get_current_user)):
    """Get current user information"""
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


@router.get(
    "/check-token",
    summary="Check token validity",
    description="Validate current authentication token"
)
async def check_token(current_user = Depends(get_current_user)):
    """Check if current token is valid"""
    return {
        "valid": True,
        "user_id": str(current_user.id),
        "email": current_user.email,
        "username": current_user.username
    }