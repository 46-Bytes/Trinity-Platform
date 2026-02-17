"""
Engagement CRUD API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, text, select
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
from ..models.task import Task
from ..models.note import Note
from ..models.diagnostic import Diagnostic
from ..schemas.engagement import (
    EngagementCreate,
    EngagementUpdate,
    EngagementResponse,
    EngagementListItem,
    EngagementDetail,
    SecondaryAdvisorCandidatesResponse,
    SecondaryAdvisorCandidate,
    EngagementClientAdd,
)
from ..services.role_check import get_current_user_from_token, check_engagement_access
from ..models.adv_client import AdvisorClient

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
    
    primary_advisor_id = engagement_data.primary_advisor_id

    # the primary advisor should depend on *who is creating* the engagement.
    if current_user.role == UserRole.FIRM_ADMIN:
        # We keep using the associated advisor as primary advisor (existing behavior).
        association = db.query(AdvisorClient).filter(AdvisorClient.client_id == engagement_data.client_id,AdvisorClient.status == 'active').first()

        if not association:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Client must have an associated advisor before creating an engagement. Please associate an advisor to the client first."
            )

        primary_advisor_id = association.advisor_id

    elif current_user.role == UserRole.FIRM_ADVISOR:
        # Firm advisor: the client must be actively associated *with this advisor*,
        association = db.query(AdvisorClient).filter(AdvisorClient.client_id == engagement_data.client_id,AdvisorClient.advisor_id == current_user.id,AdvisorClient.status == 'active').first()

        if not association:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="This client must be actively associated with you before creating an engagement.")

        primary_advisor_id = current_user.id
    
    # Verify primary advisor exists (can be ADVISOR, FIRM_ADVISOR, or FIRM_ADMIN)
    primary_advisor = db.query(User).filter(
        User.id == primary_advisor_id,
        User.role.in_([UserRole.ADVISOR, UserRole.FIRM_ADVISOR, UserRole.FIRM_ADMIN])
    ).first()
    if not primary_advisor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Primary advisor not found or invalid advisor ID."
        )
    
    # Auto-set firm_id for firm_admin and firm_advisor users if not provided
    firm_id = engagement_data.firm_id
    if not firm_id and current_user.role in [UserRole.FIRM_ADMIN, UserRole.FIRM_ADVISOR]:
        firm_id = current_user.firm_id
    
    # Verify secondary advisors if provided - validate based on engagement context
    unique_secondary_ids = []
    if engagement_data.secondary_advisor_ids:
        # Remove duplicates
        unique_secondary_ids = list(set(engagement_data.secondary_advisor_ids))
        if len(unique_secondary_ids) != len(engagement_data.secondary_advisor_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate secondary advisor IDs are not allowed."
            )
        
        # Ensure primary advisor is not in secondary list
        if primary_advisor_id in unique_secondary_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Primary advisor cannot be added as a secondary advisor."
            )
        
        # Validate based on current user role AND engagement context
        if current_user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.ADVISOR]:
            # Admin/advisor users can ONLY add advisor role users (solo advisors)
            secondary_advisors = db.query(User).filter(
                User.id.in_(unique_secondary_ids),
                User.role == UserRole.ADVISOR,
                User.firm_id.is_(None),
                User.is_active == True
            ).all()
            if len(secondary_advisors) != len(unique_secondary_ids):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Admins and advisors can only add advisor role users (solo advisors) as secondary advisors."
                )
        elif current_user.role in [UserRole.FIRM_ADMIN, UserRole.FIRM_ADVISOR]:
            # Firm users can ONLY add firm_advisor role users from the same firm
            if firm_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Firm engagements require a firm_id. Cannot add secondary advisors to solo engagements."
                )
            secondary_advisors = db.query(User).filter(
                User.id.in_(unique_secondary_ids),
                User.role == UserRole.FIRM_ADVISOR,
                User.firm_id == firm_id,
                User.is_active == True
            ).all()
            if len(secondary_advisors) != len(unique_secondary_ids):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="For firm engagements, secondary advisors must be firm_advisor role users from the same firm."
                )
    
    # Create engagement
    # Convert single client_id to client_ids array
    client_ids_array = [engagement_data.client_id]
    
    engagement = Engagement(
        engagement_name=engagement_data.engagement_name,
        business_name=engagement_data.business_name,
        industry=engagement_data.industry,
        description=engagement_data.description,
        tool=engagement_data.tool,
        status=engagement_data.status,
        client_id=engagement_data.client_id,  # Keep for backward compatibility
        client_ids=client_ids_array,  # New array format
        primary_advisor_id=primary_advisor_id,
        firm_id=firm_id,
        secondary_advisor_ids=unique_secondary_ids,
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
    client_name = client.name or client.email or client.nickname if client else None
    response.client_name = client_name  # Keep for backward compatibility
    response.client_names = [client_name] if client_name else []  # New array format
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
    query = db.query(Engagement).filter(Engagement.is_deleted == False)
    
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
        # Advisors and firm advisors see:
        associated_client_ids_stmt = select(AdvisorClient.client_id).where(
            AdvisorClient.advisor_id == current_user.id,
            AdvisorClient.status == "active",
        )

        query = query.filter(
            or_(
                Engagement.primary_advisor_id == current_user.id,
                text("secondary_advisor_ids @> ARRAY[:user_id]::uuid[]").bindparams(
                    user_id=current_user.id
                ),
                Engagement.client_id.in_(associated_client_ids_stmt),
            )
        )
    elif current_user.role == UserRole.CLIENT:
        # Support multi-client engagements via `client_ids` array.
        # `client_id` is kept for backward compatibility but is not reliable when multiple
        # clients are associated to one engagement.
        query = query.filter(
            or_(
                Engagement.client_id == current_user.id,
                text("client_ids @> ARRAY[:user_id]::uuid[]").bindparams(user_id=current_user.id),
            )
        )
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
        
        # Get client names from client_ids array (or fallback to client_id for backward compatibility)
        client_ids_to_fetch = engagement.client_ids if engagement.client_ids else []
        # Fallback to client_id if client_ids is empty (for backward compatibility)
        if not client_ids_to_fetch and engagement.client_id:
            client_ids_to_fetch = [engagement.client_id]
        
        client_name = None
        client_names = []
        if client_ids_to_fetch:
            try:
                clients = db.query(User).filter(User.id.in_(client_ids_to_fetch)).all()
                client_names = [
                    (client.name or client.email or client.nickname) 
                    for client in clients 
                    if client
                ]
                # Set client_name to first client for backward compatibility
                if client_names:
                    client_name = client_names[0]
            except Exception as e:
                logger.error(f"Error fetching clients {client_ids_to_fetch}: {str(e)}")
        
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
            "client_name": client_name,  # Keep for backward compatibility
            "client_names": client_names,  # New array format
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
                User.is_active == True,
                User.is_deleted == False
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
                User.is_active == True,
                User.is_deleted == False
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
                {
                    "id": str(client.id),
                    "name": client.name or client.email,
                    "email": client.email or "",
                    "given_name": client.first_name,
                    "family_name": client.last_name,
                    "created_at": client.created_at.isoformat() if client.created_at else None
                }
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
                User.is_active == True,
                User.is_deleted == False
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
                {
                    "id": str(client.id),
                    "name": client.name or client.email,
                    "email": client.email or "",
                    "given_name": client.first_name,
                    "family_name": client.last_name,
                    "created_at": client.created_at.isoformat() if client.created_at else None
                }
                for client in clients
            ],
            "advisors": [
                {"id": str(advisor.id), "name": advisor.name or advisor.email}
                for advisor in advisors
            ]
        }
    
    elif current_user.role == UserRole.CLIENT:
        # Get advisors associated with this client through advisor_client table        
        associations = db.query(AdvisorClient).filter(
            AdvisorClient.client_id == current_user.id,
            AdvisorClient.status == 'active'
        ).all()
        
        associated_advisor_ids = [assoc.advisor_id for assoc in associations]
        
        if not associated_advisor_ids:
            advisors = []
        else:
            # If client has firm_id, only return advisors with same firm_id
            # If client has no firm_id, only return advisors with no firm_id (solo advisors)
            if current_user.firm_id:
                advisors = db.query(User).filter(
                    User.id.in_(associated_advisor_ids),
                    User.firm_id == current_user.firm_id,
                    User.role.in_([UserRole.FIRM_ADVISOR]),
                    User.is_active == True
                ).all()
            else:
                advisors = db.query(User).filter(
                    User.id.in_(associated_advisor_ids),
                    User.firm_id.is_(None),
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
        clients = db.query(User).filter(User.role == UserRole.CLIENT,User.is_active == True,User.firm_id.is_(None),User.is_deleted == False).all()
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
    engagement = db.query(Engagement).filter(Engagement.id == engagement_id, Engagement.is_deleted == False).first()
    
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found."
        )
    
    # Check access
    if not check_engagement_access(engagement, current_user, db=db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this engagement."
        )
    
    # Populate client_name, client_names, and advisor_name for response
    client_ids_to_fetch = engagement.client_ids if engagement.client_ids else []
    # Fallback to client_id if client_ids is empty (for backward compatibility)
    if not client_ids_to_fetch and engagement.client_id:
        client_ids_to_fetch = [engagement.client_id]
    
    client_name = None
    client_names = []
    if client_ids_to_fetch:
        clients = db.query(User).filter(User.id.in_(client_ids_to_fetch)).all()
        client_names = [
            (client.name or client.email or client.nickname) 
            for client in clients 
            if client
        ]
        # Set client_name to first client for backward compatibility
        if client_names:
            client_name = client_names[0]
    
    primary_advisor = db.query(User).filter(User.id == engagement.primary_advisor_id).first()
    engagement_dict = engagement.__dict__.copy()
    engagement_dict["client_name"] = client_name  # Keep for backward compatibility
    engagement_dict["client_names"] = client_names  # New array format
    engagement_dict["advisor_name"] = primary_advisor.name or primary_advisor.email or primary_advisor.nickname if primary_advisor else None
    
    return EngagementDetail(**engagement_dict)


@router.get("/{engagement_id}/secondary-advisor-candidates", response_model=SecondaryAdvisorCandidatesResponse)
async def get_secondary_advisor_candidates(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token),
):
    """
    Get eligible secondary advisor candidates for an engagement.
    
    Returns:
    - For solo engagements (firm_id is None): advisor role users with no firm_id
    - For firm engagements (firm_id is not None): firm_advisor role users from the same firm
    
    User must have advisor access to the engagement.
    """
    engagement = db.query(Engagement).filter(
        Engagement.id == engagement_id,
        Engagement.is_deleted == False
    ).first()
    
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found."
        )
    
    # Check access - require advisor access
    if not check_engagement_access(engagement, current_user, require_advisor=True, db=db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this engagement."
        )
    
    # Determine eligible candidates based on current user role AND engagement context
    if current_user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.ADVISOR]:
        # Admin/advisor users can ONLY see advisor role users (solo advisors)
        candidates = db.query(User).filter(
            User.role == UserRole.ADVISOR,
            User.firm_id.is_(None),
            User.is_active == True,
            User.is_deleted == False,
            User.id != engagement.primary_advisor_id  # Exclude primary advisor
        ).all()
    elif current_user.role in [UserRole.FIRM_ADMIN, UserRole.FIRM_ADVISOR]:
        # Firm users can ONLY see firm_advisor role users from the same firm
        if engagement.firm_id is None:
            # No candidates for firm users on solo engagements
            candidates = []
        else:
            candidates = db.query(User).filter(
                User.role == UserRole.FIRM_ADVISOR,
                User.firm_id == engagement.firm_id,
                User.is_active == True,
                User.is_deleted == False,
                User.id != engagement.primary_advisor_id  # Exclude primary advisor
            ).all()
    else:
        # Other roles (shouldn't reach here due to access check, but handle gracefully)
        candidates = []
    
    # Convert to response format
    candidate_list = [
        SecondaryAdvisorCandidate(
            id=candidate.id,
            name=candidate.name or candidate.email or candidate.nickname or "Unknown",
            email=candidate.email or ""
        )
        for candidate in candidates
    ]
    
    return SecondaryAdvisorCandidatesResponse(candidates=candidate_list)


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
    if current_user.role not in [UserRole.ADVISOR, UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.FIRM_ADMIN, UserRole.FIRM_ADVISOR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only advisors and admins can update engagements."
        )
    
    # Check access
    if not check_engagement_access(
        engagement, current_user, require_advisor=True, db=db
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to update this engagement."
        )
    
    # Update fields
    update_data = engagement_data.model_dump(exclude_unset=True)
    
    # Handle secondary_advisor_ids separately if provided
    if "secondary_advisor_ids" in update_data:
        if update_data["secondary_advisor_ids"] is not None:
            # Remove duplicates
            unique_secondary_ids = list(set(update_data["secondary_advisor_ids"]))
            if len(unique_secondary_ids) != len(update_data["secondary_advisor_ids"]):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Duplicate secondary advisor IDs are not allowed."
                )
            
            # Ensure primary advisor is not in secondary list
            if engagement.primary_advisor_id in unique_secondary_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Primary advisor cannot be added as a secondary advisor."
                )
            
            # Validate based on current user role AND engagement context
            if current_user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.ADVISOR]:
                # Admin/advisor users can ONLY add advisor role users (solo advisors)
                secondary_advisors = db.query(User).filter(
                    User.id.in_(unique_secondary_ids),
                    User.role == UserRole.ADVISOR,
                    User.firm_id.is_(None),
                    User.is_active == True
                ).all()
                if len(secondary_advisors) != len(unique_secondary_ids):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Admins and advisors can only add advisor role users (solo advisors) as secondary advisors."
                    )
            elif current_user.role in [UserRole.FIRM_ADMIN, UserRole.FIRM_ADVISOR]:
                # Firm users can ONLY add firm_advisor role users from the same firm
                if engagement.firm_id is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Firm users cannot add secondary advisors to solo engagements."
                    )
                secondary_advisors = db.query(User).filter(
                    User.id.in_(unique_secondary_ids),
                    User.role == UserRole.FIRM_ADVISOR,
                    User.firm_id == engagement.firm_id,
                    User.is_active == True
                ).all()
                if len(secondary_advisors) != len(unique_secondary_ids):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="For firm engagements, secondary advisors must be firm_advisor role users from the same firm."
                    )
            
            # Update the value in update_data to use the validated unique list
            update_data["secondary_advisor_ids"] = unique_secondary_ids
    
    for field, value in update_data.items():
        setattr(engagement, field, value)
    
    db.commit()
    db.refresh(engagement)
    
    # Populate client_name, client_names, and advisor_name for response
    client_ids_to_fetch = engagement.client_ids if engagement.client_ids else []
    # Fallback to client_id if client_ids is empty (for backward compatibility)
    if not client_ids_to_fetch and engagement.client_id:
        client_ids_to_fetch = [engagement.client_id]
    
    client_name = None
    client_names = []
    if client_ids_to_fetch:
        clients = db.query(User).filter(User.id.in_(client_ids_to_fetch)).all()
        client_names = [
            (client.name or client.email or client.nickname) 
            for client in clients 
            if client
        ]
        # Set client_name to first client for backward compatibility
        if client_names:
            client_name = client_names[0]
    
    primary_advisor = db.query(User).filter(User.id == engagement.primary_advisor_id).first()
    engagement_dict = engagement.__dict__.copy()
    engagement_dict["client_name"] = client_name  # Keep for backward compatibility
    engagement_dict["client_names"] = client_names  # New array format
    engagement_dict["advisor_name"] = primary_advisor.name or primary_advisor.email or primary_advisor.nickname if primary_advisor else None
    
    return EngagementResponse(**engagement_dict)


def get_eligible_clients_for_user(current_user: User, db: Session) -> List[UUID]:
    """
    Get list of eligible client IDs that the current user can add to engagements.
    
    Rules:
    - admin: All clients without firm_id
    - advisor: Only associated clients (via AdvisorClient)
    - firm_admin: Only clients inside the firm (with matching firm_id)
    - firm_advisor: Associated clients with matching firm_id
    """
    if current_user.role == UserRole.ADMIN:
        # Admin can add existing clients (without firm_id)
        clients = db.query(User).filter(
            User.role == UserRole.CLIENT,
            User.firm_id.is_(None),
            User.is_active == True,
            User.is_deleted == False
        ).all()
        return [client.id for client in clients]
    
    elif current_user.role == UserRole.ADVISOR:
        # Advisor can add only associated clients
        associations = db.query(AdvisorClient).filter(
            AdvisorClient.advisor_id == current_user.id,
            AdvisorClient.status == 'active'
        ).all()
        associated_client_ids = [assoc.client_id for assoc in associations]
        
        if associated_client_ids:
            clients = db.query(User).filter(
                User.id.in_(associated_client_ids),
                User.role == UserRole.CLIENT,
                User.is_active == True,
                User.is_deleted == False
            ).all()
            return [client.id for client in clients]
        return []
    
    elif current_user.role == UserRole.FIRM_ADMIN:
        # Firm admin can add only clients inside the firm (with matching firm_id)
        if not current_user.firm_id:
            return []
        
        from ..models.firm import Firm
        firm = db.query(Firm).filter(Firm.id == current_user.firm_id).first()
        if not firm or not firm.clients:
            return []
        
        clients = db.query(User).filter(
            User.id.in_(firm.clients),
            User.role == UserRole.CLIENT,
            User.firm_id == current_user.firm_id,
            User.is_active == True,
            User.is_deleted == False
        ).all()
        return [client.id for client in clients]
    
    elif current_user.role == UserRole.FIRM_ADVISOR:
        # Firm advisor can add associated clients (with matching firm_id)
        if not current_user.firm_id:
            return []
        
        associations = db.query(AdvisorClient).filter(
            AdvisorClient.advisor_id == current_user.id,
            AdvisorClient.status == 'active'
        ).all()
        associated_client_ids = [assoc.client_id for assoc in associations]
        
        if associated_client_ids:
            clients = db.query(User).filter(
                User.id.in_(associated_client_ids),
                User.role == UserRole.CLIENT,
                User.firm_id == current_user.firm_id,
                User.is_active == True,
                User.is_deleted == False
            ).all()
            return [client.id for client in clients]
        return []
    
    return []


@router.post("/{engagement_id}/clients", response_model=EngagementResponse)
async def add_clients_to_engagement(
    engagement_id: UUID,
    client_data: EngagementClientAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Add clients to an engagement.
    
    Authorization rules:
    - admin: Can add existing clients (without firm_id)
    - advisor: Can add only associated clients (via AdvisorClient)
    - firm_admin: Can add only clients inside the firm (with matching firm_id)
    - firm_advisor: Can add associated clients (with matching firm_id)
    """
    # Check permissions
    if current_user.role not in [UserRole.ADVISOR, UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.FIRM_ADMIN, UserRole.FIRM_ADVISOR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only advisors and admins can add clients to engagements."
        )
    
    # Get engagement
    engagement = db.query(Engagement).filter(
        Engagement.id == engagement_id,
        Engagement.is_deleted == False
    ).first()
    
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found."
        )
    
    # Check access
    if not check_engagement_access(engagement, current_user, require_advisor=True, db=db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this engagement."
        )
    
    # Get eligible clients for this user
    eligible_client_ids = get_eligible_clients_for_user(current_user, db)
    
    # Validate that all requested clients are eligible
    invalid_client_ids = [cid for cid in client_data.client_ids if cid not in eligible_client_ids]
    if invalid_client_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have permission to add these clients: {invalid_client_ids}"
        )
    
    # Get current client_ids (or fallback to client_id)
    current_client_ids = engagement.client_ids if engagement.client_ids else []
    if not current_client_ids and engagement.client_id:
        current_client_ids = [engagement.client_id]
    
    # Add new clients (avoid duplicates)
    new_client_ids = list(set(current_client_ids + client_data.client_ids))
    
    # Update engagement
    engagement.client_ids = new_client_ids
    # Also update client_id for backward compatibility (use first client)
    if new_client_ids:
        engagement.client_id = new_client_ids[0]
    
    db.commit()
    db.refresh(engagement)
    
    # Populate response
    client_ids_to_fetch = engagement.client_ids if engagement.client_ids else []
    if not client_ids_to_fetch and engagement.client_id:
        client_ids_to_fetch = [engagement.client_id]
    
    client_name = None
    client_names = []
    if client_ids_to_fetch:
        clients = db.query(User).filter(User.id.in_(client_ids_to_fetch)).all()
        client_names = [
            (client.name or client.email or client.nickname) 
            for client in clients 
            if client
        ]
        if client_names:
            client_name = client_names[0]
    
    primary_advisor = db.query(User).filter(User.id == engagement.primary_advisor_id).first()
    engagement_dict = engagement.__dict__.copy()
    engagement_dict["client_name"] = client_name
    engagement_dict["client_names"] = client_names
    engagement_dict["advisor_name"] = primary_advisor.name or primary_advisor.email or primary_advisor.nickname if primary_advisor else None
    
    return EngagementResponse(**engagement_dict)


