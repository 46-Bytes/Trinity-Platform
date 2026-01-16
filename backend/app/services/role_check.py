"""
Authentication and authorization utilities.
"""
from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from ..database import get_db
from ..models.user import User, UserRole
from ..models.impersonation import ImpersonationSession
from ..config import settings


def get_current_user_from_token(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """
    Get current user from JWT token in Authorization header.
    Compatible with frontend token-based authentication.
    Also handles impersonation tokens.
    
    Args:
        request: FastAPI request object
        db: Database session
        
    Returns:
        User: The authenticated user (or impersonated user if impersonating)
        
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
        user_id = None
        auth0_id = None
        is_impersonation = False
        original_user_id = None
        impersonation_session_id = None
        
        # Try to decode with SECRET_KEY first (for email/password and impersonation tokens)
        try:
            payload = jwt.decode(token, settings.SECRET_KEY or 'your-secret-key-change-in-production', algorithms=["HS256"])
            user_id = payload.get("sub")  # For email/password and impersonation tokens, sub is user ID
            is_impersonation = payload.get('is_impersonation', False)
            if is_impersonation:
                original_user_id = payload.get('original_user_id')
                impersonation_session_id = payload.get('impersonation_session_id')
        except JWTError:
            # If verification fails, try unverified (Auth0 tokens)
            payload = jwt.get_unverified_claims(token)
            auth0_id = payload.get("sub")  # For Auth0 tokens, sub is auth0_id
            # Check for impersonation flag (shouldn't happen with Auth0 tokens, but check anyway)
            is_impersonation = payload.get('is_impersonation', False)
            if is_impersonation:
                original_user_id = payload.get('original_user_id')
                impersonation_session_id = payload.get('impersonation_session_id')
        
        if not auth0_id and not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token. Missing 'sub' claim."
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
            # Normal authentication - find user by auth0_id or user_id
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
            else:
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
    - Firm Admin: Access to all engagements in their firm
    - Advisor: Access if they are primary_advisor_id or in secondary_advisor_ids
    - Firm Advisor: Access if they are primary_advisor_id or in secondary_advisor_ids
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
    
    # Firm Admin access - can access all engagements in their firm
    if user.role == UserRole.FIRM_ADMIN:
        if user.firm_id and engagement.firm_id == user.firm_id:
            return True
        return False
    
    # Advisor access
    if user.role == UserRole.ADVISOR:
        if engagement.primary_advisor_id == user.id:
            return True
        if engagement.secondary_advisor_ids and user.id in engagement.secondary_advisor_ids:
            return True
        return False
    
    # Firm Advisor access
    if user.role == UserRole.FIRM_ADVISOR:
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