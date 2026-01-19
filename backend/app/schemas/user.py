"""
Pydantic schemas for User model validation and serialization.
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class UserBase(BaseModel):
    """Base user schema with common fields."""
    email: EmailStr
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    nickname: Optional[str] = None
    picture: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a new user."""
    auth0_id: str = Field(..., description="Auth0 user ID")
    email_verified: bool = False


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """Schema for user response."""
    id: UUID
    auth0_id: str
    email_verified: bool
    is_active: bool
    role: str  # User role as string (e.g., "client", "advisor", "admin")
    firm_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    
    model_config = {"from_attributes": True}


class UserFileResponse(BaseModel):
    """Schema for user file information."""
    id: UUID
    file_name: str
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    file_extension: Optional[str] = None
    created_at: datetime
    description: Optional[str] = None
    question_field_name: Optional[str] = None


class UserDiagnosticResponse(BaseModel):
    """Schema for diagnostic report information."""
    id: UUID
    engagement_id: UUID
    status: str
    overall_score: Optional[float] = None
    report_url: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class UserDetailResponse(UserResponse):
    """Schema for detailed user response with files, diagnostics, and engagement count."""
    files: List[UserFileResponse] = Field(default_factory=list, description="Files uploaded by the user")
    diagnostics: List[UserDiagnosticResponse] = Field(default_factory=list, description="Diagnostic reports generated for the user")
    engagements_count: int = Field(default=0, description="Number of engagements where user is the client")


class PaginatedUsersResponse(BaseModel):
    """Schema for paginated users response."""
    users: List[UserResponse] = Field(..., description="List of users")
    total: int = Field(..., description="Total number of users matching the query")
    skip: int = Field(..., description="Number of records skipped")
    limit: int = Field(..., description="Maximum number of records per page")



