"""
Pydantic schemas for AdvisorClient association model.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class AdvisorClientBase(BaseModel):
    """Base schema for advisor-client association."""
    advisor_id: UUID = Field(..., description="ID of the advisor user")
    client_id: UUID = Field(..., description="ID of the client user")
    status: str = Field(default="active", description="Association status: active, inactive, suspended")


class AdvisorClientCreate(AdvisorClientBase):
    """Schema for creating a new advisor-client association."""
    pass


class AdvisorClientUpdate(BaseModel):
    """Schema for updating an advisor-client association."""
    status: Optional[str] = Field(None, description="Association status: active, inactive, suspended")


class AdvisorClientResponse(AdvisorClientBase):
    """Schema for advisor-client association response."""
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

class AdvisorClientWithUsers(AdvisorClientResponse):
    """Schema for advisor-client association with user details."""
    advisor_name: Optional[str] = None
    advisor_email: Optional[str] = None
    client_name: Optional[str] = None
    client_email: Optional[str] = None

