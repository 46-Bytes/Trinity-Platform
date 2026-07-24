"""
Authorization utilities for engagement and role-based access control.
"""
from sqlalchemy.orm import Session

from ..models.user import User, UserRole
from ..models.adv_client import AdvisorClient


def check_engagement_access(
    engagement,
    user: User,
    require_advisor: bool = False,
    db: Session | None = None,
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

        # If we have a DB session, also allow access when the advisor is
        # actively associated with the client via AdvisorClient. This ensures
        if db is not None and engagement.client_id is not None:
            association_exists = (
                db.query(AdvisorClient)
                .filter(
                    AdvisorClient.advisor_id == user.id,
                    AdvisorClient.client_id == engagement.client_id,
                    AdvisorClient.status == "active",
                    AdvisorClient.is_deleted == False,
                )
                .first()
                is not None
            )
            if association_exists:
                return True

        return False

    # Firm Advisor access
    if user.role == UserRole.FIRM_ADVISOR:
        if engagement.primary_advisor_id == user.id:
            return True
        if engagement.secondary_advisor_ids and user.id in engagement.secondary_advisor_ids:
            return True

        if db is not None and engagement.client_id is not None:
            association_exists = (
                db.query(AdvisorClient)
                .filter(
                    AdvisorClient.advisor_id == user.id,
                    AdvisorClient.client_id == engagement.client_id,
                    AdvisorClient.status == "active",
                    AdvisorClient.is_deleted == False,
                )
                .first()
                is not None
            )
            if association_exists:
                return True

        return False
    
    # Client access
    # Covers both advisor-provisioned clients and self-service business owners -
    # a self-service owner IS a CLIENT (distinguished only by User.account_type),
    # and owns their engagement via client_id, so no extra branch is needed here.
    if user.role == UserRole.CLIENT:
        if require_advisor:
            return False
        # Support multi-client engagements via `client_ids` array.

        if engagement.client_id == user.id:
            return True
        if engagement.client_ids and user.id in engagement.client_ids:
            return True
        return False

    # Team member access (self-service tier)
    # Membership in `client_ids` is granted by team_service on invite and removed
    # on revoke, but we re-check the membership row so a revoked member who is
    # still lingering in a stale client_ids array cannot get back in.
    if user.role == UserRole.TEAM_MEMBER:
        if require_advisor:
            return False
        if not (engagement.client_ids and user.id in engagement.client_ids):
            return False
        if db is None:
            # Without a session we cannot confirm the membership is live; the
            # engagement-level check above already passed, so allow it.
            return True

        from ..models.owner_team_member import OwnerTeamMember, TeamMemberStatus

        return (
            db.query(OwnerTeamMember)
            .filter(
                OwnerTeamMember.member_user_id == user.id,
                OwnerTeamMember.status != TeamMemberStatus.REVOKED.value,
            )
            .first()
            is not None
        )

    return False