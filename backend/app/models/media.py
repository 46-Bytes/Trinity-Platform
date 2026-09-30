"""
Media model for file uploads
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, func, ForeignKey, Index, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


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
    Files are stored locally and optionally uploaded to OpenAI for analysis.
    """
    __tablename__ = "media"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    
    # Relationships
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    # Set only for files uploaded straight to an engagement. Diagnostic uploads
    # leave this null and reach their engagement through diagnostic_media.
    engagement_id = Column(UUID(as_uuid=True), ForeignKey('engagements.id', ondelete='SET NULL'),
                           nullable=True, index=True,
                           comment="Engagement this file was uploaded to, if uploaded outside a diagnostic")
    
    # File metadata
    file_name = Column(String(255), nullable=False, comment="Original filename")
    # NULL for a data room file: those live in Drive and Trinity keeps no copy.
    file_path = Column(Text, nullable=True, comment="Local storage path; NULL when the bytes live in Drive")
    file_size = Column(Integer, nullable=True, comment="File size in bytes")
    file_type = Column(String(100), nullable=True, comment="MIME type")
    file_extension = Column(String(20), nullable=True, comment="File extension (pdf, jpg, etc.)")

    # ---- Sale Ready data room (Google Drive) -------------------------------
    # All NULL on every file that is not a data room document, which is every
    # file outside Sale Ready. Drive is the store; these columns are the index.
    # Indexed in __table_args__ rather than here: add_drive_data_room named the
    # unique index uq_media_drive_file_id, and unique=True/index=True would have
    # the model expect ix_media_drive_file_id instead.
    drive_file_id = Column(String(255), nullable=True,
                           comment="Drive file id; the locator when file_path is NULL")
    drive_web_link = Column(Text, nullable=True,
                            comment="Drive UI link. Returned to advisors and owners; never to a buyer.")
    drive_modified_time = Column(DateTime, nullable=True,
                                 comment="Drive's modifiedTime at last sync; decides sync conflicts")
    dd_category_code = Column(String(10), nullable=True, comment="DD category this file is filed under, e.g. '3'")
    dd_sub_item_code = Column(String(10), nullable=True, comment="DD sub-item, e.g. '3.1'; one data room folder")
    source = Column(String(20), nullable=True,
                    comment="'trinity' when uploaded here, 'drive' when found by the sync")
    # Set only when uploaded from one DD item; NULL for Files-tab uploads and Drive-added files.
    # Indexed in __table_args__ under the name add_sale_ready_gap_fixes used.
    dd_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey('engagement_dd_item.id', ondelete='SET NULL', name='fk_media_dd_item_id'),
        nullable=True, comment="DD item the file was uploaded from (Sale Ready)",
    )

    # OpenAI integration (preserved for rollback)
    openai_file_id = Column(String(255), nullable=True, unique=True, index=True,
                           comment="OpenAI file ID for GPT analysis")
    openai_purpose = Column(String(50), nullable=True,
                           comment="OpenAI file purpose (assistants, vision, etc.)")
    openai_uploaded_at = Column(DateTime, nullable=True, comment="When uploaded to OpenAI")

    # Generic LLM integration (provider-agnostic)
    llm_file_id = Column(String(255), nullable=True, index=True,
                        comment="LLM provider file ID (Claude, OpenAI, etc.)")
    llm_provider = Column(String(50), nullable=True,
                         comment="LLM provider name (claude, openai)")
    llm_uploaded_at = Column(DateTime, nullable=True,
                            comment="When uploaded to current LLM provider")
    
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
    engagement = relationship("Engagement")
    diagnostics = relationship("Diagnostic", secondary=diagnostic_media, back_populates="media")

    __table_args__ = (
        # Both created by add_drive_data_room and declared here under the names
        # it used, so autogenerate does not propose dropping them. The unique
        # one is what makes the Drive sync idempotent: a file moved or renamed
        # in Drive matches on its id and updates, rather than duplicating.
        Index('uq_media_drive_file_id', 'drive_file_id', unique=True),
        Index('ix_media_engagement_dd_folder',
              'engagement_id', 'dd_category_code', 'dd_sub_item_code'),
        Index('ix_media_dd_item_id', 'dd_item_id'),
    )

    def __repr__(self):
        file_id = self.llm_file_id or self.openai_file_id
        return f"<Media(id={self.id}, file_name='{self.file_name}', llm_file_id='{file_id}')>"

    def to_dict(self):
        """Convert media to dictionary"""
        return {
            "id": str(self.id),
            "file_name": self.file_name,
            "file_size": self.file_size,
            "file_type": self.file_type,
            "openai_file_id": self.openai_file_id,
            "llm_file_id": self.llm_file_id,
            "llm_provider": self.llm_provider,
            "description": self.description,
            "question_field_name": self.question_field_name,
            "tag": self.tag,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

