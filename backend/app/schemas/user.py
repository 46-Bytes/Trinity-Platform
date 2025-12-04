"""
Pydantic schemas for User model validation and serialization.
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class UserBase(BaseModel):
    """Base user schema with common fields."""
    email: EmailStr
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    nickname: Optional[str] = None
    picture: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a new user."""
    auth0_id: str = Field(..., description="Auth0 user ID")
    email_verified: bool = False


class UserResponse(UserBase):
    """Schema for user response."""
    id: UUID
    auth0_id: str
    email_verified: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True



