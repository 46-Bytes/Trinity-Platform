"""
Task model for action items (manual or AI-generated)
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, Date, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class Task(Base):
    """
    Task represents an action item within an engagement.
    Can be manually created or automatically generated from diagnostic AI recommendations.
    """
    __tablename__ = "tasks"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)  
    
    # Relationships
    engagement_id = Column(UUID(as_uuid=True), ForeignKey('engagements.id', ondelete='CASCADE'), nullable=False, index=True)
    diagnostic_id = Column(UUID(as_uuid=True), ForeignKey('diagnostics.id', ondelete='SET NULL'), nullable=True, index=True,
                          comment="If auto-generated from diagnostic")
    assigned_to_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Task details
    title = Column(String(255), nullable=False, comment="Task title/name")
    description = Column(Text, nullable=True, comment="Detailed task description")
    
    # Task classification
    task_type = Column(String(50), nullable=False, server_default='manual', comment="manual, diagnostic_generated")
    status = Column(String(50), nullable=False, server_default='pending', index=True,
                   comment="pending, in_progress, completed, cancelled")
    priority = Column(String(20), nullable=False, server_default='medium', index=True,
                     comment="low, medium, high, critical")
    priority_rank = Column(Integer, nullable=True, comment="Priority rank from AI (1 = highest priority)")
    
    # Diagnostic-generated task metadata
    module_reference = Column(String(50), nullable=True, comment="Module reference from diagnostic (e.g., M1, M2, M3)")
    impact_level = Column(String(20), nullable=True, comment="Impact level: low, medium, high")
    effort_level = Column(String(20), nullable=True, comment="Effort level: low, medium, high")
    
    # Dates
    due_date = Column(Date, nullable=True, index=True, comment="Task due date")
    completed_at = Column(DateTime, nullable=True, comment="When task was completed")
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Relationships
    engagement = relationship("Engagement", back_populates="tasks")
    diagnostic = relationship("Diagnostic", back_populates="tasks")
    notes = relationship("Note", back_populates="task", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Task(id={self.id}, title='{self.title}', status='{self.status}', priority='{self.priority}')>"

