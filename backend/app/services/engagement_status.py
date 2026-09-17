"""
Engagement lifecycle status: the vocabulary, who may change it, and which
statuses hide an engagement's tasks from the aggregate Tasks views.

Everything the lifecycle feature needs to decide lives here so the rules can be
adjusted in one place. `engagements.status` is a plain VARCHAR(50) with no
CHECK constraint, so adding or renaming a value below needs no migration.
"""
from typing import Optional

from sqlalchemy.orm import Session

from ..models.engagement import Engagement
from ..models.user import User, UserRole

# ---------------------------------------------------------------------------
# Status vocabulary
# ---------------------------------------------------------------------------

# Pre-existing values kept for backward compatibility: 'draft' comes from the
# create form, 'completed' from the diagnostic pipeline.
STATUS_DRAFT = "draft"
STATUS_ACTIVE = "active"
STATUS_PAUSED = "paused"
STATUS_ENDED = "ended"
STATUS_COMPLETED = "completed"
STATUS_ARCHIVED = "archived"

# The only values the lifecycle endpoint accepts. Recommence is not a status of
# its own - it is a transition back to ACTIVE.
SETTABLE_STATUSES = (STATUS_ACTIVE, STATUS_PAUSED, STATUS_ENDED)

# Statuses that take an engagement out of day-to-day work. Its tasks are hidden
# from the aggregate Tasks views and excluded from dashboard task counts while
# it sits in one of these; nothing is deleted, so recommencing restores them.
TASK_HIDDEN_STATUSES = frozenset({STATUS_PAUSED, STATUS_ENDED})

# Statuses the automated diagnostic flows are allowed to overwrite. A paused or
# ended engagement is a deliberate choice by an advisor, so submitting a
# diagnostic must not quietly drag it back to active/completed.
AUTOMATION_MAY_OVERWRITE_STATUSES = frozenset(
    {STATUS_DRAFT, STATUS_ACTIVE, STATUS_COMPLETED, STATUS_ARCHIVED}
)


# ---------------------------------------------------------------------------
# Who may pause / end / recommence
# ---------------------------------------------------------------------------

# Pending client confirmation. To widen or narrow the permission, edit these two
# sets - no other backend file needs to change.

# Roles that may change status on any engagement they can already see.
STATUS_CHANGE_ROLES_ANY_ENGAGEMENT = frozenset({UserRole.ADMIN, UserRole.SUPER_ADMIN})

# Roles that may change status only on engagements they are assigned to, as
# primary or secondary advisor.
STATUS_CHANGE_ROLES_IF_ASSIGNED = frozenset({UserRole.ADVISOR, UserRole.FIRM_ADVISOR})


def is_assigned_advisor(engagement: Engagement, user: User) -> bool:
    """True when the user is the primary or a secondary advisor on the engagement."""
    if engagement.primary_advisor_id == user.id:
        return True
    if engagement.secondary_advisor_ids and user.id in engagement.secondary_advisor_ids:
        return True
    return False


def can_change_engagement_status(engagement: Engagement, user: User) -> bool:
    """
    Whether this user may pause, end or recommence this engagement.

    Deliberately narrower than `check_engagement_access(require_advisor=True)`,
    which also grants an advisor merely associated with the client. Changing the
    lifecycle requires being assigned to the engagement itself.
    """
    if user.role in STATUS_CHANGE_ROLES_ANY_ENGAGEMENT:
        return True
    if user.role in STATUS_CHANGE_ROLES_IF_ASSIGNED:
        return is_assigned_advisor(engagement, user)
    return False


# ---------------------------------------------------------------------------
# Task visibility
# ---------------------------------------------------------------------------
def hidden_task_engagement_ids(db: Session) -> list:
    """
    Ids of engagements whose tasks are currently hidden from aggregate views.

    Returned as a list of ids rather than a subquery so callers can use it with
    either a SQLAlchemy filter or a plain Python list of engagement ids.
    """
    rows = (
        db.query(Engagement.id)
        .filter(Engagement.status.in_(TASK_HIDDEN_STATUSES))
        .all()
    )
    return [row[0] for row in rows]


def may_automation_set_status(engagement: Optional[Engagement]) -> bool:
    """
    Whether an automated flow (diagnostic submission) may write engagement.status.

    Returns False for paused/ended so an advisor's lifecycle decision survives a
    diagnostic being filled in or completed.
    """
    if engagement is None:
        return False
    return engagement.status in AUTOMATION_MAY_OVERWRITE_STATUSES
