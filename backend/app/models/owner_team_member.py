"""
Team membership model for the self-service (SaaS) tier.

A self-service business owner (a CLIENT with account_type='self_service') can
invite team members to collaborate on their program. This table is the
owner -> member association plus the member's access level.

Members are ALSO appended to `engagements.client_ids` on invite, so every
existing engagement-scoped check (diagnostics, tasks, notes, files, BBA,
workbook, SBP) keeps working without modification.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import enum

from ..database import Base


class TeamAccessLevel(str, enum.Enum):
    """What an invited team member is allowed to do."""
    # View and complete tasks assigned to them, view and upload shared
    # documents, read the dashboard.
    COLLABORATOR = "collaborator"
    # Read-only on assigned tasks and shared documents, read the dashboard.
    VIEWER = "viewer"


class TeamMemberStatus(str, enum.Enum):
    """Lifecycle of an invitation."""
    INVITED = "invited"   # Auth0 account created, password not set yet
    ACTIVE = "active"     # member has logged in at least once
    REVOKED = "revoked"   # owner removed them; seat is freed


# The access level a newly invited member receives before the owner adjusts it.
# Least privilege by default - the owner upgrades deliberately.
DEFAULT_ACCESS_LEVEL = TeamAccessLevel.VIEWER


class OwnerTeamMember(Base):
    """Association between a self-service business owner and an invited team member."""
    __tablename__ = "owner_team_members"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
        comment="Unique identifier for the membership",
    )
    owner_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key to users (the self-service business owner)",
    )
    member_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key to users (the invited team member)",
    )
    access_level = Column(
        String(20),
        nullable=False,
        server_default=DEFAULT_ACCESS_LEVEL.value,
        comment="Access level: collaborator or viewer",
    )
    status = Column(
        String(20),
        nullable=False,
        server_default=TeamMemberStatus.INVITED.value,
        index=True,
        comment="Membership status: invited, active, revoked",
    )
    invited_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    accepted_at = Column(DateTime, nullable=True, comment="When the member first logged in")
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    __table_args__ = (
        UniqueConstraint("owner_user_id", "member_user_id", name="uq_owner_team_member"),
    )

    owner = relationship("User", foreign_keys=[owner_user_id], backref="team_members")
    member = relationship("User", foreign_keys=[member_user_id], backref="team_memberships")

    def __repr__(self):
        return (
            f"<OwnerTeamMember(owner={self.owner_user_id}, member={self.member_user_id}, "
            f"access={self.access_level}, status={self.status})>"
        )

    def to_dict(self):
        """Convert membership to a dictionary."""
        return {
            "id": str(self.id),
            "owner_user_id": str(self.owner_user_id),
            "member_user_id": str(self.member_user_id),
            "access_level": self.access_level,
            "status": self.status,
            "invited_at": self.invited_at.isoformat() if self.invited_at else None,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
        }
