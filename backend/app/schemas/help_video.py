"""
Pydantic schemas for the Help / Video User Guide feature.
"""
from pydantic import BaseModel, Field, ConfigDict, computed_field, field_validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from ..utils.youtube import extract_youtube_id, build_embed_url


# ---------------------------- Categories ----------------------------

class CategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120, description="Category name")
    description: Optional[str] = Field(None, description="Optional category description")


class CategoryCreate(CategoryBase):
    """Schema for creating a category."""
    pass


class CategoryUpdate(BaseModel):
    """Schema for updating a category (partial)."""
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    description: Optional[str] = None


class CategoryResponse(CategoryBase):
    """Schema for a category response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    position: int
    created_at: datetime
    updated_at: datetime


# ------------------------------ Videos ------------------------------

class VideoBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Video title")
    description: Optional[str] = Field(None, description="Optional short description")


class VideoCreate(VideoBase):
    """Schema for creating a video. Accepts any YouTube URL; the ID is stored."""
    category_id: UUID = Field(..., description="Category this video belongs to")
    youtube_url: str = Field(..., description="Any YouTube URL; the video ID is extracted and stored")

    @field_validator("youtube_url")
    @classmethod
    def _validate_youtube_url(cls, v: str) -> str:
        if extract_youtube_id(v) is None:
            raise ValueError("Invalid YouTube URL — could not extract a video ID.")
        return v


class VideoUpdate(BaseModel):
    """Schema for updating a video (partial)."""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    category_id: Optional[UUID] = None
    youtube_url: Optional[str] = Field(None, description="New YouTube URL (optional)")

    @field_validator("youtube_url")
    @classmethod
    def _validate_youtube_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and extract_youtube_id(v) is None:
            raise ValueError("Invalid YouTube URL — could not extract a video ID.")
        return v


class VideoResponse(VideoBase):
    """Schema for a video response, including the reconstructed embed URL."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category_id: UUID
    youtube_video_id: str
    position: int
    created_at: datetime
    updated_at: datetime

    @computed_field  # exposes a ready-to-use embed URL to the frontend
    @property
    def embed_url(self) -> str:
        return build_embed_url(self.youtube_video_id)


class CategoryWithVideos(CategoryResponse):
    """A category plus its ordered, non-deleted videos (end-user payload)."""
    videos: List[VideoResponse] = Field(default_factory=list)


# ------------------------------ Reorder -----------------------------

class ReorderRequest(BaseModel):
    """Body for reorder endpoints — IDs in their new order (ascending)."""
    ordered_ids: List[UUID] = Field(..., description="IDs in the desired new order")
