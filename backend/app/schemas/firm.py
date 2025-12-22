"""
Firm schemas for API requests/responses.
"""
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import Optional, List
from datetime import datetime
from uuid import UUID


# ==================== Firm Schemas ====================

class FirmCreate(BaseModel):
    """Schema for creating a new firm."""
    firm_name: str = Field(..., min_length=2, max_length=255, description="Name of the firm/organization")
    seat_count: int = Field(default=5, ge=5, description="Number of seats (minimum 5)")
    billing_email: Optional[EmailStr] = Field(None, description="Email for billing notifications")


class FirmUpdate(BaseModel):
    """Schema for updating a firm."""
    firm_name: Optional[str] = Field(None, min_length=2, max_length=255)
    billing_email: Optional[EmailStr] = None
    is_active: Optional[bool] = None


class FirmResponse(BaseModel):
    """Schema for firm response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    firm_name: str
    firm_admin_id: UUID
    subscription_plan: Optional[str] = None
    seat_count: int
    seats_used: int
    billing_email: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class FirmDetailResponse(FirmResponse):
    """Schema for firm detail with additional information."""
    # Can be extended with advisor list, engagement count, etc.
    pass


# ==================== Advisor Schemas ====================

class FirmAdvisorAdd(BaseModel):
    """Schema for adding an advisor to a firm."""
    email: EmailStr = Field(..., description="Email address of the advisor")
    name: str = Field(..., min_length=1, max_length=255, description="Full name of the advisor")


class FirmClientAdd(BaseModel):
    """Schema for adding a client to a firm."""
    email: EmailStr = Field(..., description="Email address of the client")
    name: Optional[str] = Field(None, max_length=255, description="Full name of the client")
    given_name: Optional[str] = Field(None, max_length=255, description="First name of the client")
    family_name: Optional[str] = Field(None, max_length=255, description="Last name of the client")


class FirmClientResponse(BaseModel):
    """Schema for client response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    email: str
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    role: str
    is_active: bool
    firm_id: Optional[UUID] = None
    created_at: datetime


class FirmAdvisorResponse(BaseModel):
    """Schema for advisor response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    email: str
    name: Optional[str] = None
    role: str
    is_active: bool
    firm_id: Optional[UUID] = None
    created_at: datetime
    last_login: Optional[datetime] = None


class FirmAdvisorListResponse(BaseModel):
    """Schema for list of advisors."""
    advisors: List[FirmAdvisorResponse]
    total: int
    seats_used: int
    seats_available: int


# ==================== Engagement Schemas ====================

class FirmEngagementResponse(BaseModel):
    """Schema for engagement in firm context."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    engagement_name: str
    business_name: Optional[str] = None
    client_id: UUID
    client_name: Optional[str] = None
    primary_advisor_id: UUID
    primary_advisor_name: Optional[str] = None
    secondary_advisor_ids: Optional[List[UUID]] = []
    status: str
    created_at: datetime
    updated_at: datetime


# ==================== Subscription Schemas ====================

class SubscriptionResponse(BaseModel):
    """Schema for subscription response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    firm_id: UUID
    plan_name: str
    seat_count: int
    monthly_price: float
    status: str
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    cancelled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class SeatUpdateRequest(BaseModel):
    """Schema for updating seat count."""
    seat_count: int = Field(..., ge=5, description="New seat count (minimum 5)")


# ==================== Reassignment Schemas ====================

class EngagementReassignRequest(BaseModel):
    """Schema for reassigning an engagement."""
    new_primary_advisor_id: UUID = Field(..., description="ID of the new primary advisor")
    engagement_id: UUID = Field(..., description="ID of the engagement to reassign")


