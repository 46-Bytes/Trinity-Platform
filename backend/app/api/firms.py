"""
Firm management API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
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
    FirmClientAdd,
    FirmClientResponse,
    FirmEngagementResponse,
    SubscriptionResponse,
    SeatUpdateRequest,
    EngagementReassignRequest,
    AdvisorSuspendRequest,
)
from ..models.user import User
from sqlalchemy import func
from sqlalchemy import func
from ..models.engagement import Engagement
from ..models.diagnostic import Diagnostic
from ..models.task import Task
from ..models.note import Note
from ..models.bba import BBA
from ..models.media import Media
from ..models.conversation import Conversation
from ..models.adv_client import AdvisorClient

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
    - Advisors (solo): Can create firms and become the Firm Admin themselves
    - Super Admins: Can create firms and assign any user (without firm_id) as Firm Admin
    """
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admin can create firm accounts"
        )
    
    # Determine firm admin ID
    if current_user.role == UserRole.SUPER_ADMIN:
        # Super admin can select a different user as firm admin
        if firm_data.firm_admin_id:
            firm_admin_id = firm_data.firm_admin_id
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="firm_admin_id is required when creating firm as super admin"
            )
    
    try:
        firm_service = get_firm_service(db)
        # Use default seat_count of 5 if not provided (seat count is managed in subscription)
        seat_count = firm_data.seat_count if firm_data.seat_count else 5
        firm = firm_service.create_firm(
            firm_name=firm_data.firm_name,
            firm_admin_id=firm_admin_id,
            seat_count=seat_count,
            billing_email=firm_data.billing_email,
            subscription_id=firm_data.subscription_id
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
    
    if current_user.role == UserRole.SUPER_ADMIN:
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
    enriched_firms: List[FirmResponse] = []
    for firm in firms:
        # Get firm admin user
        admin_user = db.query(User).filter(User.id == firm.firm_admin_id).first()
        firm_admin_name = admin_user.name or admin_user.email if admin_user else None
        firm_admin_email = admin_user.email if admin_user else None

        # Count firm advisors (FIRM_ADVISOR only)
        advisors_count = db.query(func.count(User.id)).filter(
            User.firm_id == firm.id,
            User.role == UserRole.FIRM_ADVISOR,
        ).scalar() or 0

        # Count clients from firm's clients array (excluding deleted clients)
        if firm.clients:
            active_clients = db.query(User).filter(
                User.id.in_(firm.clients),
                User.role == UserRole.CLIENT,
                User.is_deleted == False
            ).count()
            clients_count = active_clients
        else:
            clients_count = 0

        enriched_firms.append(
            FirmResponse(
                id=firm.id,
                firm_name=firm.firm_name,
                firm_admin_id=firm.firm_admin_id,
                firm_admin_name=firm_admin_name,
                firm_admin_email=firm_admin_email,
                advisors_count=advisors_count,
                clients_count=clients_count,
                subscription_id=firm.subscription_id,
                subscription_plan=firm.subscription_plan,
                seat_count=firm.seat_count,
                seats_used=firm.seats_used,
                billing_email=firm.billing_email,
                is_active=firm.is_active,
                created_at=firm.created_at,
                updated_at=firm.updated_at,
            )
        )

    return enriched_firms


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
    # Only super admin can revoke/reactivate firms (change is_active)
    if 'is_active' in firm_data.model_dump(exclude_unset=True):
        if current_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super admins can revoke or reactivate firms"
            )
    elif current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
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
        
        # Calculate seats_used based on total Firm Advisors in the firm (active + suspended).
        # Firm Admin does NOT consume a billed seat.
        from sqlalchemy import func
        total_advisors = db.query(func.count(User.id)).filter(
            User.firm_id == firm_id,
            User.role == UserRole.FIRM_ADVISOR,
        ).scalar() or 0
        
        seats_used = total_advisors
        seats_available = max(0, firm.seat_count - seats_used)
        
        return FirmAdvisorListResponse(
            advisors=[FirmAdvisorResponse.model_validate(a) for a in advisors],
            total=len(advisors),
            seats_used=seats_used,
            seats_available=seats_available
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


@router.get("/{firm_id}/advisors/{advisor_id}/engagements")
async def get_advisor_engagements(
    firm_id: UUID,
    advisor_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """Get all engagements where an advisor is involved (for suspension warning)."""
    try:
        firm_service = get_firm_service(db)
        engagements_dict = firm_service.get_advisor_engagements(firm_id, advisor_id, current_user)
        
        # Build response with engagement details
        from ..models.user import User as UserModel
        
        result = {
            "primary": [],
            "secondary": []
        }
        
        for engagement in engagements_dict["primary"]:
            client = db.query(UserModel).filter(UserModel.id == engagement.client_id).first()
            engagement_dict = {
                "id": str(engagement.id),
                "engagement_name": engagement.engagement_name,
                "business_name": engagement.business_name,
                "client_id": str(engagement.client_id),
                "client_name": client.name or client.email if client else None,
                "status": engagement.status,
            }
            result["primary"].append(engagement_dict)
        
        for engagement in engagements_dict["secondary"]:
            client = db.query(UserModel).filter(UserModel.id == engagement.client_id).first()
            primary_advisor = db.query(UserModel).filter(UserModel.id == engagement.primary_advisor_id).first()
            engagement_dict = {
                "id": str(engagement.id),
                "engagement_name": engagement.engagement_name,
                "business_name": engagement.business_name,
                "client_id": str(engagement.client_id),
                "client_name": client.name or client.email if client else None,
                "primary_advisor_name": primary_advisor.name or primary_advisor.email if primary_advisor else None,
                "status": engagement.status,
            }
            result["secondary"].append(engagement_dict)
        
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


@router.post("/{firm_id}/advisors/{advisor_id}/suspend", response_model=FirmAdvisorResponse)
async def suspend_advisor(
    firm_id: UUID,
    advisor_id: UUID,
    suspend_data: AdvisorSuspendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Suspend an advisor.
    
    Requires reassignments dict if advisor is primary in any engagements.
    Format: {"engagement_id": "new_primary_advisor_id"}
    """
    try:
        # Convert string UUIDs to UUID objects
        reassignments = None
        if suspend_data.reassignments:
            reassignments = {
                UUID(eng_id): UUID(advisor_id) 
                for eng_id, advisor_id in suspend_data.reassignments.items()
            }
        
        firm_service = get_firm_service(db)
        advisor = firm_service.suspend_advisor(
            firm_id=firm_id,
            advisor_id=advisor_id,
            suspended_by_user_id=current_user.id,
            reassignments=reassignments
        )
        
        return FirmAdvisorResponse.model_validate(advisor)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{firm_id}/advisors/{advisor_id}/reactivate", response_model=FirmAdvisorResponse)
async def reactivate_advisor(
    firm_id: UUID,
    advisor_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """Reactivate a suspended advisor."""
    try:
        firm_service = get_firm_service(db)
        advisor = firm_service.reactivate_advisor(
            firm_id=firm_id,
            advisor_id=advisor_id,
            reactivated_by_user_id=current_user.id
        )
        
        return FirmAdvisorResponse.model_validate(advisor)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ==================== Client Management ====================

@router.post("/{firm_id}/clients", response_model=FirmClientResponse, status_code=status.HTTP_201_CREATED)
async def add_client(
    firm_id: UUID,
    client_data: FirmClientAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """Add a client to a firm."""
    try:
        firm_service = get_firm_service(db)
        client = firm_service.add_client_to_firm(
            firm_id=firm_id,
            email=client_data.email,
            first_name=client_data.first_name,
            last_name=client_data.last_name,
            added_by=current_user.id,
            primary_advisor_id=client_data.primary_advisor_id
        )
        
        return FirmClientResponse.model_validate(client)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{firm_id}/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_client(
    firm_id: UUID,
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """Soft delete a client from a firm (sets is_deleted=True)."""
    # Check permissions - only firm_admin or super_admin can remove clients
    if current_user.role not in [UserRole.FIRM_ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Only firm admins and super admins can remove clients")
    
    # Verify firm exists
    firm = db.query(Firm).filter(Firm.id == firm_id).first()
    if not firm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Firm not found")
    
    # Check if user has permission for this firm
    if current_user.role == UserRole.FIRM_ADMIN and current_user.firm_id != firm_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Insufficient permissions to remove clients from this firm")
    # Verify client exists and belongs to the firm
    client = db.query(User).filter(User.id == client_id,User.role == UserRole.CLIENT).first()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Client not found")
    # Verify client is in firm's clients array
    if not firm.clients or client.id not in firm.clients:
        raise HTTPException( status_code=status.HTTP_400_BAD_REQUEST,detail="Client is not associated with this firm")
    # Soft delete the client (set is_deleted=True, but keep in firm.clients array)
    client.is_deleted = True

    # Also deactivate any advisor-client associations for this client so they no longer appear as "active"
    db.query(AdvisorClient).filter(AdvisorClient.client_id == client.id,AdvisorClient.status == 'active').update({"status": "inactive"}, synchronize_session=False)

    # Delete all client-related work/data (engagements/diagnostics/tasks/notes/etc.)
    # We keep the client row (soft delete) but remove the related operational data.
    try:
        engagement_ids = [
            row[0] for row in db.query(Engagement.id).filter(Engagement.client_id == client.id).all()
        ]

        if engagement_ids:
            # Hard delete work items tied to the client's engagements
            db.query(Task).filter(Task.engagement_id.in_(engagement_ids)).delete(synchronize_session=False)
            db.query(Note).filter(Note.engagement_id.in_(engagement_ids)).delete(synchronize_session=False)
            db.query(Diagnostic).filter(Diagnostic.engagement_id.in_(engagement_ids)).delete(synchronize_session=False)
            db.query(BBA).filter(BBA.engagement_id.in_(engagement_ids)).delete(synchronize_session=False)

            # Soft delete engagements (keep row for history/audit, consistent with engagement delete API)
            db.query(Engagement).filter(Engagement.id.in_(engagement_ids)).update(
                {"is_deleted": True},
                synchronize_session=False
            )

        # Delete any client-created BBA projects that might not be tied to an engagement
        db.query(BBA).filter(BBA.created_by_user_id == client.id).delete(synchronize_session=False)

        # Delete uploaded files and chat history for this client
        db.query(Media).filter(Media.user_id == client.id).delete(synchronize_session=False)
        db.query(Conversation).filter(Conversation.user_id == client.id).delete(synchronize_session=False)

        db.commit()
    except Exception:
        db.rollback()
        raise
    
    return None


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
    
    # Get subscription via firm's subscription_id
    firm = db.query(Firm).filter(Firm.id == firm_id).first()
    subscription = None
    if firm and firm.subscription_id:
        subscription = db.query(Subscription).filter(Subscription.id == firm.subscription_id).first()
    
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
    
    
    # Count engagements (non-deleted only)
    engagements_count = db.query(func.count(Engagement.id)).filter(
        Engagement.firm_id == firm_id,
        Engagement.is_deleted == False
    ).scalar() or 0
    
    # Count active engagements (non-deleted and status active only)
    active_engagements = db.query(func.count(Engagement.id)).filter(
        Engagement.firm_id == firm_id,
        Engagement.status == "active",
        Engagement.is_deleted == False
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
    
    # Count total advisors (FIRM_ADVISOR only, NOT including Firm Admin)
    total_advisors = db.query(func.count(User.id)).filter(
        User.firm_id == firm_id,
        User.role == UserRole.FIRM_ADVISOR
    ).scalar() or 0
    
    # Count active advisors only (FIRM_ADVISOR only, NOT including Firm Admin)
    active_advisors_count = db.query(func.count(User.id)).filter(
        User.firm_id == firm_id,
        User.role == UserRole.FIRM_ADVISOR,
        User.is_active == True
    ).scalar() or 0
    
    # Seats used = total Firm Advisors in the firm (active + suspended).
    # Firm Admin does NOT consume a billed seat.
    seats_used = total_advisors
    seats_available = max(0, firm.seat_count - seats_used)
    
    return {
        "firm_id": str(firm_id),
        "firm_name": firm.firm_name,
        "advisors_count": total_advisors,  # Total advisors (active + suspended)
        "active_advisors_count": active_advisors_count,  # Only active advisors
        "seats_used": seats_used,  # Active advisors only (for billing)
        "seats_available": seats_available,
        "engagements_count": engagements_count,
        "active_engagements": active_engagements,
        "diagnostics_count": diagnostics_count,
        "tasks_count": tasks_count,
    }


