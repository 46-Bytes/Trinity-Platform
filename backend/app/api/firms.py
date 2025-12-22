"""
Firm management API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from ..database import get_db
from ..models.user import User, UserRole
from ..models.firm import Firm
from ..models.subscription import Subscription
from ..services.role_check import get_current_user_from_token
from ..services.firm_service import get_firm_service, FirmService
from ..services.firm_permissions import (
    can_manage_firm_users,
    can_view_firm_engagements,
    can_modify_subscription,
    can_assign_advisors
)
from ..schemas.firm import (
    FirmCreate,
    FirmUpdate,
    FirmResponse,
    FirmDetailResponse,
    FirmAdvisorAdd,
    FirmAdvisorResponse,
    FirmAdvisorListResponse,
    FirmEngagementResponse,
    SubscriptionResponse,
    SeatUpdateRequest,
    EngagementReassignRequest,
)

router = APIRouter(prefix="/api/firms", tags=["firms"])


# ==================== Firm CRUD ====================

@router.post("", response_model=FirmResponse, status_code=status.HTTP_201_CREATED)
async def create_firm(
    firm_data: FirmCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Create a new firm account.
    
    Only advisors (solo) or super admins can create firms.
    The creator becomes the Firm Admin.
    """
    # Check permissions
    if current_user.role not in [UserRole.ADVISOR, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only advisors can create firm accounts"
        )
    
    # Check if user is already in a firm
    if current_user.firm_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already part of a firm"
        )
    
    try:
        firm_service = get_firm_service(db)
        firm = firm_service.create_firm(
            firm_name=firm_data.firm_name,
            firm_admin_id=current_user.id,
            seat_count=firm_data.seat_count,
            billing_email=firm_data.billing_email
        )
        
        return FirmResponse.model_validate(firm)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("", response_model=List[FirmResponse])
