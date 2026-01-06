"""
Subscription management API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta

from ..database import get_db
from ..models.user import User, UserRole
from ..models.subscription import Subscription
from ..services.role_check import get_current_user_from_token
from ..schemas.subscription import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionResponse,
)

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


# ==================== Subscription CRUD ====================

@router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    subscription_data: SubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Create a new subscription.
    
    Only super admins can create subscriptions.
    Subscriptions are independent and can be assigned to firms later.
    """
    # Check permissions - only super admins can create subscriptions
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Only super admins can create subscriptions")
    
    try:
        # Calculate monthly price based on billing period
        if subscription_data.billing_period.lower() == "annual":
            # Annual price divided by 12 for monthly equivalent
            monthly_price = subscription_data.price / 12
        else:
            monthly_price = subscription_data.price

        subscription = Subscription(
            plan_name=subscription_data.plan_name,
            seat_count=subscription_data.seat_count,
            monthly_price=monthly_price,
            status="active",
        )
        
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        
        return SubscriptionResponse.model_validate(subscription)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create subscription: {str(e)}"
        )


@router.get("", response_model=List[SubscriptionResponse])
async def list_subscriptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    firm_id: Optional[UUID] = Query(None, description="Filter by firm ID"),
):
    """
    List subscriptions.
    
    - Super Admin: See all subscriptions
    - Others: Cannot list subscriptions
    """
    # Check permissions
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only super admins can view subscriptions")
    
    query = db.query(Subscription)
    
    # Filter by firm_id if provided (check via Firm table)
    if firm_id:
        from ..models.firm import Firm
        firm = db.query(Firm).filter(Firm.id == firm_id).first()
        if firm and firm.subscription_id:
            query = query.filter(Subscription.id == firm.subscription_id)
        else:
            # Firm doesn't exist or has no subscription, return empty
            query = query.filter(Subscription.id == None)
    
    subscriptions = query.order_by(Subscription.created_at.desc()).offset(skip).limit(limit).all()
    return [SubscriptionResponse.model_validate(sub) for sub in subscriptions]


@router.get("/{subscription_id}", response_model=SubscriptionResponse)
async def get_subscription(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """Get subscription details by ID."""
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    # Check permissions
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can view subscription details"
        )
    
    return SubscriptionResponse.model_validate(subscription)


@router.patch("/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: UUID,
    subscription_data: SubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """Update subscription details."""
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    # Check permissions
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can update subscriptions"
        )
    
    # Update fields
    update_data = subscription_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(subscription, field, value)
    
    db.commit()
    db.refresh(subscription)
    
    return SubscriptionResponse.model_validate(subscription)


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """Delete a subscription."""
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    # Check permissions
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can delete subscriptions"
        )
    
    # Check if subscription is assigned to a firm (via Firm table)
    from ..models.firm import Firm
    firm_using_subscription = db.query(Firm).filter(Firm.subscription_id == subscription_id).first()
    if firm_using_subscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete subscription that is assigned to firm {firm_using_subscription.id}. Unassign it first."
        )
    
    db.delete(subscription)
    db.commit()
    
    return None

