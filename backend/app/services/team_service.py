"""
Team member management for the self-service (SaaS) tier.

A business owner can invite team members to collaborate on their program.
Invitation reuses the same Auth0 machinery firms use for advisors
(Auth0Management.create_user -> password setup email via Resend), and members
are appended to the owner's engagement `client_ids` so every existing
engagement-scoped access check applies to them unchanged.
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from ..models.engagement import Engagement
from ..models.owner_team_member import (
    DEFAULT_ACCESS_LEVEL,
    OwnerTeamMember,
    TeamAccessLevel,
    TeamMemberStatus,
)
from ..models.user import AccountType, User, UserRole
from .auth0_management import Auth0Management
from .self_service import get_active_subscription, get_owner_engagement

logger = logging.getLogger(__name__)


class TeamError(Exception):
    """Raised when a team operation cannot be completed."""


def count_active_members(db: Session, owner_id: UUID) -> int:
    """How many seats the owner's team currently occupies (revoked members freed)."""
    return (
        db.query(OwnerTeamMember)
        .filter(
            OwnerTeamMember.owner_user_id == owner_id,
            OwnerTeamMember.status != TeamMemberStatus.REVOKED.value,
        )
        .count()
    )


def list_members(db: Session, owner_id: UUID) -> List[dict]:
    """The owner's team, newest first, with each member's user details attached."""
    rows = (
        db.query(OwnerTeamMember, User)
        .join(User, User.id == OwnerTeamMember.member_user_id)
        .filter(
            OwnerTeamMember.owner_user_id == owner_id,
            OwnerTeamMember.status != TeamMemberStatus.REVOKED.value,
        )
        .order_by(OwnerTeamMember.invited_at.desc())
        .all()
    )

    members = []
    for membership, user in rows:
        members.append({
            **membership.to_dict(),
            "email": user.email,
            "name": user.name,
            "is_active": user.is_active,
            "email_verified": user.email_verified,
        })
    return members


def get_membership(db: Session, owner_id: UUID, member_id: UUID) -> Optional[OwnerTeamMember]:
    """A single membership row, or None."""
    return (
        db.query(OwnerTeamMember)
        .filter(
            OwnerTeamMember.owner_user_id == owner_id,
            OwnerTeamMember.id == member_id,
        )
        .first()
    )


def get_membership_for_user(db: Session, member_user_id: UUID) -> Optional[OwnerTeamMember]:
    """The active membership a team member belongs to, if any."""
    return (
        db.query(OwnerTeamMember)
        .filter(
            OwnerTeamMember.member_user_id == member_user_id,
            OwnerTeamMember.status != TeamMemberStatus.REVOKED.value,
        )
        .first()
    )


def invite_team_member(
    db: Session,
    owner: User,
    email: str,
    name: Optional[str] = None,
    access_level: str = DEFAULT_ACCESS_LEVEL.value,
) -> OwnerTeamMember:
    """
    Invite a team member to the owner's workspace.

    Creates the Auth0 account (which sends the password setup email), the local
    user with role TEAM_MEMBER, the membership row, and adds the member to the
    owner's engagement.

    Raises:
        TeamError: on a bad access level, an exhausted seat cap, a duplicate
            email, or an Auth0 failure.
    """
    if access_level not in {level.value for level in TeamAccessLevel}:
        raise TeamError(
            f"Invalid access level '{access_level}'. "
            f"Must be one of {sorted(level.value for level in TeamAccessLevel)}."
        )

    subscription = get_active_subscription(db, owner.id)
    if not subscription:
        raise TeamError("An active subscription is required to invite team members.")

    # The owner occupies one seat; the rest are invitable.
    member_limit = max(subscription.seat_count - 1, 0)
    if count_active_members(db, owner.id) >= member_limit:
        raise TeamError(
            f"You have used all {member_limit} team member seats on your plan. "
            "Remove a member or upgrade your plan to invite more."
        )

    normalized_email = email.strip().lower()
    if normalized_email == owner.email.strip().lower():
        raise TeamError("You cannot invite yourself.")

    existing_user = db.query(User).filter(
        User.email == normalized_email,
        User.is_deleted == False,  # noqa: E712
    ).first()
    if existing_user:
        raise TeamError(
            f"An account already exists for {normalized_email}. Please use a different email."
        )

    first_name = None
    last_name = None
    if name:
        parts = name.strip().split(" ", 1)
        first_name = parts[0]
        if len(parts) > 1:
            last_name = parts[1]

    try:
        auth0_user = Auth0Management.create_user(
            email=normalized_email,
            role=UserRole.TEAM_MEMBER.value,
            first_name=first_name,
            last_name=last_name,
        )
        auth0_id = auth0_user["user_id"]
    except Exception as exc:
        logger.error("Failed to create team member %s in Auth0: %s", normalized_email, exc)
        raise TeamError(f"Could not create the team member account: {exc}") from exc

    member = User(
        auth0_id=auth0_id,
        email=normalized_email,
        name=name or normalized_email,
        first_name=first_name,
        last_name=last_name,
        role=UserRole.TEAM_MEMBER,
        account_type=AccountType.SELF_SERVICE.value,
        business_name=owner.business_name,
        firm_id=None,
        is_active=True,
        email_verified=False,
    )
    db.add(member)
    db.flush()

    membership = OwnerTeamMember(
        owner_user_id=owner.id,
        member_user_id=member.id,
        access_level=access_level,
        status=TeamMemberStatus.INVITED.value,
    )
    db.add(membership)

    _add_member_to_engagements(db, owner.id, member.id)

    db.commit()
    db.refresh(membership)

    logger.info("Owner %s invited team member %s (access=%s)", owner.email, normalized_email, access_level)
    return membership


