"""
Engagement CRUD API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, text
from typing import List, Optional
from uuid import UUID
import logging

from ..database import get_db
from ..models.engagement import Engagement
from ..models.user import User, UserRole
from ..models.diagnostic import Diagnostic
from ..models.task import Task
from ..models.note import Note
from ..models.adv_client import AdvisorClient
from ..schemas.engagement import (
    EngagementCreate,
    EngagementUpdate,
    EngagementResponse,
    EngagementListItem,
    EngagementDetail,
)
from ..services.role_check import get_current_user_from_token, check_engagement_access

# Configure logger for this module
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/engagements", tags=["engagements"])


@router.post("", response_model=EngagementResponse, status_code=status.HTTP_201_CREATED)
async def create_engagement(
    engagement_data: EngagementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Create a new engagement.
    
    Only advisors, admins, super admins, firm admins, and firm advisors can create engagements.
    """
    # Check permissions
    if current_user.role not in [UserRole.ADVISOR, UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.FIRM_ADMIN, UserRole.FIRM_ADVISOR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only advisors and admins can create engagements."
        )
    
    # Verify client exists
    client = db.query(User).filter(
        User.id == engagement_data.client_id,
        User.role == UserRole.CLIENT
    ).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found or invalid client ID."
        )
    
    # Verify primary advisor exists (can be ADVISOR, FIRM_ADVISOR, or FIRM_ADMIN)
    primary_advisor = db.query(User).filter(
        User.id == engagement_data.primary_advisor_id,
        User.role.in_([UserRole.ADVISOR, UserRole.FIRM_ADVISOR, UserRole.FIRM_ADMIN])
    ).first()
    if not primary_advisor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Primary advisor not found or invalid advisor ID."
        )
    
    # Verify secondary advisors if provided (can be ADVISOR, FIRM_ADVISOR, or FIRM_ADMIN)
    if engagement_data.secondary_advisor_ids:
        secondary_advisors = db.query(User).filter(
            User.id.in_(engagement_data.secondary_advisor_ids),
            User.role.in_([UserRole.ADVISOR, UserRole.FIRM_ADVISOR, UserRole.FIRM_ADMIN])
        ).all()
        if len(secondary_advisors) != len(engagement_data.secondary_advisor_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more secondary advisors not found or invalid."
            )
    
    # Auto-set firm_id for firm_admin and firm_advisor users if not provided
    firm_id = engagement_data.firm_id
    if not firm_id and current_user.role in [UserRole.FIRM_ADMIN, UserRole.FIRM_ADVISOR]:
        firm_id = current_user.firm_id
    
    # Create engagement
    engagement = Engagement(
        engagement_name=engagement_data.engagement_name,
        business_name=engagement_data.business_name,
        industry=engagement_data.industry,
        description=engagement_data.description,
        tool=engagement_data.tool,
        status=engagement_data.status,
        client_id=engagement_data.client_id,
        primary_advisor_id=engagement_data.primary_advisor_id,
        firm_id=firm_id,
        secondary_advisor_ids=engagement_data.secondary_advisor_ids or [],
    )
    
    db.add(engagement)
    db.commit()
    db.refresh(engagement)
    
    # Create tool for engagement if tool is specified
    if engagement_data.tool:
        import sys
        from pathlib import Path
        # Add backend directory to path to import tool_service
        backend_path = Path(__file__).parent.parent.parent
        if str(backend_path) not in sys.path:
            sys.path.insert(0, str(backend_path))
        
        from tool_service.tool_selector import create_tool_for_engagement
        try:
            await create_tool_for_engagement(
                db=db,
                engagement_id=engagement.id,
                tool_type=engagement_data.tool,
                created_by_user_id=current_user.id
            )
            db.commit()  # Commit tool creation
        except Exception as e:
            # Log error but don't fail engagement creation
            print(f"Warning: Failed to create tool for engagement: {str(e)}")
    
    # Create response using Pydantic model_validate (handles SQLAlchemy models properly)
    response = EngagementResponse.model_validate(engagement)
    # Add client_name and advisor_name (not in model, but needed for response)
    response.client_name = client.name or client.email or client.nickname if client else None
    response.advisor_name = primary_advisor.name or primary_advisor.email or primary_advisor.nickname if primary_advisor else None
    
    return response


