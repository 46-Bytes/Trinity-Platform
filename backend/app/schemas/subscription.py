"""
Subscription schemas for API requests/responses.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime, timedelta
from uuid import UUID


# ==================== Subscription Schemas ====================

class SubscriptionCreate(BaseModel):
    """Schema for creating a new subscription."""
    plan_name: str = Field(..., min_length=1, max_length=50, description="Subscription plan name (e.g., 'professional', 'enterprise')")
    seat_count: int = Field(..., ge=1, description="Number of seats in the subscription")
    billing_period: str = Field(..., description="Billing period: 'monthly' or 'annual'")
    price: float = Field(..., ge=0, description="Subscription price")
    currency: Optional[str] = Field(default="USD", max_length=10, description="Currency code (e.g., 'USD', 'EUR')")


class SubscriptionUpdate(BaseModel):
    """Schema for updating a subscription."""
    plan_name: Optional[str] = Field(None, min_length=1, max_length=50)
    seat_count: Optional[int] = Field(None, ge=1)
    monthly_price: Optional[float] = Field(None, ge=0)
    status: Optional[str] = Field(None, max_length=20)

class SubscriptionResponse(BaseModel):
    """Schema for subscription response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    plan_name: str
    seat_count: int
    monthly_price: float
    status: str
    created_at: datetime
    updated_at: datetime

