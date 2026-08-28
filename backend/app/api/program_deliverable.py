"""
Deliverables API endpoints

Thin translation over ProgramDeliverableService. No business logic lives here:
the service owns the invariants and raises ValueError, which is converted to a
400 below. Access control lives entirely in app/services/deliverable_permissions
- there is deliberately no role check in this file.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
import logging

from app.database import get_db
from app.models.engagement import Engagement
from app.models.user import User
from app.services.deliverable_permissions import (
    require_deliverable_read,
    require_deliverable_write,
)
from app.services.program_deliverable_service import (
    DeliverableNotFound,
    derive_module_status,
    get_program_deliverable_service,
)
from app.schemas.program_deliverable import (
    AdvisorDeliverableCreate,
    AdvisorDeliverableUpdate,
    DeliverableCompleteUpdate,
    DeliverableScopeUpdate,
    DeliverableView,
    TaskGenerationResult,
)
from app.utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deliverables", tags=["deliverables"])

_INVALID_REQUEST = "Invalid request data"
_NOT_FOUND = "Deliverable not found"


def _not_found(action: str, exc: Exception) -> HTTPException:
    """
    A deliverable id that does not resolve is a 404, not a 400.

    DeliverableNotFound subclasses ValueError, so it must be caught BEFORE the
    generic handler in every endpoint below - otherwise it falls through and a
    stale id is indistinguishable from a malformed body.
    """
    logger.info("%s: %s", action, exc)
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)


def _invalid(action: str, exc: Exception) -> HTTPException:
    logger.warning("%s: %s", action, exc)
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_INVALID_REQUEST)


def _build_view(engagement: Engagement, db: Session) -> dict:
    """
    Compose the deliverables-and-status view.

    One fetch, then the status per module is derived from the same rows - no
    second query and no second source of truth.
    """
    service = get_program_deliverable_service(db)
    states_by_module = service.get_deliverable_states_by_module(engagement)

    modules = []
    for module_code in sorted(states_by_module):
        states = states_by_module[module_code]
        modules.append({
            "module_code": module_code,
            "status": derive_module_status(states),
            "deliverables": [
                {
                    "deliverable_id": s.deliverable_id,
                    "source": s.source,
                    "title": s.title,
                    "description": s.description,
                    "is_mandatory": s.mandatory,
                    "is_in_scope": s.in_scope,
                    "is_complete": s.complete,
                    "task_count": s.task_count,
                }
                for s in states
            ],
        })

    return {
        "engagement_id": engagement.id,
        "program_type": engagement.tool,
        "modules": modules,
    }


@router.get("/engagements/{engagement_id}", response_model=DeliverableView)
async def get_deliverables(
    engagement: Engagement = Depends(require_deliverable_read),
    db: Session = Depends(get_db),
):
    return _build_view(engagement, db)


@router.put("/engagements/{engagement_id}/items/{deliverable_id}/complete", response_model=DeliverableView)
async def set_deliverable_complete(
    deliverable_id: UUID,
    body: DeliverableCompleteUpdate,
    engagement: Engagement = Depends(require_deliverable_write),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_program_deliverable_service(db)
    try:
        service.set_deliverable_complete(engagement, deliverable_id, body.is_complete, current_user.id)
    except DeliverableNotFound as e:
        raise _not_found("Failed to set deliverable completion", e)
    except ValueError as e:
        raise _invalid("Failed to set deliverable completion", e)
    return _build_view(engagement, db)


@router.put("/engagements/{engagement_id}/items/{deliverable_id}/scope", response_model=DeliverableView)
async def set_deliverable_scope(
    deliverable_id: UUID,
    body: DeliverableScopeUpdate,
    engagement: Engagement = Depends(require_deliverable_write),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_program_deliverable_service(db)
    try:
        service.set_deliverable_scope(engagement, deliverable_id, body.is_in_scope, current_user.id)
    except DeliverableNotFound as e:
        raise _not_found("Failed to set deliverable scope", e)
    except ValueError as e:
        raise _invalid("Failed to set deliverable scope", e)
    return _build_view(engagement, db)


@router.post(
    "/engagements/{engagement_id}/items",
    response_model=DeliverableView,
    status_code=status.HTTP_201_CREATED,
)
async def add_advisor_deliverable(
    body: AdvisorDeliverableCreate,
    engagement: Engagement = Depends(require_deliverable_write),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_program_deliverable_service(db)
    try:
        service.add_advisor_deliverable(
            engagement,
            module_code=body.module_code,
            title=body.title,
            is_mandatory=body.is_mandatory,
            user_id=current_user.id,
            description=body.description,
        )
    except ValueError as e:
        # No DeliverableNotFound branch: a create resolves nothing.
        raise _invalid("Failed to add advisor deliverable", e)
    return _build_view(engagement, db)


@router.patch("/engagements/{engagement_id}/items/{deliverable_id}", response_model=DeliverableView)
async def update_advisor_deliverable(
    deliverable_id: UUID,
    body: AdvisorDeliverableUpdate,
    engagement: Engagement = Depends(require_deliverable_write),
    db: Session = Depends(get_db),
):
    # exclude_unset keeps "field omitted" distinct from "field sent as null":
    # the former leaves the value alone, the latter is rejected by the service.
    fields = body.model_dump(exclude_unset=True)
    service = get_program_deliverable_service(db)
    try:
        service.update_advisor_deliverable(engagement, deliverable_id, **fields)
    except DeliverableNotFound as e:
        raise _not_found("Failed to update advisor deliverable", e)
    except ValueError as e:
        raise _invalid("Failed to update advisor deliverable", e)
    return _build_view(engagement, db)


@router.delete("/engagements/{engagement_id}/items/{deliverable_id}", response_model=DeliverableView)
async def remove_advisor_deliverable(
    deliverable_id: UUID,
    engagement: Engagement = Depends(require_deliverable_write),
    db: Session = Depends(get_db),
):
    service = get_program_deliverable_service(db)
    try:
        service.remove_advisor_deliverable(engagement, deliverable_id)
    except DeliverableNotFound as e:
        raise _not_found("Failed to remove advisor deliverable", e)
    except ValueError as e:
        raise _invalid("Failed to remove advisor deliverable", e)
    return _build_view(engagement, db)


@router.post(
    "/engagements/{engagement_id}/modules/{module_code}/tasks",
    response_model=TaskGenerationResult,
    status_code=status.HTTP_201_CREATED,
)
async def generate_module_tasks(
    module_code: str,
    engagement: Engagement = Depends(require_deliverable_write),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create one task per deliverable in this module that does not have one yet.

    201 even when nothing was created. Zero is a real outcome here - every
    deliverable already carries a task - not a failure, and the caller reads
    created_count to tell the difference.
    """
    service = get_program_deliverable_service(db)
    try:
        before = len(service.get_deliverable_states_by_module(engagement).get(module_code.strip(), []))
        created = service.generate_tasks_for_module(engagement, module_code, current_user.id)
    except ValueError as e:
        raise _invalid("Failed to generate tasks", e)
    return {
        "created_count": len(created),
        "skipped_count": max(before - len(created), 0),
        "view": _build_view(engagement, db),
    }