@router.get("", response_model=List[EngagementListItem])
async def list_engagements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token),
    firm_id: Optional[UUID] = Query(None, description="Filter by firm ID (for superadmin viewing firm engagements)"),
    status_filter: Optional[str] = Query(None, description="Filter by status (active, paused, completed, archived)"),
    search: Optional[str] = Query(None, description="Search by engagement name or business name"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
):
    """
    List engagements accessible to the current user.
    
    Returns engagements based on user role:
    - Super Admin: 
      * If firm_id is provided: engagements for that firm only
      * If firm_id is NOT provided: engagements without firm_id only
    - Admin: Engagements without firm_id only
    - Firm Admin: All engagements within their firm
    - Advisor/Firm Advisor: Engagements where they are primary or secondary advisor
    - Client: Engagements where they are the client
    """
    # Build base query
    query = db.query(Engagement)
    
    if current_user.role == UserRole.SUPER_ADMIN:
        if firm_id:
            query = query.filter(Engagement.firm_id == firm_id)
        else:
            query = query.filter(Engagement.firm_id.is_(None))
    elif current_user.role == UserRole.ADMIN:
        # Admin only sees engagements without firm_id
        query = query.filter(Engagement.firm_id.is_(None))
    elif current_user.role == UserRole.FIRM_ADMIN:
        # Firm Admin sees all engagements within their firm
        if current_user.firm_id:
            query = query.filter(Engagement.firm_id == current_user.firm_id)
        else:
            # If firm_admin has no firm_id, return empty result
            query = query.filter(False)
    elif current_user.role in [UserRole.ADVISOR, UserRole.FIRM_ADVISOR]:
        # Advisors and firm advisors see engagements where they are primary or secondary advisor
        query = query.filter(
            or_(
                Engagement.primary_advisor_id == current_user.id,
                text("secondary_advisor_ids @> ARRAY[:user_id]::uuid[]").bindparams(user_id=current_user.id)
            )
        )
    elif current_user.role == UserRole.CLIENT:
        query = query.filter(Engagement.client_id == current_user.id)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user role."
        )
    
    if status_filter:
        query = query.filter(Engagement.status == status_filter)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Engagement.engagement_name.ilike(search_pattern),
                Engagement.business_name.ilike(search_pattern)
            )
        )
    
    total = query.count()
    
    engagements = query.order_by(Engagement.created_at.desc()).offset(skip).limit(limit).all()
    
    result = []
    for engagement in engagements:
        diagnostics_count = db.query(func.count(Diagnostic.id)).filter(
            Diagnostic.engagement_id == engagement.id
        ).scalar() or 0
        
        tasks_count = db.query(func.count(Task.id)).filter(
            Task.engagement_id == engagement.id
        ).scalar() or 0
        
        pending_tasks_count = db.query(func.count(Task.id)).filter(
            Task.engagement_id == engagement.id,
            Task.status == "pending"
        ).scalar() or 0
        
        notes_count = db.query(func.count(Note.id)).filter(
            Note.engagement_id == engagement.id
        ).scalar() or 0
        
        from app.models.media import diagnostic_media, Media
        documents_count = db.query(func.count(Media.id)).join(
            diagnostic_media, Media.id == diagnostic_media.c.media_id
        ).join(
            Diagnostic, diagnostic_media.c.diagnostic_id == Diagnostic.id
        ).filter(
            Diagnostic.engagement_id == engagement.id,
            Media.is_active == True,
            Media.deleted_at.is_(None)
        ).scalar() or 0
        
        completed_diagnostic = db.query(Diagnostic).filter(
            Diagnostic.engagement_id == engagement.id,
            Diagnostic.status == "completed"
        ).first()
        
        effective_status = engagement.status
        if completed_diagnostic and engagement.status != "completed":
            engagement.status = "completed"
            if not engagement.completed_at:
                from datetime import datetime
                engagement.completed_at = datetime.utcnow()
            db.commit()
            effective_status = "completed"
        
        # Get client name
        client = None
        client_name = None
        if engagement.client_id:
            try:
                client = db.query(User).filter(User.id == engagement.client_id).first()
                if client:
                    client_name = client.name or client.email or client.nickname
                    if not client_name:
                        logger.warning(f"Client {engagement.client_id} found but has no name, email, or nickname")
                else:
                    logger.warning(f"Client with id {engagement.client_id} not found in database")
            except Exception as e:
                logger.error(f"Error fetching client {engagement.client_id}: {str(e)}")
        
        # Get primary advisor name
        primary_advisor = None
        advisor_name = None
        if engagement.primary_advisor_id:
            try:
                primary_advisor = db.query(User).filter(User.id == engagement.primary_advisor_id).first()
                if primary_advisor:
                    advisor_name = primary_advisor.name or primary_advisor.email or primary_advisor.nickname
            except Exception as e:
                logger.error(f"Error fetching advisor {engagement.primary_advisor_id}: {str(e)}")
        
        engagement_dict = {
            **engagement.__dict__,
            "client_name": client_name,
            "advisor_name": advisor_name,
            "status": effective_status,  # Use computed status
            "diagnostics_count": diagnostics_count,
            "tasks_count": tasks_count,
            "pending_tasks_count": pending_tasks_count,
            "notes_count": notes_count,
            "documents_count": documents_count,
        }
        result.append(EngagementListItem(**engagement_dict))
    
    return result


