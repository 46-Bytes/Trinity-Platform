"""
Firm-specific permission checks.
"""
from sqlalchemy.orm import Session
from ..models.user import User, UserRole
from ..models.firm import Firm
from uuid import UUID


def is_firm_admin(user: User) -> bool:
    """Check if user is a Firm Admin."""
    return user.role == UserRole.FIRM_ADMIN


def is_firm_advisor(user: User) -> bool:
    """Check if user is a Firm Advisor."""
    return user.role == UserRole.FIRM_ADVISOR


def is_firm_member(user: User) -> bool:
    """Check if user belongs to a firm."""
    return user.role in [UserRole.FIRM_ADMIN, UserRole.FIRM_ADVISOR] and user.firm_id is not None


def can_manage_firm_users(user: User, firm_id: UUID) -> bool:
    """Check if user can manage users in a firm."""
    if user.role == UserRole.SUPER_ADMIN:
        return True
    if is_firm_admin(user) and user.firm_id == firm_id:
        return True
    return False


def can_view_firm_engagements(user: User, firm_id: UUID) -> bool:
    """Check if user can view all engagements in a firm."""
    if user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        return True
    if is_firm_admin(user) and user.firm_id == firm_id:
        return True
    return False


def can_assign_advisors(user: User, firm_id: UUID) -> bool:
    """Check if user can assign advisors to engagements."""
    if user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        return True
    if is_firm_admin(user) and user.firm_id == firm_id:
        return True
    return False


def can_modify_subscription(user: User, firm_id: UUID) -> bool:
    """Check if user can modify firm subscription/billing."""
    if user.role == UserRole.SUPER_ADMIN:
        return True
    if is_firm_admin(user) and user.firm_id == firm_id:
        return True
    return False


