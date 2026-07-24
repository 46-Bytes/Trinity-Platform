"""
Subscription model for tracking firm and self-service billing.
"""
from sqlalchemy import Column, String, DateTime, Integer, Numeric, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from ..database import Base


# Statuses that mean the subscriber is entitled to the paid surface.
ENTITLED_STATUSES = ("active", "trialing")


class Subscription(Base):
    """
    Tracks subscription and billing information.

    Serves two tiers:
    - Firm subscriptions: linked from Firm.subscription_id (many firms may share one).
    - Self-service subscriptions: `user_id` points at the business owner, and
      `program` records which program they bought (one subscription = one
      program = one engagement).
    """
    __tablename__ = "subscriptions"

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False, comment="Unique identifier for the subscription")
    plan_name = Column(String(50), nullable=False, comment="Subscription plan name (e.g., 'professional', 'enterprise')")
    seat_count = Column( Integer,nullable=False,comment="Number of seats in the subscription")
    monthly_price = Column( Numeric(10, 2), nullable=False, comment="Monthly subscription price")
    status = Column( String(20), nullable=False, default="active", comment="Subscription status: active, cancelled, past_due, trialing, pending")
    created_at = Column(DateTime,default=datetime.utcnow, nullable=False,comment="When the subscription was created")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, comment="When the subscription was last updated")

    # --- Self-service (SaaS) tier ---
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Foreign key to users (the self-service business owner). NULL for firm subscriptions.",
    )
    program = Column(
        String(50),
        nullable=True,
        comment="Program bought: value_builder or sale_ready (becomes Engagement.tool). NULL for firm subscriptions.",
    )
    provider = Column(
        String(20),
        nullable=False,
        server_default="manual",
        comment="Billing provider that owns this subscription: manual or stripe",
    )

    # --- Billing provider bookkeeping ---
    # These columns already exist in the database (created by
    # create_firms_and_subscriptions_tables.py) but were never mapped.
    stripe_subscription_id = Column(String(255), nullable=True, unique=True, index=True, comment="Provider-side subscription ID")
    stripe_customer_id = Column(String(255), nullable=True, index=True, comment="Provider-side customer ID")
    current_period_start = Column(DateTime, nullable=True, comment="Start of the current billing period")
    current_period_end = Column(DateTime, nullable=True, comment="End of the current billing period")
    cancel_at_period_end = Column(Boolean, nullable=True, default=False, comment="Whether the subscription ends at period end")
    cancelled_at = Column(DateTime, nullable=True, comment="When the subscription was cancelled")

    # Relationships
    # Note: Firm.subscription uses subscription_id, so we don't need back_populates here
    # Access firm via Firm.subscription_id (reverse lookup)
    owner = relationship("User", foreign_keys=[user_id], backref="subscriptions")

    @property
    def is_entitled(self) -> bool:
        """True while the subscriber should have access to the paid surface."""
        return self.status in ENTITLED_STATUSES

    def __repr__(self):
        return f"<Subscription(id={self.id}, plan={self.plan_name}, status={self.status})>"

    def to_dict(self):
        """Convert subscription object to dictionary."""
        return {
            "id": str(self.id),
            "plan_name": self.plan_name,
            "seat_count": self.seat_count,
            "monthly_price": float(self.monthly_price) if self.monthly_price else None,
            "status": self.status,
            "user_id": str(self.user_id) if self.user_id else None,
            "program": self.program,
            "provider": self.provider,
            "current_period_start": self.current_period_start.isoformat() if self.current_period_start else None,
            "current_period_end": self.current_period_end.isoformat() if self.current_period_end else None,
            "cancel_at_period_end": self.cancel_at_period_end,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


