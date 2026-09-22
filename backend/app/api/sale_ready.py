"""
Sale Ready API: the roadmap, stage detail, tasks and the DD checklist.

Owners (clients) may read the roadmap and the DD checklist only; everything
else, including stage detail, is advisor and admin only.
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.engagement import Engagement
from app.models.user import User
from app.schemas.sale_ready import (
    CloseoutUpdate,
    CloseoutView,
    CloseProgramRequest,
    DDChecklist,
    DDItem,
    DDItemUpdate,
    ModuleOrderUpdate,
    SalePlannerUpdate,
    SalePlannerView,
    SaleReadyRoadmap,
    StageDetail,
    StageTaskCreate,
    StageTaskUpdate,
    StageUpdate,
)
from app.services.engagement_status import can_change_engagement_status
from app.services.program_registry import PROGRAM_SALE_READY
from app.services.role_check import check_engagement_access
from app.services.sale_ready_planner_service import CloseoutPermissionError, get_sale_ready_planner_service
from app.services.sale_ready_service import SaleReadyNotFound, get_sale_ready_service
from app.utils.auth import get_current_user, get_original_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sale-ready", tags=["sale-ready"])


def _engagement(engagement_id: UUID, db: Session, user: User, require_advisor: bool) -> Engagement:
    engagement = db.query(Engagement).filter(
        Engagement.id == engagement_id,
        Engagement.is_deleted == False,  # noqa: E712
    ).first()
    if not engagement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engagement not found")
    if not check_engagement_access(engagement, user, require_advisor=require_advisor, db=db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this engagement")
    if engagement.tool != PROGRAM_SALE_READY:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This is not a Sale Ready engagement")
    return engagement


def _run(action):
    """Map service errors to HTTP: validation 400, permission 403, missing record 404."""
    try:
        return action()
    except CloseoutPermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except SaleReadyNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ----------------------------------------------------------------------
# Roadmap and module order
# ----------------------------------------------------------------------
@router.get("/engagements/{engagement_id}/roadmap", response_model=SaleReadyRoadmap)
async def get_roadmap(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _engagement(engagement_id, db, current_user, require_advisor=False)
    return get_sale_ready_service(db).get_roadmap(engagement, current_user)


@router.put("/engagements/{engagement_id}/order", response_model=SaleReadyRoadmap)
async def update_module_order(
    engagement_id: UUID,
    body: ModuleOrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _engagement(engagement_id, db, current_user, require_advisor=True)
    service = get_sale_ready_service(db)
    _run(lambda: service.set_module_order(engagement, body.module_order, current_user.id))
    return service.get_roadmap(engagement, current_user)


@router.post("/engagements/{engagement_id}/order/reset", response_model=SaleReadyRoadmap)
async def reset_module_order(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _engagement(engagement_id, db, current_user, require_advisor=True)
    service = get_sale_ready_service(db)
    service.reset_module_order(engagement)
    return service.get_roadmap(engagement, current_user)


# ----------------------------------------------------------------------
# Stages
# ----------------------------------------------------------------------
@router.get("/engagements/{engagement_id}/stages/{stage_code}", response_model=StageDetail)
async def get_stage(
    engagement_id: UUID,
    stage_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _engagement(engagement_id, db, current_user, require_advisor=True)
    return _run(lambda: get_sale_ready_service(db).get_stage_detail(engagement, stage_code, current_user))


@router.patch("/engagements/{engagement_id}/stages/{stage_code}", response_model=StageDetail)
async def update_stage(
    engagement_id: UUID,
    stage_code: str,
    body: StageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _engagement(engagement_id, db, current_user, require_advisor=True)
    service = get_sale_ready_service(db)
    _run(lambda: service.update_stage(engagement, stage_code, body.model_dump(exclude_unset=True), current_user))
    return service.get_stage_detail(engagement, stage_code, current_user)


@router.post("/engagements/{engagement_id}/stages/{stage_code}/start", response_model=StageDetail)
async def start_stage(
    engagement_id: UUID,
    stage_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _engagement(engagement_id, db, current_user, require_advisor=True)
    service = get_sale_ready_service(db)
    _run(lambda: service.start_stage(engagement, stage_code, current_user))
    return service.get_stage_detail(engagement, stage_code, current_user)


@router.post("/engagements/{engagement_id}/stages/{stage_code}/complete", response_model=StageDetail)
async def complete_stage(
    engagement_id: UUID,
    stage_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    original_user: User = Depends(get_original_user),
):
    engagement = _engagement(engagement_id, db, current_user, require_advisor=True)
    service = get_sale_ready_service(db)
    _run(lambda: service.complete_stage(engagement, stage_code, current_user, original_user))
    return service.get_stage_detail(engagement, stage_code, current_user)


@router.post("/engagements/{engagement_id}/stages/{stage_code}/reopen", response_model=StageDetail)
async def reopen_stage(
    engagement_id: UUID,
    stage_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _engagement(engagement_id, db, current_user, require_advisor=True)
    service = get_sale_ready_service(db)
    _run(lambda: service.reopen_stage(engagement, stage_code, current_user))
    return service.get_stage_detail(engagement, stage_code, current_user)


# ----------------------------------------------------------------------
# Tasks
# ----------------------------------------------------------------------
@router.post("/engagements/{engagement_id}/stages/{stage_code}/tasks", response_model=StageDetail)
async def add_stage_task(
    engagement_id: UUID,
    stage_code: str,
    body: StageTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Adds a client-specific task to the stage."""
    engagement = _engagement(engagement_id, db, current_user, require_advisor=True)
    service = get_sale_ready_service(db)
    _run(lambda: service.add_task(engagement, stage_code, body.title, current_user))
    return service.get_stage_detail(engagement, stage_code, current_user)


