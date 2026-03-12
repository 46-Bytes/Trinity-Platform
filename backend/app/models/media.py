"""
Media model for file uploads
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, func, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
import uuid

from app.database import Base
from app.config import settings


# Association table for diagnostic-media many-to-many relationship
diagnostic_media = Table(
    'diagnostic_media',
    Base.metadata,
    Column('diagnostic_id', UUID(as_uuid=True), ForeignKey('diagnostics.id', ondelete='CASCADE'), primary_key=True),
    Column('media_id', UUID(as_uuid=True), ForeignKey('media.id', ondelete='CASCADE'), primary_key=True),
    Column('created_at', DateTime, nullable=False, server_default=func.current_timestamp())
)


class Media(Base):
    """
    Media represents uploaded files (PDFs, images, documents, etc.)
    Files are stored locally and optionally uploaded to LLM provider for analysis.
    Supports dual-provider storage (OpenAI + Anthropic) with transparent routing.
    """
    __tablename__ = "media"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)

    # Relationships
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)

    # File metadata
    file_name = Column(String(255), nullable=False, comment="Original filename")
    file_path = Column(Text, nullable=False, comment="Storage path (local or S3)")
    file_size = Column(Integer, nullable=True, comment="File size in bytes")
    file_type = Column(String(100), nullable=True, comment="MIME type")
    file_extension = Column(String(20), nullable=True, comment="File extension (pdf, jpg, etc.)")

    # Provider-specific LLM file IDs
    openai_file_id = Column(String(255), nullable=True, unique=True, index=True,
                            comment="OpenAI file ID for AI analysis")
    anthropic_file_id = Column(String(255), nullable=True, unique=True, index=True,
                               comment="Anthropic file ID for AI analysis")
    llm_purpose = Column(String(50), nullable=True,
                         comment="LLM file purpose (user_data, assistants, etc.)")
    openai_uploaded_at = Column(DateTime, nullable=True, comment="When uploaded to OpenAI")
    anthropic_uploaded_at = Column(DateTime, nullable=True, comment="When uploaded to Anthropic")

    # Metadata
    description = Column(Text, nullable=True, comment="User-provided description")
    question_field_name = Column(String(255), nullable=True,
                                comment="Which diagnostic question this file answers")
    tag = Column(String(255), nullable=True, comment="Document tag for organization (advisor-only)")
    is_active = Column(Boolean, nullable=False, server_default='true')

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(),
                       onupdate=func.current_timestamp())
    deleted_at = Column(DateTime, nullable=True, comment="Soft delete timestamp")

    # Relationships
    user = relationship("User", back_populates="media")
    diagnostics = relationship("Diagnostic", secondary=diagnostic_media, back_populates="media")

    # --- Hybrid properties: route to active provider's column ---

    @hybrid_property
    def llm_file_id(self):
        """Return the file ID for the currently active LLM provider."""
        if settings.LLM_PROVIDER == "openai":
            return self.openai_file_id
        return self.anthropic_file_id

    @llm_file_id.setter
    def llm_file_id(self, value):
        """Set the file ID for the currently active LLM provider."""
        if settings.LLM_PROVIDER == "openai":
            self.openai_file_id = value
        else:
            self.anthropic_file_id = value

    @hybrid_property
    def llm_uploaded_at(self):
        """Return the upload timestamp for the currently active LLM provider."""
        if settings.LLM_PROVIDER == "openai":
            return self.openai_uploaded_at
        return self.anthropic_uploaded_at

    @llm_uploaded_at.setter
    def llm_uploaded_at(self, value):
        """Set the upload timestamp for the currently active LLM provider."""
        if settings.LLM_PROVIDER == "openai":
            self.openai_uploaded_at = value
        else:
            self.anthropic_uploaded_at = value

    def __repr__(self):
        return (
            f"<Media(id={self.id}, file_name='{self.file_name}', "
            f"openai_file_id='{self.openai_file_id}', "
            f"anthropic_file_id='{self.anthropic_file_id}')>"
        )

    def to_dict(self):
        """Convert media to dictionary"""
        return {
            "id": str(self.id),
            "file_name": self.file_name,
            "file_size": self.file_size,
            "file_type": self.file_type,
            "llm_file_id": self.llm_file_id,
            "openai_file_id": self.openai_file_id,
            "anthropic_file_id": self.anthropic_file_id,
            "description": self.description,
            "question_field_name": self.question_field_name,
            "tag": self.tag,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