@router.delete("/{engagement_id}/clients/{client_id}", response_model=EngagementResponse)
async def remove_client_from_engagement(
    engagement_id: UUID,
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Remove a client from an engagement.
    
    Authorization rules:
    - Same as add_client rules (users who can add can also remove)
    """
    # Check permissions
    if current_user.role not in [UserRole.ADVISOR, UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.FIRM_ADMIN, UserRole.FIRM_ADVISOR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only advisors and admins can remove clients from engagements."
        )
    
    # Get engagement
    engagement = db.query(Engagement).filter(
        Engagement.id == engagement_id,
        Engagement.is_deleted == False
    ).first()
    
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found."
        )
    
    # Check access
    if not check_engagement_access(engagement, current_user, require_advisor=True, db=db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this engagement."
        )
    
    # Get current client_ids (or fallback to client_id)
    current_client_ids = engagement.client_ids if engagement.client_ids else []
    if not current_client_ids and engagement.client_id:
        current_client_ids = [engagement.client_id]
    
    # Check if client is in the engagement
    if client_id not in current_client_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client is not associated with this engagement."
        )
    
    # Remove client
    new_client_ids = [cid for cid in current_client_ids if cid != client_id]
    
    # Don't allow removing the last client
    if not new_client_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the last client from an engagement."
        )
    
    # Update engagement
    engagement.client_ids = new_client_ids
    # Also update client_id for backward compatibility (use first client)
    engagement.client_id = new_client_ids[0]
    
    db.commit()
    db.refresh(engagement)
    
    # Populate response
    client_ids_to_fetch = engagement.client_ids if engagement.client_ids else []
    if not client_ids_to_fetch and engagement.client_id:
        client_ids_to_fetch = [engagement.client_id]
    
    client_name = None
    client_names = []
    if client_ids_to_fetch:
        clients = db.query(User).filter(User.id.in_(client_ids_to_fetch)).all()
        client_names = [
            (client.name or client.email or client.nickname) 
            for client in clients 
            if client
        ]
        if client_names:
            client_name = client_names[0]
    
    primary_advisor = db.query(User).filter(User.id == engagement.primary_advisor_id).first()
    engagement_dict = engagement.__dict__.copy()
    engagement_dict["client_name"] = client_name
    engagement_dict["client_names"] = client_names
    engagement_dict["advisor_name"] = primary_advisor.name or primary_advisor.email or primary_advisor.nickname if primary_advisor else None
    
    return EngagementResponse(**engagement_dict)


@router.delete("/{engagement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_engagement(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token),
):
    """
    Soft delete an engagement by marking it as is_deleted=True.
    
    Additionally hard delete all related tasks, notes, and diagnostics so
    no orphaned work items remain.
    
    Only super admins, admins, and firm admins can delete engagements.
    """
    engagement = db.query(Engagement).filter(
        Engagement.id == engagement_id,
        Engagement.is_deleted == False,
    ).first()
    
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found."
        )
    
    # Check permissions - only admin-level roles can delete
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.FIRM_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and firm admins can delete engagements."
        )
    
    # Hard delete related work items tied to this engagement
    db.query(Task).filter(Task.engagement_id == engagement_id).delete(synchronize_session=False)
    db.query(Note).filter(Note.engagement_id == engagement_id).delete(synchronize_session=False)
    db.query(Diagnostic).filter(Diagnostic.engagement_id == engagement_id).delete(synchronize_session=False)

    # Soft delete: mark engagement as deleted instead of removing the row
    engagement.is_deleted = True
    db.commit()

    return None

