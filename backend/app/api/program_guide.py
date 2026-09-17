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
from app.models.user import User, UserRole
from app.models.engagement import Engagement
from app.services.role_check import check_engagement_access
from app.services.program_guide_service import get_program_guide_service
from app.schemas.program_guide import (
    ProgramModuleContentItem,
    ProgramGuideDashboardView,
    ProgramGuideInsightsView,
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


def _require_value_builder(engagement: Engagement) -> None:
    if engagement.tool != "value_builder":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Program Guide is only available for Value Builder engagements",
        )


@router.get("/content", response_model=List[ProgramModuleContentItem])
async def list_content(
    program_type: str = Query(..., description="e.g. 'value_builder'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    The module card library for a program type.

    Not engagement-scoped, so there is no engagement to authorize against - the
    role alone decides. Part A gives advisors View and admins View and edit on
    module card contents, and owners No, so clients are refused outright rather
    than being served the entire library.
    """
    if current_user.role == UserRole.CLIENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Module card contents are not available to business owners",
        )

    service = get_program_guide_service(db)
    return service.get_content(program_type)


@router.get("/engagements/{engagement_id}", response_model=ProgramGuideView)
async def get_program_guide(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    The full guide: every module card's contents.

    Advisor and admin only. Part A puts module card contents in the owner's No
    column - an owner gets /dashboard below instead.
    """
    engagement = _get_engagement_or_404(engagement_id, db)
    _check_access(engagement, current_user, db, require_advisor=True)
    _require_value_builder(engagement)

    service = get_program_guide_service(db)
    return service.get_program_guide_view(engagement)


@router.get("/engagements/{engagement_id}/dashboard", response_model=ProgramGuideDashboardView)
async def get_program_dashboard(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Progress and the module list - the one Program Guide read owners do get.

    Deliberately open to every role with engagement access. The narrowing is in
    the payload, not the guard: ProgramGuideDashboardView carries no card
    content, so there is nothing here an owner may not see.
    """
    engagement = _get_engagement_or_404(engagement_id, db)
    _check_access(engagement, current_user, db)
    _require_value_builder(engagement)

    service = get_program_guide_service(db)
    return service.get_dashboard_view(engagement)


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
    service.set_custom_order(engagement, body.module_order, current_user.id)
    # set_custom_order returns the order dict ({source, order, diagnostic_id}),
    # which is not a ProgramGuideView and fails response validation. The view is
    # also what the caller wants: it re-ranks and re-sorts the module list, so
    # the client can replace state wholesale instead of reordering it itself.
    return service.get_program_guide_view(engagement)


@router.post("/engagements/{engagement_id}/order/reset", response_model=ProgramGuideView)
async def reset_module_order(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _get_engagement_or_404(engagement_id, db)
    _check_access(engagement, current_user, db, require_advisor=True)

    service = get_program_guide_service(db)
    service.reset_custom_order(engagement)
    # Same as update_module_order above: the service returns the order dict, the
    # endpoint has to answer with the composed view.
    return service.get_program_guide_view(engagement)


@router.get("/engagements/{engagement_id}/value-movement", response_model=ValueMovementResponse)
async def get_value_movement(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _get_engagement_or_404(engagement_id, db)
    # Per-module scores and RAG are diagnostic findings, which Part A puts in
    # the owner's No column.
    _check_access(engagement, current_user, db, require_advisor=True)

    service = get_program_guide_service(db)
    return service.compute_value_movement(engagement_id)


@router.get("/engagements/{engagement_id}/insights", response_model=ProgramGuideInsightsView)
async def get_module_insights(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Per-module score, RAG and severity for this engagement.

    Same guard and the same reason as value-movement: Part A puts per-module
    scores in the owner's No column. Unlike that route, this one answers from a
    single completed diagnostic, which is what most engagements actually have.
    """
    engagement = _get_engagement_or_404(engagement_id, db)
    _check_access(engagement, current_user, db, require_advisor=True)
    _require_value_builder(engagement)

    service = get_program_guide_service(db)
    return service.compute_module_insights(engagement)