@router.get("/user-role-data")
async def get_user_role_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token),
):
    """
    Get user role and associated clients/advisors.
    
    Returns:
    - For advisors: List of clients they can work with
    - For clients: List of advisors they can work with
    - For admins: Both lists
    """
    if current_user.role in [UserRole.ADVISOR, UserRole.FIRM_ADVISOR]:
        # Get only clients that are associated with this advisor
        # Get all active associations for this advisor
        associations = db.query(AdvisorClient).filter(
            AdvisorClient.advisor_id == current_user.id,
            AdvisorClient.status == 'active'
        ).all()
        
        associated_client_ids = [assoc.client_id for assoc in associations]
        
        if associated_client_ids:
            clients = db.query(User).filter(
                User.id.in_(associated_client_ids),
                User.role == UserRole.CLIENT,
                User.is_active == True
            ).all()
        else:
            clients = []
        
        return {
            "user_role": "advisor",
            "clients": [
                {"id": str(client.id), "name": client.name or client.email}
                for client in clients
            ]
        }
    
    elif current_user.role == UserRole.FIRM_ADMIN:
        # Firm Admin gets all clients from the firm's clients array
        # and all advisors in their firm
        from ..models.firm import Firm
        
        firm = db.query(Firm).filter(Firm.id == current_user.firm_id).first()
        client_ids_list = firm.clients if firm and firm.clients else []
        
        if client_ids_list:
            clients = db.query(User).filter(
                User.id.in_(client_ids_list),
                User.role == UserRole.CLIENT,
                User.is_active == True
            ).all()
        else:
            clients = []
        
        advisors = db.query(User).filter(
            User.firm_id == current_user.firm_id,
            User.role.in_([UserRole.FIRM_ADMIN, UserRole.FIRM_ADVISOR]),
            User.is_active == True
        ).all()
        
        return {
            "user_role": "firm_admin",
            "clients": [
                {"id": str(client.id), "name": client.name or client.email}
                for client in clients
            ],
            "advisors": [
                {"id": str(advisor.id), "name": advisor.name or advisor.email}
                for advisor in advisors
            ]
        }
    
    elif current_user.role == UserRole.FIRM_ADVISOR:
        # Firm Advisor gets clients from the firm's clients array
        # and advisors in their firm
        from ..models.firm import Firm
        
        firm = db.query(Firm).filter(Firm.id == current_user.firm_id).first()
        client_ids_list = firm.clients if firm and firm.clients else []
        
        if client_ids_list:
            clients = db.query(User).filter(
                User.id.in_(client_ids_list),
                User.role == UserRole.CLIENT,
                User.is_active == True
            ).all()
        else:
            clients = []
        
        advisors = db.query(User).filter(
            User.firm_id == current_user.firm_id,
            User.role.in_([UserRole.FIRM_ADMIN, UserRole.FIRM_ADVISOR]),
            User.is_active == True
        ).all()
        
        return {
            "user_role": "firm_advisor",
            "clients": [
                {"id": str(client.id), "name": client.name or client.email}
                for client in clients
            ],
            "advisors": [
                {"id": str(advisor.id), "name": advisor.name or advisor.email}
                for advisor in advisors
            ]
        }
    
    elif current_user.role == UserRole.CLIENT:
        # Get all advisors (for now - can be filtered by firm later)
        advisors = db.query(User).filter(
            User.role == UserRole.ADVISOR,
            User.is_active == True
        ).all()
        
        return {
            "user_role": "client",
            "advisors": [
                {"id": str(advisor.id), "name": advisor.name or advisor.email}
                for advisor in advisors
            ]
        }
    
    elif current_user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        clients = db.query(User).filter(User.role == UserRole.CLIENT,User.is_active == True,User.firm_id.is_(None)).all()
        advisors = db.query(User).filter( User.role == UserRole.ADVISOR,User.is_active == True).all()
        
        return {
            "user_role": "admin",
            "clients": [
                {"id": str(client.id), "name": client.name or client.email}
                for client in clients
            ],
            "advisors": [
                {"id": str(advisor.id), "name": advisor.name or advisor.email}
                for advisor in advisors
            ]
        }
    
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user role."
        )


