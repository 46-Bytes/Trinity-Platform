"""
Media model for file uploads
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, func, ForeignKey, Table
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
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    
    # Relationships
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # File metadata
    file_name = Column(String(255), nullable=False, comment="Original filename")
    file_path = Column(Text, nullable=False, comment="Storage path (local or S3)")
    file_size = Column(Integer, nullable=True, comment="File size in bytes")
    file_type = Column(String(100), nullable=True, comment="MIME type")
    file_extension = Column(String(20), nullable=True, comment="File extension (pdf, jpg, etc.)")
    
    # OpenAI integration
    openai_file_id = Column(String(255), nullable=True, unique=True, index=True,
                           comment="OpenAI file ID for GPT analysis")
    openai_purpose = Column(String(50), nullable=True, 
                           comment="OpenAI file purpose (assistants, vision, etc.)")
    openai_uploaded_at = Column(DateTime, nullable=True, comment="When uploaded to OpenAI")
    
    # Metadata
    description = Column(Text, nullable=True, comment="User-provided description")
    question_field_name = Column(String(255), nullable=True, 
                                comment="Which diagnostic question this file answers")
    is_active = Column(Boolean, nullable=False, server_default='true')
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), 
                       onupdate=func.current_timestamp())
    deleted_at = Column(DateTime, nullable=True, comment="Soft delete timestamp")
    
    # Relationships
    user = relationship("User", back_populates="media")
    diagnostics = relationship("Diagnostic", secondary=diagnostic_media, back_populates="media")
    
    def __repr__(self):
        return f"<Media(id={self.id}, file_name='{self.file_name}', openai_file_id='{self.openai_file_id}')>"
    
    def to_dict(self):
        """Convert media to dictionary"""
        return {
            "id": str(self.id),
            "file_name": self.file_name,
            "file_size": self.file_size,
            "file_type": self.file_type,
            "openai_file_id": self.openai_file_id,
            "description": self.description,
            "question_field_name": self.question_field_name,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

