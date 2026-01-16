"""
Authentication and authorization utilities.
"""
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from datetime import datetime
from ..database import get_db
from ..models.user import User, UserRole
from ..models.impersonation import ImpersonationSession
from ..config import settings
from typing import Optional, List


def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user.
    
    Supports two authentication methods:
    1. Bearer token (Authorization header) - for API clients like Postman
    2. Session-based (cookies) - for web frontend
    
    Priority: Bearer token is checked first, then session.
    
    Also handles impersonation tokens:
    - If token has is_impersonation flag, uses impersonated user ID from 'sub'
    - Verifies impersonation session is still active
    - Stores original user ID in request state for audit logging
    
    Raises:
        HTTPException: If user is not authenticated
    """
    auth0_id = None
    user_id = None  # For email/password tokens
    is_impersonation = False
    original_user_id = None
    impersonation_session_id = None
    payload = None
    
    # Method 1: Check for Bearer token in Authorization header
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        
        try:
            # Decode the token to get user info
            # Try to verify with SECRET_KEY first (email/password tokens)
            try:
                payload = jwt.decode(token, settings.SECRET_KEY or 'your-secret-key-change-in-production', algorithms=["HS256"])
                user_id = payload.get('sub')  # For email/password, sub is user ID
                # Check for impersonation flag
                is_impersonation = payload.get('is_impersonation', False)
                if is_impersonation:
                    original_user_id = payload.get('original_user_id')
                    impersonation_session_id = payload.get('impersonation_session_id')
                print(f"✅ Email/password token decoded, user_id: {user_id}, impersonation: {is_impersonation}")
            except JWTError:
                # If verification fails, try unverified (Auth0 tokens)
                payload = jwt.get_unverified_claims(token)
                auth0_id = payload.get('sub')  # For Auth0, sub is auth0_id
                # Check for impersonation flag (shouldn't happen with Auth0 tokens, but check anyway)
                is_impersonation = payload.get('is_impersonation', False)
                if is_impersonation:
                    original_user_id = payload.get('original_user_id')
                    impersonation_session_id = payload.get('impersonation_session_id')
                print(f"✅ Auth0 token decoded, auth0_id: {auth0_id}, impersonation: {is_impersonation}")
            
            if not auth0_id and not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: missing 'sub' claim"
                )
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    
    # Method 2: Check for session-based authentication
    if not auth0_id and not user_id:
        user_session = request.session.get('user')
        
        if user_session:
            auth0_id = user_session.get('auth0_id')
    
    # If no authentication method worked
    if not auth0_id and not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # Handle impersonation
    if is_impersonation and user_id:
        # Verify impersonation session is still active
        if impersonation_session_id:
            try:
                from uuid import UUID
                session_uuid = UUID(impersonation_session_id) if isinstance(impersonation_session_id, str) else impersonation_session_id
                impersonation_session = db.query(ImpersonationSession).filter(
                    ImpersonationSession.id == session_uuid,
                    ImpersonationSession.status == 'active'
                ).first()
                
                if not impersonation_session:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Impersonation session has ended"
                    )
                
                # Store original user ID in request state for audit logging
                request.state.original_user_id = original_user_id
                request.state.impersonation_session_id = impersonation_session_id
            except (ValueError, TypeError) as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid impersonation session"
                )
        
        # Use impersonated user ID from token
        user = db.query(User).filter(User.id == user_id).first()
    else:
        # Get user from database normally
        # If we have user_id (email/password token), use that; otherwise use auth0_id
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
        else:
            user = db.query(User).filter(User.auth0_id == auth0_id).first()
    
    if not user:
        identifier = user_id if user_id else auth0_id
        print(f"❌ User not found in database for identifier: {identifier}")
        if request.session.get('user'):
            request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    impersonation_note = f" (impersonating as {user.email})" if is_impersonation else ""
    print(f" User authenticated: {user.email}, username/nickname: {user.nickname}, role: {user.role}{impersonation_note}")
    return user


def require_role(allowed_roles: List[UserRole]):
    """
    Dependency factory to require specific roles.
    
    Usage:
        @router.get("/admin-only")
        def admin_route(user: User = Depends(require_role([UserRole.ADMIN, UserRole.SUPER_ADMIN]))):
            ...
    """
    def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in allowed_roles]}"
            )
        return user
    
    return role_checker


def is_token_expired(token: dict) -> bool:
    """
    Check if Auth0 token is expired.
    
    Args:
        token: Token dictionary from Auth0
        
    Returns:
        bool: True if token is expired, False otherwise
    """
    try:
        # Get access token
        access_token = token.get('access_token')
        if not access_token:
            return True
        
        # Decode token WITHOUT verifying signature – we only need the `exp` claim.
        # python-jose requires a key for decode(), so we use get_unverified_claims instead.
        decoded = jwt.get_unverified_claims(access_token)
        
        # Check expiry
        exp = decoded.get('exp')
        if not exp:
            return True
        
        # Compare with current time
        current_time = datetime.utcnow().timestamp()
        return exp < current_time
        
    except (JWTError, KeyError, ValueError):
        return True


def get_token_expiry_time(token: dict) -> Optional[datetime]:
    """
    Get token expiry time.
    
    Args:
        token: Token dictionary from Auth0
        
    Returns:
        datetime: Expiry time or None if not found
    """
    try:
        access_token = token.get('access_token')
        if not access_token:
            return None
        
        # Decode token without verifying signature to read `exp` claim
        decoded = jwt.get_unverified_claims(access_token)
        
        exp = decoded.get('exp')
        if not exp:
            return None
        
        return datetime.utcfromtimestamp(exp)
        
    except (JWTError, KeyError, ValueError):
        return None


def get_original_user(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get the original superadmin user when impersonating.
    
    This function extracts the original user ID from the request state
    (set by get_current_user when impersonation is detected) and returns
    the original user object.
    
    Args:
        request: FastAPI request object
        db: Database session
        
    Returns:
        User: The original superadmin user, or None if not impersonating
    """
    original_user_id = getattr(request.state, 'original_user_id', None)
    if not original_user_id:
        return None
    
    try:
        from uuid import UUID
        user_uuid = UUID(original_user_id) if isinstance(original_user_id, str) else original_user_id
        return db.query(User).filter(User.id == user_uuid).first()
    except (ValueError, TypeError):
        return None