@router.patch("/engagements/{engagement_id}/tasks/{task_id}", response_model=StageDetail)
async def update_stage_task(
    engagement_id: UUID,
    task_id: UUID,
    body: StageTaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _engagement(engagement_id, db, current_user, require_advisor=True)
    service = get_sale_ready_service(db)
    stage_code = _run(lambda: service.update_task(engagement, task_id, body.model_dump(exclude_unset=True)))
    return service.get_stage_detail(engagement, stage_code, current_user)


# ----------------------------------------------------------------------
# DD checklist
# ----------------------------------------------------------------------
@router.get("/engagements/{engagement_id}/dd", response_model=DDChecklist)
async def get_dd_checklist(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _engagement(engagement_id, db, current_user, require_advisor=False)
    return get_sale_ready_service(db).get_dd_checklist(engagement, current_user)


@router.patch("/engagements/{engagement_id}/dd/{item_id}", response_model=DDItem)
async def update_dd_item(
    engagement_id: UUID,
    item_id: UUID,
    body: DDItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _engagement(engagement_id, db, current_user, require_advisor=True)
    service = get_sale_ready_service(db)
    return _run(lambda: service.update_dd_item(engagement, item_id, body.model_dump(exclude_unset=True), current_user))


# ----------------------------------------------------------------------
# Sale Planner
# ----------------------------------------------------------------------
@router.get("/engagements/{engagement_id}/sale-planner", response_model=SalePlannerView)
async def get_sale_planner(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _engagement(engagement_id, db, current_user, require_advisor=True)
    return _run(lambda: get_sale_ready_planner_service(db).get_sale_planner(engagement))


@router.patch("/engagements/{engagement_id}/sale-planner", response_model=SalePlannerView)
async def update_sale_planner(
    engagement_id: UUID,
    body: SalePlannerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _engagement(engagement_id, db, current_user, require_advisor=True)
    service = get_sale_ready_planner_service(db)
    return _run(lambda: service.update_sale_planner(engagement, body.model_dump(exclude_unset=True), current_user))


# ----------------------------------------------------------------------
# Close-out
# ----------------------------------------------------------------------
@router.get("/engagements/{engagement_id}/closeout", response_model=CloseoutView)
async def get_closeout(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _engagement(engagement_id, db, current_user, require_advisor=True)
    return get_sale_ready_planner_service(db).get_closeout(
        engagement, can_close=can_change_engagement_status(engagement, current_user),
    )


@router.patch("/engagements/{engagement_id}/closeout", response_model=CloseoutView)
async def update_closeout(
    engagement_id: UUID,
    body: CloseoutUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _engagement(engagement_id, db, current_user, require_advisor=True)
    service = get_sale_ready_planner_service(db)
    return _run(lambda: service.update_closeout(
        engagement, body.model_dump(exclude_unset=True),
        can_close=can_change_engagement_status(engagement, current_user),
    ))


@router.post("/engagements/{engagement_id}/closeout/close", response_model=CloseoutView)
async def close_program(
    engagement_id: UUID,
    body: CloseProgramRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    original_user: User = Depends(get_original_user),
):
    """Closes the program and ends the engagement (lifecycle status 'ended') in one transaction."""
    engagement = _engagement(engagement_id, db, current_user, require_advisor=True)
    fields = body.model_dump(exclude_unset=True, exclude={"confirm_without_referral"})
    service = get_sale_ready_planner_service(db)
    return _run(lambda: service.close_program(
        engagement, fields, body.confirm_without_referral, current_user, original_user,
        can_change_status=can_change_engagement_status(engagement, current_user),
    ))


@router.post("/engagements/{engagement_id}/closeout/reopen", response_model=CloseoutView)
async def reopen_program(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reopens the program and recommences the engagement, as the lifecycle Recommence does."""
    engagement = _engagement(engagement_id, db, current_user, require_advisor=True)
    service = get_sale_ready_planner_service(db)
    return _run(lambda: service.reopen_program(
        engagement, current_user, can_change_status=can_change_engagement_status(engagement, current_user),
    ))
