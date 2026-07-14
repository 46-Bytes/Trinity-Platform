"""
Sale Ready Program API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
import logging

from app.database import get_db
from app.utils.auth import get_current_user
from app.models.user import User
from app.models.engagement import Engagement
from app.services.role_check import check_engagement_access
from app.services.sale_ready_service import get_sale_ready_service, PROGRAM_TYPE
from app.schemas.sale_ready import (
    StagesResponse,
    RoadmapResponse,
    StageStateUpdate,
    StageView,
    ModuleOrderUpdate,
    TaskCompletionResponse,
    GenerateResponse,
    MemberItem,
    DDItemCreate,
    DDItemUpdate,
    DDItemResponse,
    DocumentEntryCreate,
    DocumentEntryUpdate,
    DocumentEntryResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sale-ready", tags=["sale-ready"])


def _get_engagement_or_404(engagement_id: UUID, db: Session) -> Engagement:
    engagement = db.query(Engagement).filter(
        Engagement.id == engagement_id,
        Engagement.is_deleted == False,  # noqa: E712
    ).first()
    if not engagement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engagement not found")
    return engagement


def _require_sale_ready(engagement: Engagement) -> None:
    if engagement.tool != PROGRAM_TYPE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint is only available for Sale Ready engagements",
        )


def _load(engagement_id: UUID, current_user: User, db: Session, require_advisor: bool = False) -> Engagement:
    engagement = _get_engagement_or_404(engagement_id, db)
    if not check_engagement_access(engagement, current_user, require_advisor=require_advisor, db=db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this engagement")
    _require_sale_ready(engagement)
    return engagement


# ---------------------------------------------------------------------------
# Roadmap / stages
# ---------------------------------------------------------------------------
@router.get("/engagements/{engagement_id}/stages", response_model=StagesResponse)
async def get_stages(engagement_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    engagement = _load(engagement_id, current_user, db)
    return get_sale_ready_service(db).get_stages_view(engagement)


@router.get("/engagements/{engagement_id}/roadmap", response_model=RoadmapResponse)
async def get_roadmap(engagement_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    engagement = _load(engagement_id, current_user, db)
    return get_sale_ready_service(db).get_roadmap(engagement)


@router.get("/engagements/{engagement_id}/members", response_model=List[MemberItem])
async def list_members(engagement_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    engagement = _load(engagement_id, current_user, db)
    return get_sale_ready_service(db).list_members(engagement)


@router.post("/engagements/{engagement_id}/generate", response_model=GenerateResponse)
async def generate(engagement_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Idempotently generate stage state, tasks, and DD items (manual/backfill trigger)."""
    engagement = _load(engagement_id, current_user, db, require_advisor=True)
    return get_sale_ready_service(db).generate_engagement(engagement, current_user.id)


@router.patch("/engagements/{engagement_id}/stages/{stage_code}", response_model=StageView)
async def update_stage(
    engagement_id: UUID,
    stage_code: str,
    body: StageStateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _load(engagement_id, current_user, db, require_advisor=True)
    service = get_sale_ready_service(db)
    service.update_stage_state(engagement.id, stage_code, body.model_dump(exclude_unset=True))
    # Return the composed stage so the client gets template fields + state together.
    for s in service.get_stages_view(engagement)["stages"]:
        if s["stage_code"] == stage_code:
            return s
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stage not found")


@router.get("/engagements/{engagement_id}/stages/{stage_code}/task-completion", response_model=TaskCompletionResponse)
async def stage_task_completion(
    engagement_id: UUID, stage_code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    engagement = _load(engagement_id, current_user, db)
    return get_sale_ready_service(db).stage_task_completion(engagement.id, stage_code)


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------
@router.put("/engagements/{engagement_id}/order", response_model=RoadmapResponse)
async def set_order(
    engagement_id: UUID,
    body: ModuleOrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _load(engagement_id, current_user, db, require_advisor=True)
    return get_sale_ready_service(db).set_module_order(engagement, body.module_order)


@router.post("/engagements/{engagement_id}/order/recommended", response_model=RoadmapResponse)
async def apply_recommended_order(
    engagement_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    engagement = _load(engagement_id, current_user, db, require_advisor=True)
    return get_sale_ready_service(db).apply_recommended_order(engagement)


# ---------------------------------------------------------------------------
# DD items (master + module views are the same rows, filtered)
# ---------------------------------------------------------------------------
@router.get("/engagements/{engagement_id}/dd-items", response_model=List[DDItemResponse])
async def list_dd_items(
    engagement_id: UUID,
    module_code: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    completed: Optional[bool] = Query(None),
    responsible_user_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _load(engagement_id, current_user, db)
    return get_sale_ready_service(db).list_dd_items(
        engagement.id, module_code=module_code, category=category,
        completed=completed, responsible_user_id=responsible_user_id,
    )


@router.post("/engagements/{engagement_id}/dd-items", response_model=DDItemResponse, status_code=status.HTTP_201_CREATED)
async def create_dd_item(
    engagement_id: UUID, body: DDItemCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    engagement = _load(engagement_id, current_user, db, require_advisor=True)
    return get_sale_ready_service(db).create_dd_item(engagement.id, body.model_dump(exclude_unset=True))


@router.patch("/engagements/{engagement_id}/dd-items/{item_id}", response_model=DDItemResponse)
async def update_dd_item(
    engagement_id: UUID,
    item_id: UUID,
    body: DDItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _load(engagement_id, current_user, db, require_advisor=True)
    result = get_sale_ready_service(db).update_dd_item(engagement.id, item_id, body.model_dump(exclude_unset=True))
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DD item not found")
    return result


@router.delete("/engagements/{engagement_id}/dd-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dd_item(
    engagement_id: UUID, item_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    engagement = _load(engagement_id, current_user, db, require_advisor=True)
    if not get_sale_ready_service(db).delete_dd_item(engagement.id, item_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DD item not found")
    return None


# ---------------------------------------------------------------------------
# Document register
# ---------------------------------------------------------------------------
@router.get("/engagements/{engagement_id}/documents", response_model=List[DocumentEntryResponse])
async def list_documents(
    engagement_id: UUID,
    stage_code: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _load(engagement_id, current_user, db)
    return get_sale_ready_service(db).list_documents(engagement.id, stage_code=stage_code)


@router.post("/engagements/{engagement_id}/documents", response_model=DocumentEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    engagement_id: UUID,
    body: DocumentEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _load(engagement_id, current_user, db, require_advisor=True)
    return get_sale_ready_service(db).create_document(engagement.id, body.model_dump(exclude_unset=True))


@router.patch("/engagements/{engagement_id}/documents/{entry_id}", response_model=DocumentEntryResponse)
async def update_document(
    engagement_id: UUID,
    entry_id: UUID,
    body: DocumentEntryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _load(engagement_id, current_user, db, require_advisor=True)
    result = get_sale_ready_service(db).update_document(engagement.id, entry_id, body.model_dump(exclude_unset=True))
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document entry not found")
    return result


@router.delete("/engagements/{engagement_id}/documents/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    engagement_id: UUID, entry_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    engagement = _load(engagement_id, current_user, db, require_advisor=True)
    if not get_sale_ready_service(db).delete_document(engagement.id, entry_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document entry not found")
    return None
