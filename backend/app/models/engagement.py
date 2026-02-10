"""
Engagement model for client-advisor workspaces
"""
from sqlalchemy import Column, String, Text, DateTime, ARRAY, func, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class Engagement(Base):
    """
    Engagement represents a client-advisor working relationship/workspace.
    It serves as the central hub for diagnostics, tasks, and notes.
    """
    __tablename__ = "engagements"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    
    # Relationships to firms and users
    firm_id = Column(UUID(as_uuid=True), ForeignKey("firms.id", ondelete="SET NULL"), nullable=True, index=True, comment="Foreign key to firms (NULL for solo advisors)")
    client_id = Column(UUID(as_uuid=True), nullable=False, index=True, comment="Foreign key to users (the client account)")
    primary_advisor_id = Column(UUID(as_uuid=True), nullable=False, index=True, comment="Foreign key to users (main advisor)")
    secondary_advisor_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True, comment="Array of additional advisor IDs")
    
    # Engagement details
    engagement_name = Column(String(255), nullable=False, comment="Project/client name (e.g., 'ABC Corp Growth Strategy')")
    business_name = Column(String(255), nullable=True, comment="Client's business name")
    industry = Column(String(100), nullable=True, comment="Business industry")
    description = Column(Text, nullable=True, comment="Engagement description/notes")
    tool = Column(String(100), nullable=True, comment="Selected tool for the engagement")
    
    # Status and timestamps
    status = Column(String(50), nullable=False, server_default='active', index=True, comment="active, paused, completed, archived")
    is_deleted = Column(Boolean, nullable=False, server_default='false', comment="Whether the engagement has been soft deleted")
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    firm = relationship("Firm", back_populates="engagements")
    diagnostics = relationship("Diagnostic", back_populates="engagement", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="engagement", cascade="all, delete-orphan")
    notes = relationship("Note", back_populates="engagement", cascade="all, delete-orphan")
    bba_projects = relationship("BBA", back_populates="engagement", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Engagement(id={self.id}, name='{self.engagement_name}', client_id={self.client_id})>"

