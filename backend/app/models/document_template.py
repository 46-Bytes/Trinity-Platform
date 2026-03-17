"""
DocumentTemplate model - stores .docx templates in the database
"""
import uuid
from sqlalchemy import Column, String, LargeBinary, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class DocumentTemplate(Base):
    __tablename__ = "document_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    file_name = Column(String, nullable=False, unique=True, index=True)
    display_name = Column(String, nullable=False)
    file_data = Column(LargeBinary, nullable=False)
    file_size = Column(Integer, nullable=False)
    uploaded_by_user_id = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
