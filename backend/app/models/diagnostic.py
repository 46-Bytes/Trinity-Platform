"""
Diagnostic model for AI-powered business assessments
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, Numeric, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class Diagnostic(Base):
    """
    Diagnostic represents a 200-question business health assessment.
    Stores questions, user responses, AI analysis, and generates tasks.
    """
    __tablename__ = "diagnostics"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    
    # Relationships
    engagement_id = Column(UUID(as_uuid=True), ForeignKey('engagements.id', ondelete='CASCADE'), nullable=False, index=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    completed_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # Diagnostic metadata
    status = Column(String(50), nullable=False, server_default='draft', index=True, 
                   comment="draft, in_progress, processing, completed, archived")
    diagnostic_type = Column(String(100), nullable=False, server_default='business_health_assessment')
    diagnostic_version = Column(String(20), nullable=False, server_default='1.0')
    
    # JSONB fields - Core diagnostic data
    questions = Column(JSONB, nullable=False, comment="All 200 questions with their structure (from JSON file)")
    user_responses = Column(JSONB, nullable=True, comment="User's answers to all questions")
    scoring_data = Column(JSONB, nullable=True, comment="Question-level and module-level scores")
    ai_analysis = Column(JSONB, nullable=True, comment="GPT-generated insights, recommendations, commentary")
    module_scores = Column(JSONB, nullable=True, comment="The 8 module scores (M1-M8) with details")
    
    # Scoring results
    overall_score = Column(Numeric(3, 1), nullable=True, comment="Overall diagnostic score (0-5, 1 decimal place)")
    
    # Reports
    report_url = Column(Text, nullable=True, comment="S3/storage URL for generated PDF report")
    report_html = Column(Text, nullable=True, comment="HTML version of the report (optional)")
    
    # Task generation tracking
    tasks_generated_count = Column(Integer, nullable=True, server_default='0', 
                                   comment="Number of tasks generated from this diagnostic")
    
    # AI metadata
    ai_model_used = Column(String(100), nullable=True, comment="AI model used for analysis (e.g., gpt-4-turbo)")
    ai_tokens_used = Column(Integer, nullable=True, comment="Total tokens used in AI processing")
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    started_at = Column(DateTime, nullable=True, comment="When user started filling it out")
    completed_at = Column(DateTime, nullable=True, comment="When user submitted it")
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Relationships
    engagement = relationship("Engagement", back_populates="diagnostics")
    tasks = relationship("Task", back_populates="diagnostic", cascade="all, delete-orphan")
    notes = relationship("Note", back_populates="diagnostic")
    
    def __repr__(self):
        return f"<Diagnostic(id={self.id}, engagement_id={self.engagement_id}, status='{self.status}', score={self.overall_score})>"

