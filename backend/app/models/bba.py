"""
BBA (Business Benchmark Analysis) model for POC file upload and analysis workflow
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class BBA(Base):
    """
    BBA represents a Business Benchmark Analysis project.
    Stores uploaded files, context questionnaire, and analysis results.
    """
    __tablename__ = "bba"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    
    # Relationships
    engagement_id = Column(UUID(as_uuid=True), ForeignKey('engagements.id', ondelete='CASCADE'), nullable=True, index=True,
                          comment="Optional link to engagement")
    diagnostic_id = Column(UUID(as_uuid=True), ForeignKey('diagnostics.id', ondelete='SET NULL'), nullable=True, index=True,
                          comment="When created from a completed diagnostic, link to that diagnostic")
    diagnostic_context = Column(JSONB, nullable=True,
                                comment="Diagnostic report/summary used as context (e.g. report_html or ai_analysis subset)")
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    # Status tracking
    status = Column(String(50), nullable=False, server_default='uploaded', index=True,
                   comment="uploaded, questionnaire_completed, draft_findings, expanded_findings, completed")
    # Step tracking for UI persistence
    current_step = Column(Integer, nullable=True, comment="Current step the user is on (1-9)")
    max_step_reached = Column(Integer, nullable=True, comment="Maximum step the user has reached (1-9)")
    # Step 1: File uploads
    file_ids = Column(JSONB, nullable=True, comment="List of OpenAI file_ids: ['file-abc123', 'file-xyz789']")
    file_mappings = Column(JSONB, nullable=True, comment="Mapping of filename to file_id: {'doc.pdf': 'file-abc123'}")
    stored_files = Column(JSONB, nullable=True, comment="Mapping of filename to relative storage path for persisted uploads: {'doc.pdf': 'project_id/doc.pdf'}")
    # Step 2: Context Capture (Questionnaire)
    client_name = Column(String(255), nullable=True)
    industry = Column(String(255), nullable=True)
    company_size = Column(String(50), nullable=True, comment="startup, small, medium, large, enterprise")
    locations = Column(String(500), nullable=True)
    exclusions = Column(Text, nullable=True, comment="Areas or topics to exclude from analysis")
    constraints = Column(Text, nullable=True, comment="Constraints or limitations to consider")
    preferred_ranking = Column(Text, nullable=True, comment="How findings should be ranked")
    strategic_priorities = Column(Text, nullable=True, comment="Strategic priorities for next 12 months")
    exclude_sale_readiness = Column(Boolean, nullable=False, server_default='false',
                                   comment="Whether to exclude sale-readiness from analysis")
    
    # Step 3: Draft Findings (future)
    draft_findings = Column(JSONB, nullable=True, comment="Ranked list of top findings with summaries")
    draft_findings_edited = Column(Boolean, nullable=False, server_default='false',
                                   comment="Whether user has edited draft findings")
    
    # Step 4: Expanded Findings (future)
    expanded_findings = Column(JSONB, nullable=True, comment="Expanded findings with detailed paragraphs")
    
    # Step 5: Snapshot Table (future)
    snapshot_table = Column(JSONB, nullable=True, comment="Three-column table: Priority Area | Key Findings | Recommendations")
    
    # Step 6: 12-Month Plan
    twelve_month_plan = Column(JSONB, nullable=True, comment="Detailed recommendations with Purpose, Objectives, Actions, BBA Support, Outcomes")
    plan_notes = Column(Text, nullable=True, comment="Notes/disclaimer for the 12-month plan")
    
    # Step 7: Final Report
    executive_summary = Column(Text, nullable=True, comment="2-4 paragraph executive summary")
    final_report = Column(JSONB, nullable=True, comment="Complete compiled report data")
    report_version = Column(Integer, nullable=False, server_default='1', comment="Report version number")

    # Phase 2 – Excel Task Planner (Engagement Planner)
    task_planner_settings = Column(
        JSONB,
        nullable=True,
        comment=(
            "Phase 2 task planner context: lead/support advisors, advisor_count, "
            "max_hours_per_month, start_month, start_year"
        ),
    )
    task_planner_tasks = Column(
        JSONB,
        nullable=True,
        comment=(
            "Phase 2 generated task rows used for Excel export. "
            "Each row matches the Excel columns: Rec #, Recommendation, Owner, "
            "Task, Advisor Hrs, Advisor, Status, Notes, Timing."
        ),
    )
    task_planner_summary = Column(
        JSONB,
        nullable=True,
        comment=(
            "Phase 2 summary data including total BBA hours, per-month hours, "
            "and any capacity warnings."
        ),
    )
    
    # Phase 3 – PowerPoint Presentation Generator
    presentation_slides = Column(
        JSONB,
        nullable=True,
        comment=(
            "Phase 3 presentation slide content. Contains a 'slides' array "
            "with typed slide objects (title, executive_summary, structure, "
            "recommendation, timeline, next_steps) each with an approved flag."
        ),
    )

    # Conversation history (for context continuity)
    conversation_history = Column(JSONB, nullable=True, comment="Message history for AI conversation context")
    
    # AI metadata
    ai_model_used = Column(String(100), nullable=True, comment="AI model used for analysis")
    ai_tokens_used = Column(Integer, nullable=True, comment="Total tokens used in AI processing")
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    questionnaire_completed_at = Column(DateTime, nullable=True, comment="When questionnaire was completed")
    
    # Relationships
    engagement = relationship("Engagement", back_populates="bba_projects")
    diagnostic = relationship("Diagnostic", backref="bba_projects", foreign_keys=[diagnostic_id])
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])
    
    def __repr__(self):
        return f"<BBA(id={self.id}, status='{self.status}', client_name='{self.client_name}')>"
    
    def to_dict(self):
        """Convert BBA to dictionary"""
        return {
            "id": str(self.id),
            "engagement_id": str(self.engagement_id) if self.engagement_id else None,
            "diagnostic_id": str(self.diagnostic_id) if self.diagnostic_id else None,
            "diagnostic_context": self.diagnostic_context,
            "created_by_user_id": str(self.created_by_user_id),
            "status": self.status,
            "file_ids": self.file_ids,
            "file_mappings": self.file_mappings,
            "stored_files": self.stored_files,
            "client_name": self.client_name,
            "industry": self.industry,
            "company_size": self.company_size,
            "locations": self.locations,
            "exclusions": self.exclusions,
            "constraints": self.constraints,
            "preferred_ranking": self.preferred_ranking,
            "strategic_priorities": self.strategic_priorities,
            "exclude_sale_readiness": self.exclude_sale_readiness,
            "draft_findings": self.draft_findings,
            "draft_findings_edited": self.draft_findings_edited,
            "expanded_findings": self.expanded_findings,
            "snapshot_table": self.snapshot_table,
            "twelve_month_plan": self.twelve_month_plan,
            "plan_notes": self.plan_notes,
            "executive_summary": self.executive_summary,
            "final_report": self.final_report,
            "report_version": self.report_version,
            "ai_model_used": self.ai_model_used,
            "ai_tokens_used": self.ai_tokens_used,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "questionnaire_completed_at": self.questionnaire_completed_at.isoformat() if self.questionnaire_completed_at else None,
            "task_planner_settings": self.task_planner_settings,
            "task_planner_tasks": self.task_planner_tasks,
            "task_planner_summary": self.task_planner_summary,
            "presentation_slides": self.presentation_slides,
            "current_step": self.current_step,
            "max_step_reached": self.max_step_reached,
        }

