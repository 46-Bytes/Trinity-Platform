"""
Subscription model for tracking firm billing.
"""
from sqlalchemy import Column, String, DateTime, Integer, Numeric, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from ..database import Base


class Subscription(Base):
    """
    Tracks firm subscription and billing information.
    """
    __tablename__ = "subscriptions"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False, comment="Unique identifier for the subscription")
    plan_name = Column(String(50), nullable=False, comment="Subscription plan name (e.g., 'professional', 'enterprise')")
    seat_count = Column( Integer,nullable=False,comment="Number of seats in the subscription")  
    monthly_price = Column( Numeric(10, 2), nullable=False, comment="Monthly subscription price")
    status = Column( String(20), nullable=False, default="active", comment="Subscription status: active, cancelled, past_due, trialing")
    created_at = Column(DateTime,default=datetime.utcnow, nullable=False,comment="When the subscription was created")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, comment="When the subscription was last updated")
    
    # Relationships
    # Note: Firm.subscription uses subscription_id, so we don't need back_populates here
    # Access firm via Firm.subscription_id (reverse lookup)
    
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
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


