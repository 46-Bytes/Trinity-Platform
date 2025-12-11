"""
Authentication and authorization utilities.
"""
from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.orm import Session
from jose import jwt

from ..database import get_db
from ..models.user import User, UserRole


def get_current_user_from_token(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """
    Get current user from JWT token in Authorization header.
    Compatible with frontend token-based authentication.
    
    Args:
        request: FastAPI request object
        db: Database session
        
    Returns:
        User: The authenticated user
        
    Raises:
        HTTPException: If authentication fails
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Missing or invalid Authorization header."
        )
    
    token = auth_header.split(" ")[1]
    
    try:
        # Decode token to get user info
        payload = jwt.get_unverified_claims(token)
        auth0_id = payload.get("sub")
        
        if not auth0_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token. Missing 'sub' claim."
            )
        
        # Find user in database
        user = db.query(User).filter(User.auth0_id == auth0_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found."
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive."
            )
        
        return user
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {str(e)}"
        )


def check_engagement_access(
    engagement,
    user: User,
    require_advisor: bool = False
) -> bool:
    """
    Check if user has access to an engagement.
    
    Rules:
    - Super Admin: Access to all
    - Admin: Access to all
    - Advisor: Access if they are primary_advisor_id or in secondary_advisor_ids
    - Client: Access if they are client_id
    
    Args:
        engagement: Engagement to check
        user: Current user
        require_advisor: If True, only advisors can access
        
    Returns:
        bool: True if user has access
    """
    # Super Admin and Admin have full access
    if user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        return True
    
    # Advisor access
    if user.role == UserRole.ADVISOR:
        if engagement.primary_advisor_id == user.id:
            return True
        if engagement.secondary_advisor_ids and user.id in engagement.secondary_advisor_ids:
            return True
        return False
    
    # Client access
    if user.role == UserRole.CLIENT:
        if require_advisor:
            return False
        return engagement.client_id == user.id
    
    return False