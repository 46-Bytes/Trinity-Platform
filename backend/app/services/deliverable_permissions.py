"""
Access control for the Value Builder deliverables API.

    ┌─── PENDING BBA CONFIRMATION ──────────────────────────────────────────┐

    The spec says business owners get a dashboard only - they cannot open
    modules or mutate anything - while advisors and admins have full access.
    That has NOT been finally confirmed with BBA.

    EVERY access decision for the deliverables API is made in this file. No
    endpoint in app/api/program_deliverable.py contains a role check. If the
    rule changes, it changes here and nowhere else.

    What "owner" means in practice: the write guard denies UserRole.CLIENT,
    which is ALL clients, not only self-service owners. Per migration
    f7a1b2c3d4e5, a true self-service owner is CLIENT *and*
    users.account_type == 'self_service', while an advisor-provisioned client
    is CLIENT + 'advisory'. account_type exists in the database but is not on
    the User model on this branch, so the two cannot be told apart in code.

    That is correct for the rule as written, because neither kind of client is
    an advisor. It only becomes wrong if BBA wants advisory clients treated
    differently from owners - and adding account_type to the User model is the
    prerequisite for expressing that.

    └───────────────────────────────────────────────────────────────────────┘
"""
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.engagement import Engagement
from app.models.user import User, UserRole
from app.services.role_check import check_engagement_access
from app.utils.auth import get_current_user

# The program this API serves. Non-matching engagements are rejected, mirroring
# app/api/program_guide.py.
DELIVERABLE_PROGRAM_TYPE = "value_builder"

# The effective write allow-list. This is documentation plus the set the
# boundary tests assert against - enforcement goes through
# check_engagement_access(require_advisor=True), which yields exactly this set.
#
# That flag is easy to misread: it is tested in one place only (role_check.py,
# inside the CLIENT branch), so it means "is not a client" rather than "is an
# advisor" - admins, super admins and firm admins return True before it is ever
# read. Using it keeps one mechanism rather than two that must agree.
DELIVERABLE_MUTATE_ROLES = frozenset({
    UserRole.ADVISOR,
    UserRole.FIRM_ADVISOR,
    UserRole.FIRM_ADMIN,
    UserRole.ADMIN,
    UserRole.SUPER_ADMIN,
})


def _load_engagement(engagement_id: UUID, db: Session) -> Engagement:
    engagement = db.query(Engagement).filter(
        Engagement.id == engagement_id,
        Engagement.is_deleted == False,  # noqa: E712
    ).first()
    if not engagement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engagement not found")
    return engagement


def _authorize(engagement: Engagement, current_user: User, db: Session, require_advisor: bool) -> Engagement:
    if not check_engagement_access(engagement, current_user, require_advisor=require_advisor, db=db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this engagement",
        )
    if engagement.tool != DELIVERABLE_PROGRAM_TYPE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deliverables are only available for Value Builder engagements",
        )
    return engagement


def require_deliverable_read(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Engagement:
    """
    Read access: any role with access to the engagement, owners included.

    Returns the loaded engagement so endpoints do not refetch it.
    """
    engagement = _load_engagement(engagement_id, db)
    return _authorize(engagement, current_user, db, require_advisor=False)


def require_deliverable_write(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Engagement:
    """
    Mutate access: advisors and admins only - see DELIVERABLE_MUTATE_ROLES.

    Returns the loaded engagement so endpoints do not refetch it.
    """
    engagement = _load_engagement(engagement_id, db)
    return _authorize(engagement, current_user, db, require_advisor=True)
