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
    
    Supports two authentication methods:
    1. Bearer token (Authorization header) - for API clients like Postman
    2. Session-based (cookies) - for web frontend
    
    Priority: Bearer token is checked first, then session.
    
    Raises:
        HTTPException: If user is not authenticated
    """
    auth0_id = None
    user_id = None  # For email/password tokens
    
    # Method 1: Check for Bearer token in Authorization header
    auth_header = request.headers.get('Authorization')
    user_id = None  # For email/password tokens
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        print(f"🔑 Bearer token found, length: {len(token)}")
        
        try:
            # Decode the token to get user info
            # Try to verify with SECRET_KEY first (email/password tokens)
            try:
                payload = jwt.decode(token, settings.SECRET_KEY or 'your-secret-key-change-in-production', algorithms=["HS256"])
                user_id = payload.get('sub')  # For email/password, sub is user ID
                print(f"✅ Email/password token decoded, user_id: {user_id}")
            except JWTError:
                # If verification fails, try unverified (Auth0 tokens)
                payload = jwt.get_unverified_claims(token)
                auth0_id = payload.get('sub')  # For Auth0, sub is auth0_id
                print(f"✅ Auth0 token decoded, auth0_id: {auth0_id}")
            
            if not auth0_id and not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: missing 'sub' claim"
                )
        except JWTError as e:
            print(f"❌ Token decode error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    
    # Method 2: Check for session-based authentication
    if not auth0_id:
        user_session = request.session.get('user')
        print(f"🍪 Session check - keys: {list(request.session.keys())}")
        print(f"🍪 User session exists: {user_session is not None}")
        
        if user_session:
            auth0_id = user_session.get('auth0_id')
            print(f"✅ Session auth0_id: {auth0_id}")
    
    # If no authentication method worked
    if not auth0_id:
        print("❌ No valid authentication found (neither Bearer token nor session)")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # Get user from database
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
        print(f"❌ User account inactive: {user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    print(f"✅ User authenticated: {user.email}, role: {user.role}")
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


