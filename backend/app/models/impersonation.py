"""
ImpersonationSession model for tracking superadmin impersonation sessions.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from ..database import Base


class ImpersonationSession(Base):
    """
    Model representing an active impersonation session.
    
    Tracks when a superadmin impersonates another user for audit purposes.
    """
    __tablename__ = "impersonation_sessions"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,unique=True,nullable=False,comment="Unique identifier for the impersonation session") 
    # Foreign Keys
    original_user_id = Column(UUID(as_uuid=True),ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="The superadmin user who is impersonating")
    impersonated_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="The user being impersonated")
    # Status
    status = Column( String(20), default="active", nullable=False, comment="Session status: 'active' or 'ended'")
    # Timestamps
    created_at = Column(DateTime,default=datetime.utcnow,nullable=False,comment="When the impersonation session was created")
    ended_at = Column(DateTime, nullable=True, comment="When the impersonation session was ended")
    # Relationships
    original_user = relationship("User", foreign_keys=[original_user_id], backref="impersonation_sessions_started")
    impersonated_user = relationship("User", foreign_keys=[impersonated_user_id], backref="impersonation_sessions_received")
    
    # Indexes
    __table_args__ = (
        Index('idx_impersonation_original_user', 'original_user_id'),
        Index('idx_impersonation_impersonated_user', 'impersonated_user_id'),
        Index('idx_impersonation_status', 'status'),
    )
    
    def __repr__(self):
        return f"<ImpersonationSession(id={self.id}, original={self.original_user_id}, impersonated={self.impersonated_user_id}, status={self.status})>"