@router.get("/{engagement_id}", response_model=EngagementDetail)
async def get_engagement(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token),
):
    """
    Get a specific engagement by ID.
    
    User must have access to the engagement based on their role.
    """
    engagement = db.query(Engagement).filter(Engagement.id == engagement_id).first()
    
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found."
        )
    
    # Check access
    if not check_engagement_access(engagement, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this engagement."
        )
    
    # Populate client_name and advisor_name for response
    client = db.query(User).filter(User.id == engagement.client_id).first()
    primary_advisor = db.query(User).filter(User.id == engagement.primary_advisor_id).first()
    engagement_dict = engagement.__dict__.copy()
    engagement_dict["client_name"] = client.name or client.email or client.nickname if client else None
    engagement_dict["advisor_name"] = primary_advisor.name or primary_advisor.email or primary_advisor.nickname if primary_advisor else None
    
    return EngagementDetail(**engagement_dict)


@router.patch("/{engagement_id}", response_model=EngagementResponse)
async def update_engagement(
    engagement_id: UUID,
    engagement_data: EngagementUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token),
):
    """
    Update an engagement.
    
    Only advisors and admins can update engagements.
    User must have access to the engagement.
    """
    engagement = db.query(Engagement).filter(Engagement.id == engagement_id).first()
    
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found."
        )
    
    # Check permissions
    if current_user.role not in [UserRole.ADVISOR, UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only advisors and admins can update engagements."
        )
    
    # Check access
    if not check_engagement_access(engagement, current_user, require_advisor=True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to update this engagement."
        )
    
    # Update fields
    update_data = engagement_data.model_dump(exclude_unset=True)
    
    # Handle secondary_advisor_ids separately if provided
    if "secondary_advisor_ids" in update_data:
        if update_data["secondary_advisor_ids"] is not None:
            # Verify all secondary advisors exist
            secondary_advisors = db.query(User).filter(
                User.id.in_(update_data["secondary_advisor_ids"]),
                User.role == UserRole.ADVISOR
            ).all()
            if len(secondary_advisors) != len(update_data["secondary_advisor_ids"]):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="One or more secondary advisors not found or invalid."
                )
    
    for field, value in update_data.items():
        setattr(engagement, field, value)
    
    db.commit()
    db.refresh(engagement)
    
    # Populate client_name and advisor_name for response
    client = db.query(User).filter(User.id == engagement.client_id).first()
    primary_advisor = db.query(User).filter(User.id == engagement.primary_advisor_id).first()
    engagement_dict = engagement.__dict__.copy()
    engagement_dict["client_name"] = client.name or client.email or client.nickname if client else None
    engagement_dict["advisor_name"] = primary_advisor.name or primary_advisor.email or primary_advisor.nickname if primary_advisor else None
    
    return EngagementResponse(**engagement_dict)


@router.delete("/{engagement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_engagement(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token),
):
    """
    Delete an engagement.
    
    Only super admins and admins can delete engagements.
    """
    engagement = db.query(Engagement).filter(Engagement.id == engagement_id).first()
    
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found."
        )
    
    # Check permissions - only admins can delete
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete engagements."
        )
    
    db.delete(engagement)
    db.commit()
    
    return None

