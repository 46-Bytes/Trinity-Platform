"""
Task model for action items (manual or AI-generated)
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, Date, Boolean, func, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID, ARRAY
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
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)  
    
    # Relationships
    engagement_id = Column(UUID(as_uuid=True), ForeignKey('engagements.id', ondelete='CASCADE'), nullable=False, index=True)
    diagnostic_id = Column(UUID(as_uuid=True), ForeignKey('diagnostics.id', ondelete='SET NULL'), nullable=True, index=True,
                          comment="If auto-generated from diagnostic")
    # Polymorphic and deliberately unconstrained - see add_task_source_deliverable.
    # Holds the library id for a preset deliverable and the instance id for an
    # advisor-added one, which is two tables and therefore no single FK. The
    # absence of a constraint is what lets a task outlive its deliverable being
    # scoped out or retired, as Part A requires.
    source_deliverable_id = Column(UUID(as_uuid=True), nullable=True, index=True,
                                   comment="Deliverable this task was generated from, if any")
    assigned_to_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    assigned_to_user_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True, index=True,
                                  comment="Array of user IDs assigned to this task (for multiple assignments, e.g., all advisors in engagement)")
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

    # Sale Ready: module_reference holds the stage code, section the task group
    # (must_do / optional / client_specific). NULL on every other task.
    section = Column(String(20), nullable=True)
    source_task_template_id = Column(
        UUID(as_uuid=True),
        ForeignKey('program_task_template.id', ondelete='SET NULL', name='fk_tasks_source_task_template'),
        nullable=True,
        comment="Sale Ready task template this task was created from; NULL for every other task",
    )
    # Sale Ready only: the mockup's "not required" and "blocked" marks. Kept out
    # of `status`, which is shared with every other feature and knows exactly
    # four values (C7). NULL on every non-Sale Ready task.
    sale_ready_state = Column(
        String(20), nullable=True,
        comment="Sale Ready only: 'not_applicable' or 'blocked'; NULL for every other task",
    )
    # The column is `notes`, but `notes` on this class is already the Note
    # relationship below, so the text column is mapped as `task_notes`.
    task_notes = Column('notes', Text, nullable=True, comment="Free-text notes on the task")
    
    # Dates
    due_date = Column(Date, nullable=True, index=True, comment="Task due date")
    completed_at = Column(DateTime, nullable=True, comment="When task was completed")
    
    # Soft delete
    is_deleted = Column(Boolean, nullable=False, server_default='false', comment="Whether this record has been soft deleted")

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships
    engagement = relationship("Engagement", back_populates="tasks")
    diagnostic = relationship("Diagnostic", back_populates="tasks")
    notes = relationship("Note", back_populates="task", cascade="all, delete-orphan")

    __table_args__ = (
        # One live task per Sale Ready template per engagement; soft-deleted
        # tasks drop out, so a deleted template task can be recreated.
        Index(
            'uq_tasks_engagement_source_template', 'engagement_id', 'source_task_template_id',
            unique=True,
            postgresql_where=text('source_task_template_id IS NOT NULL AND is_deleted = false'),
        ),
        Index('ix_tasks_engagement_module_section', 'engagement_id', 'module_reference', 'section'),
    )

    def __repr__(self):
        return f"<Task(id={self.id}, title='{self.title}', status='{self.status}', priority='{self.priority}')>"

