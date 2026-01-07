"""
Firm model for multi-advisor organizations.
"""
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from ..database import Base


class Firm(Base):
    """
    Firm represents an organization that employs multiple advisors.
    Each firm has one Firm Admin who manages billing and users.
    """
    __tablename__ = "firms" 
    # Primary Key
    id = Column( UUID(as_uuid=True),primary_key=True,default=uuid.uuid4,unique=True, nullable=False, comment="Unique identifier for the firm")
    # Firm Information
    firm_name = Column(String(255),nullable=False,comment="Name of the firm/organization")
    
    # Firm Admin (the primary user who manages the firm)
    firm_admin_id = Column(UUID(as_uuid=True), nullable=False,unique=True,index=True,comment="Foreign key to users (the Firm Admin)")  
    
    # Subscription & Billing
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True, index=True, comment="Foreign key to subscriptions")
    subscription_plan = Column(String(50),nullable=True,comment="Subscription plan name (e.g., 'professional', 'enterprise')")
    seat_count = Column(Integer,nullable=False,default=5,comment="Number of seats purchased (minimum 5)")  
    seats_used = Column( Integer, nullable=False, default=1, comment="Number of active advisor seats in use")  
    billing_email = Column(String(255),nullable=True,comment="Email for billing notifications")
    
    # Clients array - stores array of client user IDs associated with this firm
    clients = Column(ARRAY(UUID(as_uuid=True)), nullable=True, default=None, comment="Array of client user IDs associated with this firm")
    
    # Status
    is_active = Column(Boolean,default=True,nullable=False,comment="Whether the firm account is active")
    
    # Timestamps
    created_at = Column(DateTime,default=datetime.utcnow,nullable=False,comment="When the firm was created")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,nullable=False,comment="When the firm was last updated")
    
    # Relationships
    advisors = relationship("User", back_populates="firm")
    engagements = relationship("Engagement", back_populates="firm")
    subscription = relationship("Subscription", uselist=False, primaryjoin="Firm.subscription_id == Subscription.id")
    
    def __repr__(self):
        return f"<Firm {self.firm_name}>"
    
    def to_dict(self):
        """Convert firm object to dictionary."""
        return {
            "id": str(self.id),
            "firm_name": self.firm_name,
            "firm_admin_id": str(self.firm_admin_id),
            "subscription_id": str(self.subscription_id) if self.subscription_id else None,
            "subscription_plan": self.subscription_plan,
            "seat_count": self.seat_count,
            "seats_used": self.seats_used,
            "billing_email": self.billing_email,
            "clients": [str(client_id) for client_id in (self.clients or [])],
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }