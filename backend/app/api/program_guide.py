"""
Program Guide API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
import logging

from app.database import get_db
from app.utils.auth import get_current_user
from app.models.user import User
from app.models.engagement import Engagement
from app.services.role_check import check_engagement_access
from app.services.program_guide_service import get_program_guide_service
from app.schemas.program_guide import (
    ProgramModuleContentItem,
    ProgramGuideView,
    ProgramGuideOrderUpdate,
    ValueMovementResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/program-guide", tags=["program-guide"])


def _get_engagement_or_404(engagement_id: UUID, db: Session) -> Engagement:
    engagement = db.query(Engagement).filter(
        Engagement.id == engagement_id,
        Engagement.is_deleted == False,
    ).first()
    if not engagement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engagement not found")
    return engagement


def _check_access(engagement: Engagement, current_user: User, db: Session, require_advisor: bool = False):
    if not check_engagement_access(engagement, current_user, require_advisor=require_advisor, db=db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this engagement")


@router.get("/content", response_model=List[ProgramModuleContentItem])
async def list_content(
    program_type: str = Query(..., description="e.g. 'value_builder'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_program_guide_service(db)
    return service.get_content(program_type)


@router.get("/engagements/{engagement_id}", response_model=ProgramGuideView)
async def get_program_guide(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _get_engagement_or_404(engagement_id, db)
    _check_access(engagement, current_user, db)

    if engagement.tool != "value_builder":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Program Guide is only available for Value Builder engagements",
        )

    service = get_program_guide_service(db)
    return service.get_program_guide_view(engagement)


@router.put("/engagements/{engagement_id}/order", response_model=ProgramGuideView)
async def update_module_order(
    engagement_id: UUID,
    body: ProgramGuideOrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _get_engagement_or_404(engagement_id, db)
    _check_access(engagement, current_user, db, require_advisor=True)

    service = get_program_guide_service(db)
    return service.set_custom_order(engagement, body.module_order, current_user.id)


@router.post("/engagements/{engagement_id}/order/reset", response_model=ProgramGuideView)
async def reset_module_order(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _get_engagement_or_404(engagement_id, db)
    _check_access(engagement, current_user, db, require_advisor=True)

    service = get_program_guide_service(db)
    return service.reset_custom_order(engagement)


@router.get("/engagements/{engagement_id}/value-movement", response_model=ValueMovementResponse)
async def get_value_movement(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _get_engagement_or_404(engagement_id, db)
    _check_access(engagement, current_user, db)

    service = get_program_guide_service(db)
    return service.compute_value_movement(engagement_id)
