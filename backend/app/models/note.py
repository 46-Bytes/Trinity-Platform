"""
Note model for engagement documentation and observations
"""
from sqlalchemy import Column, String, Text, DateTime, Boolean, ARRAY, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class Note(Base):
    """
    Note represents documentation, observations, and updates within an engagement.
    Can optionally reference a specific diagnostic.
    """
    __tablename__ = "notes"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    
    # Relationships
    engagement_id = Column(UUID(as_uuid=True), ForeignKey('engagements.id', ondelete='CASCADE'), nullable=False, index=True)
    diagnostic_id = Column(UUID(as_uuid=True), ForeignKey('diagnostics.id', ondelete='SET NULL'), nullable=True, index=True,
                          comment="Optional: if note references a specific diagnostic")
    author_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey('tasks.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # Note content
    title = Column(String(255), nullable=True, comment="Optional note title")
    content = Column(Text, nullable=False, comment="Note content/body")
    
    # Note classification
    note_type = Column(String(50), nullable=False, server_default='general', index=True,
                      comment="general, meeting, observation, decision, progress_update")
    
    # Display and access control
    is_pinned = Column(Boolean, nullable=False, server_default='false', comment="Whether note is pinned to top")
    visibility = Column(String(50), nullable=False, server_default='all', 
                       comment="all, advisor_only, client_only")
    
    # Organization
    tags = Column(ARRAY(String), nullable=True, comment="Array of tags for categorization")
    attachments = Column(JSONB, nullable=True, comment="Array of attachment metadata (file URLs, names, types)")
    read_by = Column(ARRAY(UUID(as_uuid=True)), nullable=False, server_default="{}", comment="Array of user IDs who have read this note",)
    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), index=True)
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Relationships
    engagement = relationship("Engagement", back_populates="notes")
    diagnostic = relationship("Diagnostic", back_populates="notes")
    task = relationship("Task", back_populates="notes")
    
    def __repr__(self):
        return f"<Note(id={self.id}, engagement_id={self.engagement_id}, diagnostic_id={self.diagnostic_id}, task_id={self.task_id}, type='{self.note_type}', author_id={self.author_id})>"

