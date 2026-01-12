"""
Service for checking if a user should be allowed to login.
Reusable logic for checking firm revocation and user suspension.
"""
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, Tuple
from ..models.user import User, UserRole
from ..models.firm import Firm


def check_user_login_eligibility(
    db: Session,
    user: User
) -> Tuple[bool, Optional[str]]:
    """
    Check if a user is eligible to login.
    
    This function checks:
    1. If user's firm is revoked (for firm_admin, firm_advisor, and clients)
    2. If user is suspended (for firm_advisor and firm_admin roles)
    3. If client is in a revoked firm's clients array
    
    Args:
        db: Database session
        user: User object to check
        
    Returns:
        Tuple[bool, Optional[str]]: 
            - (True, None) if user can login
            - (False, error_message) if user cannot login
    """
    # Check if user account is suspended (for firm_advisor and firm_admin)
    if user.role in [UserRole.FIRM_ADVISOR, UserRole.FIRM_ADMIN]:
        if not user.is_active:
            return False, "Your account has been suspended. Please contact your firm administrator."
    
    # Check if user's firm is revoked (for firm_admin, firm_advisor, and clients with firm_id)
    if user.firm_id:
        firm = db.query(Firm).filter(Firm.id == user.firm_id).first()
        if firm and not firm.is_active:
            return False, "firm_revoked"
    
    # Check if client is in any firm's clients array (even if they don't have firm_id)
    if user.role == UserRole.CLIENT:
        # Query all firms to check if this client is in any firm's clients array
        firms_with_client = db.query(Firm).filter(
            text("clients @> ARRAY[:user_id]::uuid[]").bindparams(user_id=user.id)
        ).all()
        for firm in firms_with_client:
            if not firm.is_active:
                return False, "firm_revoked"
    
    # User is eligible to login
    return True, None

