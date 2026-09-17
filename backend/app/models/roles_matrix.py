"""
Roles & Responsibilities Matrix model.

Backs the HR Planning Tool workflow: advisors upload position descriptions and
notes, the AI extracts responsibilities, and the result is exported into the
"Job Roles" tab of the HR Planning Tool workbook.
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class RolesMatrix(Base):
    """
    RolesMatrix represents a single Roles & Responsibilities matrix build.
    Stores the advisor's inputs, the extracted responsibilities, and the
    reviewed matrix rows used for the Excel export.
    """
    __tablename__ = "roles_matrices"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    # Relationships
    engagement_id = Column(UUID(as_uuid=True), ForeignKey('engagements.id', ondelete='SET NULL'), nullable=True, index=True,
                           comment="Optional link to engagement")
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)

    # Status tracking
    status = Column(String(50), nullable=False, server_default='inputs', index=True,
                    comment="inputs, extracted, matrix_built, completed")
    # Step tracking for UI persistence
    current_step = Column(Integer, nullable=True, comment="Current step the user is on (1-4)")
    max_step_reached = Column(Integer, nullable=True, comment="Maximum step the user has reached (1-4)")

    # Step 1: Inputs
    file_ids = Column(JSONB, nullable=True, comment="List of Claude file_ids for uploaded PDs/notes")
    file_mappings = Column(JSONB, nullable=True, comment="Mapping of filename to file_id: {'pd.pdf': 'file-abc123'}")
    stored_files = Column(JSONB, nullable=True, comment="Mapping of filename to relative storage path: {'pd.pdf': 'matrix_id/pd.pdf'}")
    staff = Column(JSONB, nullable=True, comment="Key staff: [{'name': 'Scott', 'role_title': 'Director'}]")
    included_roles = Column(JSONB, nullable=True, comment="Roles confirmed for inclusion in the matrix: ['Director', ...]")
    pasted_notes = Column(Text, nullable=True, comment="Pasted responsibilities lists, org chart text or notes")

    # Step 2: Extraction
    extracted_responsibilities = Column(JSONB, nullable=True,
                                        comment="Per-person responsibilities extracted from the inputs")

    # Step 3: Matrix
    matrix_rows = Column(JSONB, nullable=True,
                         comment=(
                             "Ordered matrix rows. Each row matches the Job Roles columns: "
                             "name, role_description, time, priorities, retain, gain, lose, action, resp, when"
                         ))
    matrix_edited = Column(Boolean, nullable=False, server_default='false',
                           comment="Whether the advisor has edited the generated matrix")

    # AI metadata
    ai_model_used = Column(String(100), nullable=True, comment="AI model used")
    ai_tokens_used = Column(Integer, nullable=True, comment="Total tokens used in AI processing")

    # Soft delete
    is_deleted = Column(Boolean, nullable=False, server_default='false', comment="Whether this record has been soft deleted")

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    completed_at = Column(DateTime, nullable=True, comment="When the matrix was first exported")

    # Relationships
    engagement = relationship("Engagement", back_populates="roles_matrices")
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])

    def __repr__(self):
        return f"<RolesMatrix(id={self.id}, status='{self.status}')>"

    def to_dict(self):
        """Convert matrix to dictionary"""
        return {
            "id": str(self.id),
            "engagement_id": str(self.engagement_id) if self.engagement_id else None,
            "created_by_user_id": str(self.created_by_user_id),
            "status": self.status,
            "current_step": self.current_step,
            "max_step_reached": self.max_step_reached,
            "file_ids": self.file_ids,
            "file_mappings": self.file_mappings,
            "stored_files": self.stored_files,
            "staff": self.staff,
            "included_roles": self.included_roles,
            "pasted_notes": self.pasted_notes,
            "extracted_responsibilities": self.extracted_responsibilities,
            "matrix_rows": self.matrix_rows,
            "matrix_edited": self.matrix_edited,
            "ai_model_used": self.ai_model_used,
            "ai_tokens_used": self.ai_tokens_used,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
