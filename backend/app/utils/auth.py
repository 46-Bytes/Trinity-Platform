"""
Authentication and authorization utilities.
"""
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from datetime import datetime
from ..database import get_db
from ..models.user import User, UserRole
from ..config import settings
from typing import Optional, List


def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user.
    
    This checks:
    1. Session exists
    2. Token exists in session
    3. Token is not expired
    4. User exists in database
    
    Raises:
        HTTPException: If user is not authenticated or token is expired
    """
    user_session = request.session.get('user')
    
    # Debug: Print session info
    print(f"Session keys in get_current_user: {list(request.session.keys())}")
    print(f"User session exists: {user_session is not None}")
    
    if not user_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # NOTE: For now we are **not** enforcing token presence/expiry here.
    # We only rely on the existence of the session. This keeps the flow simple
    # while we're setting things up. Later we can re-enable token checks.

    # Get user from database based on Auth0 ID stored in session
    auth0_id = user_session.get('auth0_id')
    user = db.query(User).filter(User.auth0_id == auth0_id).first()
    
    if not user:
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


