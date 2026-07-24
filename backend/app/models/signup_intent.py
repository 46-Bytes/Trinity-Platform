"""
Signup intent model for the self-service (SaaS) funnel.

Auth0 Universal Login owns the credential step, so the business details the
owner types on /signup (name, business name, chosen program) cannot travel
through Auth0. They are parked here first, then matched back by email on
/api/auth/callback so the new user is created as a self-service CLIENT with the
right business name and program - instead of falling through to the ADVISOR
default in AuthService.get_or_create_user.
"""
from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timedelta, timezone
import uuid
import enum

from ..database import Base


class SignupIntentStatus(str, enum.Enum):
    """Lifecycle of a signup intent."""
    PENDING = "pending"    # created, waiting for the Auth0 round trip
    CONSUMED = "consumed"  # matched on callback and applied to a user
    EXPIRED = "expired"    # timed out before the user came back


# How long an intent stays valid. Long enough for a slow Auth0 signup
# (including email verification), short enough that a stale intent cannot be
# replayed against a later signup with the same address.
INTENT_TTL = timedelta(hours=24)


class SignupIntent(Base):
    """A pending self-service signup, created before the Auth0 redirect."""
    __tablename__ = "signup_intents"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
        comment="Unique identifier for the signup intent",
    )
    email = Column(
        String(255),
        nullable=False,
        index=True,
        comment="Email the owner signed up with; matched against the Auth0 profile on callback",
    )
    name = Column(String(255), nullable=True, comment="Owner's full name")
    business_name = Column(String(255), nullable=True, comment="Owner's business name")
    program = Column(
        String(50),
        nullable=False,
        comment="Selected program: value_builder or sale_ready (becomes Engagement.tool)",
    )
    plan_name = Column(String(50), nullable=True, comment="Selected plan from the billing catalogue")
    status = Column(
        String(20),
        nullable=False,
        server_default=SignupIntentStatus.PENDING.value,
        index=True,
        comment="Intent status: pending, consumed, expired",
    )
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    expires_at = Column(DateTime, nullable=False, comment="When this intent stops being valid")
    consumed_at = Column(DateTime, nullable=True)

    @staticmethod
    def default_expiry() -> datetime:
        """Expiry timestamp for a newly created intent."""
        return datetime.now(timezone.utc).replace(tzinfo=None) + INTENT_TTL

    @property
    def is_usable(self) -> bool:
        """True if this intent can still be applied to a signing-up user."""
        if self.status != SignupIntentStatus.PENDING.value:
            return False
        return self.expires_at > datetime.now(timezone.utc).replace(tzinfo=None)

    def __repr__(self):
        return f"<SignupIntent(email={self.email}, program={self.program}, status={self.status})>"

    def to_dict(self):
        """Convert intent to a dictionary."""
        return {
            "id": str(self.id),
            "email": self.email,
            "name": self.name,
            "business_name": self.business_name,
            "program": self.program,
            "plan_name": self.plan_name,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
