"""
Pydantic schemas for Note model
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


# Base schema with common fields
class NoteBase(BaseModel):
    """Base note schema"""
    title: Optional[str] = Field(None, max_length=255, description="Optional note title")
    content: str = Field(..., description="Note content/body")
    note_type: str = Field(default="general", description="general, meeting, observation, decision, progress_update")
    is_pinned: bool = Field(default=False, description="Whether note is pinned to top")
    visibility: str = Field(default="all", description="all, advisor_only, client_only")
    tags: Optional[List[str]] = Field(default=[], description="Array of tags for categorization")
    attachments: Optional[List[Dict[str, Any]]] = Field(default=[], description="Array of attachment metadata")


# Schema for creating a note
class NoteCreate(NoteBase):
    """Schema for creating a new note"""
    engagement_id: UUID = Field(..., description="The engagement this note belongs to")
    diagnostic_id: Optional[UUID] = Field(None, description="Optional: If note references a diagnostic")
    task_id: Optional[UUID] = Field(None, description="Optional: If note references a task")


# Schema for updating a note
class NoteUpdate(BaseModel):
    """Schema for updating a note"""
    title: Optional[str] = Field(None, max_length=255)
    content: Optional[str] = None
    note_type: Optional[str] = None
    is_pinned: Optional[bool] = None
    visibility: Optional[str] = None
    tags: Optional[List[str]] = None
    attachments: Optional[List[Dict[str, Any]]] = None


# Schema for note response
class NoteResponse(NoteBase):
    """Schema for note response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    engagement_id: UUID
    diagnostic_id: Optional[UUID] = None
    task_id: Optional[UUID] = None
    author_id: UUID
    created_at: datetime
    updated_at: datetime



# Schema for note list item (with author info)
class NoteListItem(NoteResponse):
    """Schema for note in list view with author information"""
    author_name: Optional[str] = Field(None, description="Name of the note author")
    engagement_name: Optional[str] = Field(None, description="Name of the engagement")


# Attachment schema for better typing
class NoteAttachment(BaseModel):
    """Schema for note attachment metadata"""
    file_name: str = Field(..., description="Name of the file")
    file_url: str = Field(..., description="URL to access the file")
    file_type: str = Field(..., description="MIME type of the file")
    file_size: Optional[int] = Field(None, description="Size of the file in bytes")
    uploaded_at: datetime = Field(..., description="When the file was uploaded")

