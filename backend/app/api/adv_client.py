"""
Advisor-Client Association CRUD API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from ..database import get_db
from ..models.adv_client import AdvisorClient
from ..models.user import User, UserRole
from ..schemas.adv_client import (
    AdvisorClientCreate,
    AdvisorClientUpdate,
    AdvisorClientResponse,
    AdvisorClientWithUsers,
)
from ..services.role_check import get_current_user_from_token

router = APIRouter(prefix="/api/advisor-client", tags=["advisor-client"])


@router.post("", response_model=AdvisorClientWithUsers, status_code=status.HTTP_201_CREATED)
async def create_association(
    association_data: AdvisorClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Create a new advisor-client association.
    """
    # Check permissions
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.FIRM_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to create associations."
        )
    
    # Verify advisor exists and is actually an advisor
    advisor = db.query(User).filter(User.id == association_data.advisor_id).first()
    if not advisor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Advisor not found.")
    
    if advisor.role not in [UserRole.ADVISOR, UserRole.FIRM_ADVISOR]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="The specified user is not an advisor.")
    
    # Verify client exists and is actually a client
    client = db.query(User).filter(User.id == association_data.client_id).first()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Client not found.")
    
    if client.role != UserRole.CLIENT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The specified user is not a client.")
    
    # Validate firm_id matching for FIRM_ADVISOR advisors
    if advisor.role == UserRole.FIRM_ADVISOR:
        if not advisor.firm_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="The advisor must belong to a firm.")
        if not client.firm_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Client must belong to a firm to be associated with a firm advisor.")
        if advisor.firm_id != client.firm_id:
            raise HTTPException( status_code=status.HTTP_400_BAD_REQUEST,detail="Client must belong to the same firm as the advisor.")
    
    existing = db.query(AdvisorClient).filter(AdvisorClient.advisor_id == association_data.advisor_id,AdvisorClient.client_id == association_data.client_id).first()
    
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,detail="Association already exists between this advisor and client.")
    
    association = AdvisorClient(
        advisor_id=association_data.advisor_id,
        client_id=association_data.client_id,
        status=association_data.status
    )
    
    db.add(association)
    db.commit()
    db.refresh(association)
    
    # Return association with user details
    advisor = db.query(User).filter(User.id == association.advisor_id).first()
    client = db.query(User).filter(User.id == association.client_id).first()
    
    return AdvisorClientWithUsers(
        id=association.id,
        advisor_id=association.advisor_id,
        client_id=association.client_id,
        status=association.status,
        created_at=association.created_at,
        updated_at=association.updated_at,
        advisor_name=advisor.name if advisor else None,
        advisor_email=advisor.email if advisor else None,
        client_name=client.name if client else None,
        client_email=client.email if client else None,
    )


@router.get("", response_model=List[AdvisorClientWithUsers])
async def list_associations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token),
    advisor_id: Optional[UUID] = Query(None, description="Filter by advisor ID"),
    client_id: Optional[UUID] = Query(None, description="Filter by client ID"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    List advisor-client associations.
    
    Admins and super_admins can see all associations.
    Advisors can see their own associations.
    Clients can see associations where they are the client.
    """
    query = db.query(AdvisorClient)
    
    # Apply role-based filtering
    if current_user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN,UserRole.FIRM_ADMIN]:
        pass
    elif current_user.role in [UserRole.ADVISOR, UserRole.FIRM_ADVISOR]:
        query = query.filter(AdvisorClient.advisor_id == current_user.id)
    elif current_user.role == UserRole.CLIENT:
        query = query.filter(AdvisorClient.client_id == current_user.id)
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="You do not have permission to view associations.")
    
    # Apply filters
    if advisor_id:
        query = query.filter(AdvisorClient.advisor_id == advisor_id)
    
    if client_id:
        query = query.filter(AdvisorClient.client_id == client_id)
    
    if status_filter:
        query = query.filter(AdvisorClient.status == status_filter)
    

    associations = query.offset(skip).limit(limit).all()
    
    result = []
    for assoc in associations:
        advisor = db.query(User).filter(User.id == assoc.advisor_id).first()
        client = db.query(User).filter(User.id == assoc.client_id).first()
        
        result.append(AdvisorClientWithUsers(
            id=assoc.id,
            advisor_id=assoc.advisor_id,
            client_id=assoc.client_id,
            status=assoc.status,
            created_at=assoc.created_at,
            updated_at=assoc.updated_at,
            advisor_name=advisor.name if advisor else None,
            advisor_email=advisor.email if advisor else None,
            client_name=client.name if client else None,
            client_email=client.email if client else None,
        ))
    
    return result


@router.get("/{association_id}", response_model=AdvisorClientWithUsers)
async def get_association(
    association_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Get a specific advisor-client association by ID.
    
    User must have permission to view this association.
    """
    association = db.query(AdvisorClient).filter(AdvisorClient.id == association_id).first()
    
    if not association:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Association not found."
        )
    
    # Check permissions
    if current_user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        # Admins can see all
        pass
    elif current_user.role in [UserRole.ADVISOR, UserRole.FIRM_ADVISOR]:
        # Advisors can only see their own associations
        if association.advisor_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view this association."
            )
    elif current_user.role == UserRole.CLIENT:
        # Clients can only see associations where they are the client
        if association.client_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view this association."
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view associations."
        )
    
    # Get user details
    advisor = db.query(User).filter(User.id == association.advisor_id).first()
    client = db.query(User).filter(User.id == association.client_id).first()
    
    return AdvisorClientWithUsers(
        id=association.id,
        advisor_id=association.advisor_id,
        client_id=association.client_id,
        status=association.status,
        created_at=association.created_at,
        updated_at=association.updated_at,
        advisor_name=advisor.name if advisor else None,
        advisor_email=advisor.email if advisor else None,
        client_name=client.name if client else None,
        client_email=client.email if client else None,
    )


@router.patch("/{association_id}", response_model=AdvisorClientResponse)
async def update_association(
    association_id: UUID,
    association_data: AdvisorClientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Update an advisor-client association.
    Only admins, super_admins, and the advisor can update associations.
    """
    association = db.query(AdvisorClient).filter(AdvisorClient.id == association_id).first()
    
    if not association:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Association not found."
        )
    
    # Check permissions
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        if current_user.role in [UserRole.ADVISOR, UserRole.FIRM_ADVISOR]:
            # Advisors can only update their own associations
            if association.advisor_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have permission to update this association."
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to update associations."
            )
    
    # Update fields
    if association_data.status is not None:
        association.status = association_data.status
    
    db.commit()
    db.refresh(association)
    
    return association


@router.delete("/{association_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_association(
    association_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Delete an advisor-client association.
    
    Only admins, super_admins, and the advisor can delete associations.
    """
    association = db.query(AdvisorClient).filter(AdvisorClient.id == association_id).first()
    
    if not association:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Association not found."
        )
    
    # Check permissions
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.FIRM_ADMIN]:
        if current_user.role in [UserRole.ADVISOR, UserRole.FIRM_ADVISOR]:
            # Advisors can only delete their own associations
            if association.advisor_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have permission to delete this association."
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete associations."
            )
    
    db.delete(association)
    db.commit()
    
    return None

