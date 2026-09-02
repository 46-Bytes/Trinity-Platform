"""
Help / Video User Guide models.

Stores training/guide videos hosted on YouTube, grouped by admin-managed
categories. Only the extracted YouTube video ID is stored (parsed and
validated at save time); the embed URL is reconstructed at render time.
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class HelpVideoCategory(Base):
    """
    A category grouping help videos (e.g. "Getting Started", "AI Tools").
    Managed by super_admin / admin users.
    """
    __tablename__ = "help_video_categories"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)

    # Category details
    name = Column(String(120), nullable=False, comment="Category display name")
    description = Column(Text, nullable=True, comment="Optional category description")
    position = Column(Integer, nullable=False, server_default='0', index=True,
                      comment="Ordering of categories (ascending)")

    # Soft delete
    is_deleted = Column(Boolean, nullable=False, server_default='false',
                        comment="Whether this record has been soft deleted")

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())

    # Relationships
    videos = relationship("HelpVideo", back_populates="category", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<HelpVideoCategory(id={self.id}, name='{self.name}')>"


class HelpVideo(Base):
    """
    A single help video hosted on YouTube, belonging to a category.
    Only the 11-character YouTube video ID is stored.
    """
    __tablename__ = "help_videos"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)

    # Relationships
    category_id = Column(UUID(as_uuid=True), ForeignKey('help_video_categories.id', ondelete='CASCADE'),
                         nullable=False, index=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'),
                                nullable=True, index=True)

    # Video details
    youtube_video_id = Column(String(20), nullable=False, comment="Extracted 11-char YouTube video ID")
    title = Column(String(255), nullable=False, comment="Video title")
    description = Column(Text, nullable=True, comment="Optional short description")
    position = Column(Integer, nullable=False, server_default='0', index=True,
                      comment="Ordering within the category (ascending)")

    # Soft delete
    is_deleted = Column(Boolean, nullable=False, server_default='false',
                        comment="Whether this record has been soft deleted")

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())

    # Relationships
    category = relationship("HelpVideoCategory", back_populates="videos")

    def __repr__(self):
        return f"<HelpVideo(id={self.id}, title='{self.title}', category_id={self.category_id})>"
