"""
Pydantic schemas for Task model
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime, date
from uuid import UUID


# Base schema with common fields
class TaskBase(BaseModel):
    """Base task schema"""
    title: str = Field(..., max_length=255, description="Task title/name")
    description: Optional[str] = Field(None, description="Detailed task description")
    task_type: str = Field(default="manual", description="manual, diagnostic_generated")
    status: str = Field(default="pending", description="pending, in_progress, completed, cancelled")
    priority: str = Field(default="medium", description="low, medium, high, critical")
    priority_rank: Optional[int] = Field(None, description="Priority rank from AI (1 = highest)")
    module_reference: Optional[str] = Field(None, max_length=10, description="Module reference (e.g., M1, M2)")
    impact_level: Optional[str] = Field(None, description="Impact level: low, medium, high")
    effort_level: Optional[str] = Field(None, description="Effort level: low, medium, high")
    due_date: Optional[date] = Field(None, description="Task due date")


# Schema for creating a task (manual)
class TaskCreate(TaskBase):
    """Schema for creating a new task manually"""
    engagement_id: UUID = Field(..., description="The engagement this task belongs to")
    created_by_user_id: UUID = Field(..., description="Who created this task")
    assigned_to_user_id: Optional[UUID] = Field(None, description="Who is assigned to this task")
    diagnostic_id: Optional[UUID] = Field(None, description="Optional: If task is linked to a diagnostic")


# Schema for creating a task from diagnostic (auto-generated)
class TaskCreateFromDiagnostic(BaseModel):
    """Schema for creating a task from diagnostic AI recommendations"""
    engagement_id: UUID
    diagnostic_id: UUID
    created_by_user_id: UUID
    assigned_to_user_id: Optional[UUID] = None
    title: str
    description: Optional[str] = None
    priority: str = "medium"
    priority_rank: Optional[int] = None
    module_reference: Optional[str] = None
    impact_level: Optional[str] = None
    effort_level: Optional[str] = None
    due_date: Optional[date] = None
    task_type: str = "diagnostic_generated"


# Schema for updating a task
class TaskUpdate(BaseModel):
    """Schema for updating a task"""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to_user_id: Optional[UUID] = None
    due_date: Optional[date] = None
    completed_at: Optional[datetime] = None


# Schema for task response
class TaskResponse(TaskBase):
    """Schema for task response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    engagement_id: UUID
    diagnostic_id: Optional[UUID] = None
    assigned_to_user_id: Optional[UUID] = None
    created_by_user_id: UUID
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# Schema for task list item (with additional context)
class TaskListItem(TaskResponse):
    """Schema for task in list view with context"""
    engagement_name: Optional[str] = Field(None, description="Name of the engagement")
    assigned_to_name: Optional[str] = Field(None, description="Name of assigned user")
    created_by_name: Optional[str] = Field(None, description="Name of creator")


# Schema for bulk task creation (for diagnostic processing)
class BulkTaskCreate(BaseModel):
    """Schema for creating multiple tasks at once (from diagnostic)"""
    tasks: list[TaskCreateFromDiagnostic] = Field(..., description="List of tasks to create")

