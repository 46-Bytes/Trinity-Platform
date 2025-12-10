"""
Engagement CRUD API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, text
from typing import List, Optional
from uuid import UUID
from jose import jwt

from ..database import get_db
from ..models.engagement import Engagement
from ..models.user import User, UserRole
from ..models.diagnostic import Diagnostic
from ..models.task import Task
from ..models.note import Note
from ..schemas.engagement import (
    EngagementCreate,
    EngagementUpdate,
    EngagementResponse,
    EngagementListItem,
    EngagementDetail,
)

router = APIRouter(prefix="/api/engagements", tags=["engagements"])


def get_current_user_from_token(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """
    Get current user from JWT token in Authorization header.
    Compatible with frontend token-based authentication.
    """
    
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Missing or invalid Authorization header."
        )
    
    token = auth_header.split(" ")[1]
    
    try:
        # Decode token to get user info
        payload = jwt.get_unverified_claims(token)
        auth0_id = payload.get("sub")
        
        if not auth0_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token. Missing 'sub' claim."
            )
        
        # Find user in database
        user = db.query(User).filter(User.auth0_id == auth0_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found."
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive."
            )
        
        return user
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {str(e)}"
        )


def check_engagement_access(
    engagement: Engagement,
    user: User,
    require_advisor: bool = False
) -> bool:
    """
    Check if user has access to an engagement.
    
    Rules:
    - Super Admin: Access to all
    - Admin: Access to all
    - Advisor: Access if they are primary_advisor_id or in secondary_advisor_ids
    - Client: Access if they are client_id
    
    Args:
        engagement: Engagement to check
        user: Current user
        require_advisor: If True, only advisors can access
        
    Returns:
        bool: True if user has access
    """
    # Super Admin and Admin have full access
    if user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        return True
    
    # Advisor access
    if user.role == UserRole.ADVISOR:
        if engagement.primary_advisor_id == user.id:
            return True
        if engagement.secondary_advisor_ids and user.id in engagement.secondary_advisor_ids:
            return True
        return False
    
    # Client access
    if user.role == UserRole.CLIENT:
        if require_advisor:
            return False
        return engagement.client_id == user.id
    
    return False


@router.post("", response_model=EngagementResponse, status_code=status.HTTP_201_CREATED)
async def create_engagement(
    engagement_data: EngagementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Create a new engagement.
    
    Only advisors, admins, and super admins can create engagements.
    """
    # Check permissions
    if current_user.role not in [UserRole.ADVISOR, UserRole.ADMIN, UserRole.SUPER_ADMIN]:
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
    
    # Verify primary advisor exists
    primary_advisor = db.query(User).filter(
        User.id == engagement_data.primary_advisor_id,
        User.role == UserRole.ADVISOR
    ).first()
    if not primary_advisor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Primary advisor not found or invalid advisor ID."
        )
    
    # Verify secondary advisors if provided
    if engagement_data.secondary_advisor_ids:
        secondary_advisors = db.query(User).filter(
            User.id.in_(engagement_data.secondary_advisor_ids),
            User.role == UserRole.ADVISOR
        ).all()
        if len(secondary_advisors) != len(engagement_data.secondary_advisor_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more secondary advisors not found or invalid."
            )
    
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
        firm_id=engagement_data.firm_id,
        secondary_advisor_ids=engagement_data.secondary_advisor_ids or [],
    )
    
    db.add(engagement)
    db.commit()
    db.refresh(engagement)
    
    # Populate client_name for response
    engagement_dict = engagement.__dict__.copy()
    engagement_dict["client_name"] = client.name or client.email
    
    return EngagementResponse(**engagement_dict)


@router.get("", response_model=List[EngagementListItem])
async def list_engagements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token),
    status_filter: Optional[str] = Query(None, description="Filter by status (active, paused, completed, archived)"),
    search: Optional[str] = Query(None, description="Search by engagement name or business name"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
):
    """
    List engagements accessible to the current user.
    
    Returns engagements based on user role:
    - Super Admin/Admin: All engagements
    - Advisor: Engagements where they are primary or secondary advisor
    - Client: Engagements where they are the client
    """
    # Build base query
    query = db.query(Engagement)
    
    # Apply role-based filtering
    if current_user.role == UserRole.SUPER_ADMIN or current_user.role == UserRole.ADMIN:
        # Admins see all
        pass
    elif current_user.role == UserRole.ADVISOR:
        # Advisors see engagements where they are involved
        # Use PostgreSQL array contains operator (@>) to check if user ID is in secondary_advisor_ids array
        # Using text() with bindparam for safe parameter binding
        query = query.filter(
            or_(
                Engagement.primary_advisor_id == current_user.id,
                text("secondary_advisor_ids @> ARRAY[:user_id]::uuid[]").bindparams(user_id=current_user.id)
            )
        )
    elif current_user.role == UserRole.CLIENT:
        # Clients see only their engagements
        query = query.filter(Engagement.client_id == current_user.id)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user role."
        )
    
    # Apply status filter
    if status_filter:
        query = query.filter(Engagement.status == status_filter)
    
    # Apply search filter
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Engagement.engagement_name.ilike(search_pattern),
                Engagement.business_name.ilike(search_pattern)
            )
        )
    
    # Get total count before pagination
    total = query.count()
    
    # Apply pagination
    engagements = query.order_by(Engagement.created_at.desc()).offset(skip).limit(limit).all()
    
    # Build response with counts
    result = []
    for engagement in engagements:
        # Count related records
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
        
        # Get client name
        client = db.query(User).filter(User.id == engagement.client_id).first()
        client_name = client.name or client.email if client else None
        
        engagement_dict = {
            **engagement.__dict__,
            "client_name": client_name,
            "diagnostics_count": diagnostics_count,
            "tasks_count": tasks_count,
            "pending_tasks_count": pending_tasks_count,
            "notes_count": notes_count,
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
    if current_user.role == UserRole.ADVISOR:
        # Get all clients (for now - can be filtered by firm later)
        clients = db.query(User).filter(
            User.role == UserRole.CLIENT,
            User.is_active == True
        ).all()
        
        return {
            "user_role": "advisor",
            "clients": [
                {"id": str(client.id), "name": client.name or client.email}
                for client in clients
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
        # Admins get both
        clients = db.query(User).filter(
            User.role == UserRole.CLIENT,
            User.is_active == True
        ).all()
        
        advisors = db.query(User).filter(
            User.role == UserRole.ADVISOR,
            User.is_active == True
        ).all()
        
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
    
    # Populate client_name for response
    client = db.query(User).filter(User.id == engagement.client_id).first()
    engagement_dict = engagement.__dict__.copy()
    engagement_dict["client_name"] = client.name or client.email if client else None
    
    return EngagementDetail(**engagement_dict)


@router.put("/{engagement_id}", response_model=EngagementResponse)
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
    
    # Populate client_name for response
    client = db.query(User).filter(User.id == engagement.client_id).first()
    engagement_dict = engagement.__dict__.copy()
    engagement_dict["client_name"] = client.name or client.email if client else None
    
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

