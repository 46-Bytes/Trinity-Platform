"""
Schemas for the self-service (SaaS) tier: signup, checkout, account and team.
"""
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import List, Optional
from datetime import datetime
from uuid import UUID


# ==================== Programs / plans ====================

class PlanResponse(BaseModel):
    """A purchasable self-service plan."""
    program: str = Field(..., description="value_builder or sale_ready")
    plan_name: str
    label: str
    description: str
    monthly_price: float
    currency: str
    seat_count: int
    team_member_limit: int = Field(..., description="Team members invitable, excluding the owner")
    features: List[str]


class ProgramsResponse(BaseModel):
    """The self-service catalogue."""
    plans: List[PlanResponse]
    signup_enabled: bool = Field(..., description="Whether self-service signup is currently open")


# ==================== Signup ====================

class SignupIntentCreate(BaseModel):
    """Details the owner supplies before being handed to Auth0."""
    email: EmailStr
    program: str = Field(..., description="Selected program: value_builder or sale_ready")
    name: Optional[str] = Field(None, max_length=255, description="Owner's full name")
    business_name: Optional[str] = Field(None, max_length=255)


class SignupIntentResponse(BaseModel):
    """Where to send the owner next."""
    intent_id: Optional[UUID] = Field(None, description="Null when the email is already registered")
    redirect_url: str = Field(..., description="URL to send the browser to (Auth0 signup, or login if already registered)")
    already_registered: bool = Field(
        default=False,
        description="True if an account exists for this email; the redirect points at login instead of signup",
    )


# ==================== Checkout / billing ====================

class CheckoutCreate(BaseModel):
    """Start payment for a program."""
    program: str = Field(..., description="Program to subscribe to: value_builder or sale_ready")


class CheckoutResponse(BaseModel):
    """Where the owner pays."""
    redirect_url: str
    subscription_id: UUID
    activated_immediately: bool = Field(
        default=False,
        description="True when the provider activated without a payment step (manual billing)",
    )
    engagement_id: Optional[UUID] = Field(None, description="Set when provisioning already completed")


class CancelSubscriptionRequest(BaseModel):
    """Cancel a self-service subscription."""
    at_period_end: bool = Field(default=True, description="Cancel at period end rather than immediately")


class SeatsResponse(BaseModel):
    """Seat usage on the owner's plan."""
    total: int
    team_member_limit: int
    team_members_used: int


class SubscriptionSummary(BaseModel):
    """Subscription fields the owner's UI needs."""
    id: UUID
    plan_name: str
    status: str
    program: Optional[str] = None
    seat_count: int
    monthly_price: Optional[float] = None
    provider: Optional[str] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: Optional[bool] = None
    cancelled_at: Optional[datetime] = None


class AccountResponse(BaseModel):
    """Everything the owner's frontend needs to route them correctly."""
    is_self_service: bool
    subscription: Optional[SubscriptionSummary] = None
    program: Optional[str] = None
    program_label: Optional[str] = None
    engagement_id: Optional[UUID] = None
    diagnostic_id: Optional[UUID] = None
    diagnostic_status: Optional[str] = None
    seats: SeatsResponse


# ==================== Team members ====================

class TeamMemberInvite(BaseModel):
    """Invite a team member to the owner's workspace."""
    email: EmailStr
    name: Optional[str] = Field(None, max_length=255)
    access_level: str = Field(default="viewer", description="collaborator or viewer")


class TeamMemberUpdate(BaseModel):
    """Change a team member's access level."""
    access_level: str = Field(..., description="collaborator or viewer")


class TeamMemberResponse(BaseModel):
    """A team member as shown to the owner."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    member_user_id: UUID
    email: str
    name: Optional[str] = None
    access_level: str
    status: str
    is_active: bool = True
    email_verified: bool = False
    invited_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None


class TeamListResponse(BaseModel):
    """The owner's team plus their seat usage."""
    members: List[TeamMemberResponse]
    seats: SeatsResponse
