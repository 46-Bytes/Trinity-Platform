"""
Strategic Business Plan model for tracking plan generation sessions
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class StrategicBusinessPlan(Base):
    """
    StrategicBusinessPlan represents a strategic business plan generation session.
    Tracks document uploads, cross-analysis, section-by-section drafting, and final export.
    """
    __tablename__ = "strategic_business_plans"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)

    # Foreign keys
    engagement_id = Column(UUID(as_uuid=True), ForeignKey('engagements.id', ondelete='CASCADE'), nullable=True, index=True,
                           comment="Optional link to engagement")
    diagnostic_id = Column(UUID(as_uuid=True), ForeignKey('diagnostics.id', ondelete='SET NULL'), nullable=True, index=True,
                           comment="When created from a completed diagnostic")
    diagnostic_context = Column(JSONB, nullable=True,
                                comment="Diagnostic report/ai_analysis used as context")
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)

    # Status tracking
    status = Column(String(50), nullable=False, server_default='draft', index=True,
                    comment="draft, uploading, analysing, drafting, reviewing, exporting, completed")

    # Step tracking for UI persistence (6 wizard steps)
    current_step = Column(Integer, nullable=True, comment="Current wizard step the user is on (1-6)")
    max_step_reached = Column(Integer, nullable=True, comment="Maximum wizard step the user has reached (1-6)")

    # Step 1: Setup & Background
    client_name = Column(String(255), nullable=True)
    industry = Column(String(255), nullable=True)
    planning_horizon = Column(String(50), nullable=True, comment="1-year, 3-year, 5-year")
    target_audience = Column(Text, nullable=True, comment="Primary audience: owners, management team, bank, investors")
    additional_context = Column(Text, nullable=True, comment="Any additional context or notes from the advisor")

    # Step 1: File uploads
    file_ids = Column(JSONB, nullable=True, comment="List of file IDs: ['file-abc123', ...]")
    file_mappings = Column(JSONB, nullable=True, comment="Mapping of filename to file_id: {'doc.pdf': 'file-abc123'}")
    file_tags = Column(JSONB, nullable=True, comment="Mapping of filename to tag: {'workbook.xlsx': 'strategy_workbook', 'diag.pdf': 'diagnostic'}")
    stored_files = Column(JSONB, nullable=True, comment="Mapping of filename to relative storage path")

    # Step 2: Cross-Analysis
    cross_analysis = Column(JSONB, nullable=True,
                            comment="AI cross-pattern analysis: themes, tensions, correlations, gaps, observations")
    cross_analysis_advisor_notes = Column(Text, nullable=True,
                                          comment="Advisor notes/corrections on the cross-analysis")

    # Step 3: Section Drafting
    sections = Column(JSONB, nullable=True, comment="""
        Array of section objects:
        [{
            "key": "executive_summary",
            "title": "Executive Summary",
            "status": "pending|drafting|drafted|revision_requested|approved",
            "content": "...",
            "strategic_implications": "...",
            "revision_notes": "...",
            "revision_history": [...],
            "approved_at": "ISO timestamp",
            "draft_count": 1
        }, ...]
    """)
    current_section_index = Column(Integer, nullable=True, default=0,
                                    comment="Which section is currently being drafted (0-12)")
    emerging_themes = Column(JSONB, nullable=True,
                             comment="Strategic themes surfaced after core diagnostic sections")

    # Step 4: Final Plan Assembly
    final_plan = Column(JSONB, nullable=True, comment="Complete assembled plan data with all approved sections")

    # Step 5: Export
    report_version = Column(Integer, nullable=False, server_default='1', comment="Report version number")
    generated_report_path = Column(Text, nullable=True, comment="Path to the generated .docx file")
    employee_variant_requested = Column(Boolean, nullable=False, server_default='false',
                                         comment="Whether employee-facing variant was requested")
    generated_employee_report_path = Column(Text, nullable=True, comment="Path to the generated employee .docx file")

    # Step 6: Presentation
    presentation_slides = Column(JSONB, nullable=True,
                                  comment="Presentation slide content array with typed slide objects")

    # Conversation history (for AI context continuity)
    conversation_history = Column(JSONB, nullable=True, comment="Message history for AI conversation context")

    # AI metadata
    ai_model_used = Column(String(100), nullable=True, comment="AI model used for analysis")
    ai_tokens_used = Column(Integer, nullable=True, comment="Total tokens used in AI processing")

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    completed_at = Column(DateTime, nullable=True, comment="When plan generation completed")

    # Relationships
    engagement = relationship("Engagement", back_populates="strategic_business_plans")
    diagnostic = relationship("Diagnostic", backref="strategic_business_plans", foreign_keys=[diagnostic_id])
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])

    def __repr__(self):
        return f"<StrategicBusinessPlan(id={self.id}, status='{self.status}', client_name='{self.client_name}')>"

    def to_dict(self):
        """Convert plan to dictionary"""
        return {
            "id": str(self.id),
            "engagement_id": str(self.engagement_id) if self.engagement_id else None,
            "diagnostic_id": str(self.diagnostic_id) if self.diagnostic_id else None,
            "diagnostic_context": self.diagnostic_context,
            "created_by_user_id": str(self.created_by_user_id),
            "status": self.status,
            "current_step": self.current_step,
            "max_step_reached": self.max_step_reached,
            "client_name": self.client_name,
            "industry": self.industry,
            "planning_horizon": self.planning_horizon,
            "target_audience": self.target_audience,
            "additional_context": self.additional_context,
            "file_ids": self.file_ids,
            "file_mappings": self.file_mappings,
            "file_tags": self.file_tags,
            "stored_files": self.stored_files,
            "cross_analysis": self.cross_analysis,
            "cross_analysis_advisor_notes": self.cross_analysis_advisor_notes,
            "sections": self.sections,
            "current_section_index": self.current_section_index,
            "emerging_themes": self.emerging_themes,
            "final_plan": self.final_plan,
            "report_version": self.report_version,
            "generated_report_path": self.generated_report_path,
            "employee_variant_requested": self.employee_variant_requested,
            "generated_employee_report_path": self.generated_employee_report_path,
            "presentation_slides": self.presentation_slides,
            "ai_model_used": self.ai_model_used,
            "ai_tokens_used": self.ai_tokens_used,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