async def list_firms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    List firms.
    
    - Super Admin/Admin: See all firms
    - Firm Admin: See their own firm
    - Others: Cannot list firms
    """
    query = db.query(Firm)
    
    if current_user.role == UserRole.SUPER_ADMIN or current_user.role == UserRole.ADMIN:
        # Admins see all firms
        pass
    elif current_user.role == UserRole.FIRM_ADMIN:
        # Firm Admin sees only their firm
        query = query.filter(Firm.id == current_user.firm_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to list firms"
        )
    
    firms = query.order_by(Firm.created_at.desc()).offset(skip).limit(limit).all()
    return [FirmResponse.model_validate(firm) for firm in firms]


@router.get("/{firm_id}", response_model=FirmDetailResponse)
async def get_firm(
    firm_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """Get firm details."""
    firm = db.query(Firm).filter(Firm.id == firm_id).first()
    
    if not firm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Firm not found"
        )
    
    # Check access
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        if current_user.firm_id != firm_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
    
    return FirmDetailResponse.model_validate(firm)


@router.patch("/{firm_id}", response_model=FirmResponse)
async def update_firm(
    firm_id: UUID,
    firm_data: FirmUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """Update firm details."""
    firm = db.query(Firm).filter(Firm.id == firm_id).first()
    
    if not firm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Firm not found"
        )
    
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        if not can_manage_firm_users(current_user, firm_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Firm Admins can update firm details"
            )
    
    # Update fields
    update_data = firm_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(firm, field, value)
    
    db.commit()
    db.refresh(firm)
    
    return FirmResponse.model_validate(firm)


# ==================== Advisor Management ====================

@router.post("/{firm_id}/advisors", response_model=FirmAdvisorResponse, status_code=status.HTTP_201_CREATED)
async def add_advisor(
    firm_id: UUID,
    advisor_data: FirmAdvisorAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """Add an advisor to a firm."""
    try:
        firm_service = get_firm_service(db)
        advisor = firm_service.add_advisor_to_firm(
            firm_id=firm_id,
            advisor_email=advisor_data.email,
            advisor_name=advisor_data.name,
            added_by_user_id=current_user.id
        )
        
        return FirmAdvisorResponse.model_validate(advisor)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{firm_id}/advisors/{advisor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_advisor(
    firm_id: UUID,
    advisor_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """Remove an advisor from a firm."""
    try:
        firm_service = get_firm_service(db)
        firm_service.remove_advisor_from_firm(
            firm_id=firm_id,
            advisor_id=advisor_id,
            removed_by_user_id=current_user.id
        )
        
        return None
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{firm_id}/advisors", response_model=FirmAdvisorListResponse)
async def list_advisors(
    firm_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """List all advisors in a firm."""
    try:
        firm_service = get_firm_service(db)
        advisors = firm_service.get_firm_advisors(firm_id, current_user)
        
        firm = db.query(Firm).filter(Firm.id == firm_id).first()
        if not firm:
            raise HTTPException(status_code=404, detail="Firm not found")
        
        return FirmAdvisorListResponse(
            advisors=[FirmAdvisorResponse.model_validate(a) for a in advisors],
            total=len(advisors),
            seats_used=firm.seats_used,
            seats_available=firm.seat_count - firm.seats_used
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


# ==================== Engagement Management ====================

@router.get("/{firm_id}/engagements", response_model=List[FirmEngagementResponse])
async def list_firm_engagements(
    firm_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """List all engagements for a firm."""
    try:
        firm_service = get_firm_service(db)
        engagements = firm_service.get_firm_engagements(firm_id, current_user)
        
        # Apply pagination
        paginated_engagements = engagements[skip:skip + limit]
        
        # Build response with client and advisor names
        result = []
        for engagement in paginated_engagements:
            # Get client name
            client = db.query(User).filter(User.id == engagement.client_id).first()
            client_name = client.name or client.email if client else None
            
            # Get primary advisor name
            primary_advisor = db.query(User).filter(User.id == engagement.primary_advisor_id).first()
            primary_advisor_name = primary_advisor.name or primary_advisor.email if primary_advisor else None
            
            engagement_dict = {
                **engagement.__dict__,
                "client_name": client_name,
                "primary_advisor_name": primary_advisor_name,
            }
            result.append(FirmEngagementResponse(**engagement_dict))
        
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


@router.post("/{firm_id}/engagements/{engagement_id}/reassign", response_model=FirmEngagementResponse)
async def reassign_engagement(
    firm_id: UUID,
    engagement_id: UUID,
    reassign_data: EngagementReassignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """Reassign an engagement to a different advisor within the firm."""
    try:
        firm_service = get_firm_service(db)
        engagement = firm_service.reassign_engagement(
            engagement_id=engagement_id,
            new_primary_advisor_id=reassign_data.new_primary_advisor_id,
            reassigned_by=current_user.id
        )
        
        # Get client and advisor names
        client = db.query(User).filter(User.id == engagement.client_id).first()
        client_name = client.name or client.email if client else None
        
        primary_advisor = db.query(User).filter(User.id == engagement.primary_advisor_id).first()
        primary_advisor_name = primary_advisor.name or primary_advisor.email if primary_advisor else None
        
        engagement_dict = {
            **engagement.__dict__,
            "client_name": client_name,
            "primary_advisor_name": primary_advisor_name,
        }
        
        return FirmEngagementResponse(**engagement_dict)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ==================== Subscription Management ====================

@router.get("/{firm_id}/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    firm_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """Get firm subscription details."""
    firm = db.query(Firm).filter(Firm.id == firm_id).first()
    
    if not firm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Firm not found"
        )
    
    # Check access
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        if not can_modify_subscription(current_user, firm_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Firm Admins can view subscription details"
            )
    
    subscription = db.query(Subscription).filter(Subscription.firm_id == firm_id).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    return SubscriptionResponse.model_validate(subscription)


@router.patch("/{firm_id}/seats", response_model=FirmResponse)
async def update_seats(
    firm_id: UUID,
    seat_data: SeatUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """Update firm seat count (triggers billing update)."""
    try:
        firm_service = get_firm_service(db)
        firm = firm_service.update_seat_count(
            firm_id=firm_id,
            new_seat_count=seat_data.seat_count,
            updated_by=current_user.id
        )
        
        return FirmResponse.model_validate(firm)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ==================== Firm Statistics ====================

@router.get("/{firm_id}/stats")
async def get_firm_stats(
    firm_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """Get firm statistics."""
    firm = db.query(Firm).filter(Firm.id == firm_id).first()
    
    if not firm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Firm not found"
        )
    
    # Check access
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        if not can_view_firm_engagements(current_user, firm_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
    
    from sqlalchemy import func
    from ..models.engagement import Engagement
    from ..models.diagnostic import Diagnostic
    from ..models.task import Task
    
    # Count engagements
    engagements_count = db.query(func.count(Engagement.id)).filter(
        Engagement.firm_id == firm_id
    ).scalar() or 0
    
    # Count active engagements
    active_engagements = db.query(func.count(Engagement.id)).filter(
        Engagement.firm_id == firm_id,
        Engagement.status == "active"
    ).scalar() or 0
    
    # Count diagnostics
    diagnostics_count = db.query(func.count(Diagnostic.id)).join(
        Engagement
    ).filter(
        Engagement.firm_id == firm_id
    ).scalar() or 0
    
    # Count tasks
    tasks_count = db.query(func.count(Task.id)).join(
        Engagement
    ).filter(
        Engagement.firm_id == firm_id
    ).scalar() or 0
    
    # Count advisors
    advisors_count = firm.seats_used
    
    return {
        "firm_id": str(firm_id),
        "firm_name": firm.firm_name,
        "advisors_count": advisors_count,
        "seats_used": firm.seats_used,
        "seats_available": firm.seat_count - firm.seats_used,
        "engagements_count": engagements_count,
        "active_engagements": active_engagements,
        "diagnostics_count": diagnostics_count,
        "tasks_count": tasks_count,
    }


