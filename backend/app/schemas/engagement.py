"""
Pydantic schemas for Engagement model
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from uuid import UUID


# Base schema with common fields
class EngagementBase(BaseModel):
    """Base engagement schema"""
    engagement_name: str = Field(..., max_length=255, description="Project/client name")
    business_name: Optional[str] = Field(None, max_length=255, description="Client's business name")
    industry: Optional[str] = Field(None, max_length=100, description="Business industry")
    description: Optional[str] = Field(None, description="Engagement description/notes")
    tool: Optional[str] = Field(None, max_length=100, description="Selected tool for the engagement")
    status: str = Field(default="active", description="active, paused, completed, archived")


# Schema for creating an engagement
class EngagementCreate(EngagementBase):
    """Schema for creating a new engagement"""
    client_id: UUID = Field(..., description="The client user ID")
    primary_advisor_id: UUID = Field(..., description="The primary advisor user ID")
    firm_id: Optional[UUID] = Field(None, description="Firm ID for multi-advisor firms")
    secondary_advisor_ids: Optional[List[UUID]] = Field(default=[], description="Additional advisor IDs")


# Schema for updating an engagement
class EngagementUpdate(BaseModel):
    """Schema for updating an engagement"""
    engagement_name: Optional[str] = Field(None, max_length=255)
    business_name: Optional[str] = Field(None, max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    tool: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = None
    secondary_advisor_ids: Optional[List[UUID]] = None
    completed_at: Optional[datetime] = None


# Schema for engagement response
class EngagementResponse(EngagementBase):
    """Schema for engagement response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    firm_id: Optional[UUID] = None
    client_id: UUID
    primary_advisor_id: UUID
    secondary_advisor_ids: Optional[List[UUID]] = []
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


# Schema for engagement list (with counts)
class EngagementListItem(EngagementResponse):
    """Schema for engagement in list view with additional metadata"""
    diagnostics_count: int = Field(default=0, description="Number of diagnostics in this engagement")
    tasks_count: int = Field(default=0, description="Number of tasks in this engagement")
    pending_tasks_count: int = Field(default=0, description="Number of pending tasks")
    notes_count: int = Field(default=0, description="Number of notes in this engagement")


# Schema for engagement detail (with relationships)
class EngagementDetail(EngagementResponse):
    """Schema for engagement detail view with related data"""
    # Optional: Include related objects if needed
    # diagnostics: Optional[List['DiagnosticResponse']] = []
    # tasks: Optional[List['TaskResponse']] = []
    # notes: Optional[List['NoteResponse']] = []
    pass