def update_access_level(db: Session, owner: User, member_id: UUID, access_level: str) -> OwnerTeamMember:
    """
    Change a member's access level.

    Raises:
        TeamError: on a bad access level or an unknown membership.
    """
    if access_level not in {level.value for level in TeamAccessLevel}:
        raise TeamError(
            f"Invalid access level '{access_level}'. "
            f"Must be one of {sorted(level.value for level in TeamAccessLevel)}."
        )

    membership = get_membership(db, owner.id, member_id)
    if not membership or membership.status == TeamMemberStatus.REVOKED.value:
        raise TeamError("Team member not found.")

    membership.access_level = access_level
    db.commit()
    db.refresh(membership)
    return membership


def revoke_member(db: Session, owner: User, member_id: UUID) -> None:
    """
    Remove a team member: frees the seat, deactivates the login and takes them
    off the owner's engagements.

    Raises:
        TeamError: if the membership does not exist.
    """
    membership = get_membership(db, owner.id, member_id)
    if not membership or membership.status == TeamMemberStatus.REVOKED.value:
        raise TeamError("Team member not found.")

    membership.status = TeamMemberStatus.REVOKED.value
    membership.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    member = db.query(User).filter(User.id == membership.member_user_id).first()
    if member:
        member.is_active = False

    _remove_member_from_engagements(db, owner.id, membership.member_user_id)

    db.commit()
    logger.info("Owner %s revoked team member %s", owner.email, membership.member_user_id)


def mark_member_active(db: Session, member: User) -> None:
    """Flip a membership from 'invited' to 'active' on the member's first login."""
    membership = get_membership_for_user(db, member.id)
    if membership and membership.status == TeamMemberStatus.INVITED.value:
        membership.status = TeamMemberStatus.ACTIVE.value
        membership.accepted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()


# ----------------------------------------------------------------------------
# Engagement membership
# ----------------------------------------------------------------------------

def _owner_engagements(db: Session, owner_id: UUID) -> List[Engagement]:
    return (
        db.query(Engagement)
        .filter(
            Engagement.client_id == owner_id,
            Engagement.is_deleted == False,  # noqa: E712
        )
        .all()
    )


def _add_member_to_engagements(db: Session, owner_id: UUID, member_id: UUID) -> None:
    """
    Add the member to every engagement the owner owns.

    This is what grants access - check_engagement_access already honours
    `client_ids`, so no new permission code is needed for the member to reach
    tasks, documents and the program.
    """
    for engagement in _owner_engagements(db, owner_id):
        client_ids = list(engagement.client_ids or [])
        if member_id not in client_ids:
            client_ids.append(member_id)
            engagement.client_ids = client_ids
            flag_modified(engagement, "client_ids")


def _remove_member_from_engagements(db: Session, owner_id: UUID, member_id: UUID) -> None:
    """Take a revoked member off the owner's engagements."""
    for engagement in _owner_engagements(db, owner_id):
        client_ids = list(engagement.client_ids or [])
        if member_id in client_ids:
            client_ids.remove(member_id)
            engagement.client_ids = client_ids
            flag_modified(engagement, "client_ids")


def sync_team_to_engagement(db: Session, owner_id: UUID, engagement: Engagement) -> None:
    """
    Add the owner's whole team to a newly provisioned engagement.

    Called after provisioning so members invited before an engagement existed
    (or before an upsell created a second one) still get access.
    """
    member_ids = [
        row.member_user_id
        for row in db.query(OwnerTeamMember).filter(
            OwnerTeamMember.owner_user_id == owner_id,
            OwnerTeamMember.status != TeamMemberStatus.REVOKED.value,
        )
    ]
    if not member_ids:
        return

    client_ids = list(engagement.client_ids or [])
    changed = False
    for member_id in member_ids:
        if member_id not in client_ids:
            client_ids.append(member_id)
            changed = True

    if changed:
        engagement.client_ids = client_ids
        flag_modified(engagement, "client_ids")
        db.commit()
