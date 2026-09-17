"""
PD & Role Scorecard models.

Backs the Position Description generator: the advisor supplies a completed
Roles & Responsibilities matrix, and the tool produces a Position Description
(.docx) and a Half-Yearly Role Scorecard (.xlsx) for each role in turn.
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class PDScorecard(Base):
    """
    A single PD & Scorecard build for one client. Holds the source matrix and
    the shared inputs; the per-role drafts live on PDScorecardRole.
    """
    __tablename__ = "pd_scorecards"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    # Relationships
    engagement_id = Column(UUID(as_uuid=True), ForeignKey('engagements.id', ondelete='SET NULL'), nullable=True, index=True,
                           comment="Optional link to engagement")
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)

    # Status tracking
    status = Column(String(50), nullable=False, server_default='inputs', index=True,
                    comment="inputs, roles_identified, in_progress, completed")
    current_step = Column(Integer, nullable=True, comment="Current step the user is on (1-4)")
    max_step_reached = Column(Integer, nullable=True, comment="Maximum step the user has reached (1-4)")

    # Step 1: Inputs
    client_name = Column(String(255), nullable=True, comment="Business name shown in the PD header")
    fy_range = Column(String(50), nullable=True, comment="Financial year range for transition sections, e.g. 'FY25-27'")
    file_ids = Column(JSONB, nullable=True, comment="List of Claude file_ids for the uploaded matrix and reference PDs")
    file_mappings = Column(JSONB, nullable=True, comment="Mapping of filename to file_id: {'matrix.xlsx': 'file-abc123'}")
    stored_files = Column(JSONB, nullable=True, comment="Mapping of filename to relative storage path: {'matrix.xlsx': 'pd_id/matrix.xlsx'}")
    reference_pd_files = Column(JSONB, nullable=True,
                                comment="Filenames flagged as tone-only reference PDs: ['old-ceo-pd.docx']")
    pasted_notes = Column(Text, nullable=True, comment="Pasted matrix content or extra notes")

    # Step 2: The matrix the PDs are built from
    matrix_rows = Column(JSONB, nullable=True,
                         comment=(
                             "Source matrix rows. Each row matches the Job Roles columns: "
                             "name, role_description, time, priorities, retain, gain, lose, action, resp, when"
                         ))

    # AI metadata
    ai_model_used = Column(String(100), nullable=True, comment="AI model used")
    ai_tokens_used = Column(Integer, nullable=True, comment="Total tokens used in AI processing")

    # Soft delete
    is_deleted = Column(Boolean, nullable=False, server_default='false', comment="Whether this record has been soft deleted")

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    completed_at = Column(DateTime, nullable=True, comment="When every included role was first approved")

    # Relationships
    engagement = relationship("Engagement", back_populates="pd_scorecards")
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])
    roles = relationship(
        "PDScorecardRole",
        back_populates="pd_scorecard",
        cascade="all, delete-orphan",
        order_by="PDScorecardRole.sort_order",
    )

    def __repr__(self):
        return f"<PDScorecard(id={self.id}, status='{self.status}')>"

    def to_dict(self, include_roles: bool = True):
        """Convert the build to a dictionary"""
        data = {
            "id": str(self.id),
            "engagement_id": str(self.engagement_id) if self.engagement_id else None,
            "created_by_user_id": str(self.created_by_user_id),
            "status": self.status,
            "current_step": self.current_step,
            "max_step_reached": self.max_step_reached,
            "client_name": self.client_name,
            "fy_range": self.fy_range,
            "file_ids": self.file_ids,
            "file_mappings": self.file_mappings,
            "stored_files": self.stored_files,
            "reference_pd_files": self.reference_pd_files,
            "pasted_notes": self.pasted_notes,
            "matrix_rows": self.matrix_rows,
            "ai_model_used": self.ai_model_used,
            "ai_tokens_used": self.ai_tokens_used,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
        if include_roles:
            data["roles"] = [role.to_dict() for role in self.roles if not role.is_deleted]
        return data


class PDScorecardRole(Base):
    """
    One role within a build. Carries its own PD and scorecard drafts and their
    approval state, so roles are completed one at a time and exported
    independently.
    """
    __tablename__ = "pd_scorecard_roles"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    # Parent
    pd_scorecard_id = Column(UUID(as_uuid=True), ForeignKey('pd_scorecards.id', ondelete='CASCADE'), nullable=False, index=True)

    # Identity
    role_title = Column(String(255), nullable=False, comment="Role name, e.g. 'General Manager'")
    person_name = Column(String(255), nullable=True, comment="Person currently in the role, where known")
    sort_order = Column(Integer, nullable=False, server_default='0')
    included = Column(Boolean, nullable=False, server_default='true',
                      comment="Whether the advisor confirmed this role for the build")

    # Source responsibilities for this role, split by retain/gain/lose
    source_responsibilities = Column(JSONB, nullable=True,
                                     comment="Matrix rows attributed to this role, grouped by retain, gain and lose")

    # Position Description
    pd_content = Column(JSONB, nullable=True, comment="The seven PD sections")
    pd_status = Column(String(50), nullable=False, server_default='not_started',
                       comment="not_started, draft, approved")
    pd_approved_at = Column(DateTime, nullable=True)

    # Half-Yearly Role Scorecard
    scorecard_content = Column(JSONB, nullable=True, comment="The four scorecard sections")
    scorecard_status = Column(String(50), nullable=False, server_default='not_started',
                              comment="not_started, draft, approved")
    scorecard_approved_at = Column(DateTime, nullable=True)

    # Soft delete
    is_deleted = Column(Boolean, nullable=False, server_default='false', comment="Whether this record has been soft deleted")

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships
    pd_scorecard = relationship("PDScorecard", back_populates="roles")

    __table_args__ = (
        Index('ix_pd_scorecard_roles_parent_order', 'pd_scorecard_id', 'sort_order'),
    )

    def __repr__(self):
        return f"<PDScorecardRole(id={self.id}, role_title='{self.role_title}')>"

    def to_dict(self):
        """Convert the role to a dictionary"""
        return {
            "id": str(self.id),
            "pd_scorecard_id": str(self.pd_scorecard_id),
            "role_title": self.role_title,
            "person_name": self.person_name,
            "sort_order": self.sort_order,
            "included": self.included,
            "source_responsibilities": self.source_responsibilities,
            "pd_content": self.pd_content,
            "pd_status": self.pd_status,
            "pd_approved_at": self.pd_approved_at.isoformat() if self.pd_approved_at else None,
            "scorecard_content": self.scorecard_content,
            "scorecard_status": self.scorecard_status,
            "scorecard_approved_at": self.scorecard_approved_at.isoformat() if self.scorecard_approved_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
