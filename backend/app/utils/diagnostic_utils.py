"""
Utility functions for diagnostic operations.
"""
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.diagnostic import Diagnostic
from app.schemas.diagnostic import DiagnosticResponse, DiagnosticDetail


def get_admin_role_if_applicable(db: Session, user_id: UUID) -> Optional[str]:
    """
    Get the role of a user if they are an admin/firm_admin/super_admin.
    
    Args:
        db: Database session
        user_id: UUID of the user
        
    Returns:
        Role string (lowercase: 'admin', 'firm_admin', 'super_admin') if user is an admin role, None otherwise
    """
    if not user_id:
        return None
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    
    # Check if user has an admin role
    if user.role in [UserRole.ADMIN, UserRole.FIRM_ADMIN, UserRole.SUPER_ADMIN]:
        # Return normalized role value (lowercase)
        role_value = user.role.value if hasattr(user.role, 'value') else str(user.role)
        return role_value.lower()
    
    return None


def enrich_diagnostic_with_roles(db: Session, diagnostic: Diagnostic, use_detail_schema: bool = False) -> dict:
    """
    Enrich diagnostic response with role information for admin users.
    
    Args:
        db: Database session
        diagnostic: Diagnostic model instance
        use_detail_schema: If True, use DiagnosticDetail schema, otherwise use DiagnosticResponse
        
    Returns:
        Dictionary with diagnostic data and role fields added
    """
    # Get role for completed_by_user_id (preferred) or created_by_user_id (fallback)
    completed_by_role = None
    created_by_role = None
    
    if diagnostic.completed_by_user_id:
        completed_by_role = get_admin_role_if_applicable(db, diagnostic.completed_by_user_id)
    
    if diagnostic.created_by_user_id:
        created_by_role = get_admin_role_if_applicable(db, diagnostic.created_by_user_id)
    
    # Convert diagnostic to Pydantic model first, then to dict and add role fields
    # Use model_validate to convert SQLAlchemy model to Pydantic model
    if use_detail_schema:
        diagnostic_response = DiagnosticDetail.model_validate(diagnostic)
    else:
        diagnostic_response = DiagnosticResponse.model_validate(diagnostic)
    diagnostic_dict = diagnostic_response.model_dump()
    
    # Add role fields
    diagnostic_dict['created_by_user_role'] = created_by_role
    diagnostic_dict['completed_by_user_role'] = completed_by_role
    
    return diagnostic_dict

