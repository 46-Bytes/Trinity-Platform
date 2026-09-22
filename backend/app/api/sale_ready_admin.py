"""
Sale Ready Management API: the master content behind every future engagement.

Admin and super admin only. Everything here edits master rows; an engagement's
own tasks, DD items and guide are copies taken when it was created, so nothing
on this router can change a live engagement.
"""
import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.sale_ready_admin import (
    AdminDDTemplate,
    AdminGuideView,
    AdminTaskTemplate,
    DDCategoryOption,
    DDTemplateCreate,
    DDTemplateUpdate,
    ProgramGuideUpdate,
    ReorderRequest,
    StageGuideUpdate,
    TaskTemplateCreate,
    TaskTemplateUpdate,
)
from app.services.sale_ready_admin_service import (
    SaleReadyAdminNotFound,
    get_sale_ready_admin_service,
)
from app.utils.auth import require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sale-ready/admin", tags=["sale-ready-admin"])

# The brief's Admin row: "Edits the guide text, task templates and DD checklist
# for future engagements." Deliberately narrower than engagement access.
admin_required = require_role([UserRole.SUPER_ADMIN, UserRole.ADMIN])


def _run(action):
    """Map service errors to HTTP: validation 400, missing record 404."""
    try:
        return action()
    except SaleReadyAdminNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ----------------------------------------------------------------------
# Program guide
# ----------------------------------------------------------------------
@router.get("/guide", response_model=AdminGuideView)
async def get_guide(
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """Program-level guide content plus every stage's guide. Stages are read-only."""
    return get_sale_ready_admin_service(db).get_guide()


@router.patch("/guide/program", response_model=AdminGuideView)
async def update_program_guide(
    body: ProgramGuideUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """Edit the workflow steps and the program rules."""
    service = get_sale_ready_admin_service(db)
    return _run(lambda: service.update_program_guide(body.model_dump(exclude_unset=True)))


@router.patch("/guide/stages/{stage_code}", response_model=AdminGuideView)
async def update_stage_guide(
    stage_code: str,
    body: StageGuideUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """Edit one stage's Purpose, How it runs, Watch for, Templates and Run with."""
    service = get_sale_ready_admin_service(db)
    return _run(lambda: service.update_stage_guide(stage_code, body.model_dump(exclude_unset=True)))


# ----------------------------------------------------------------------
# Task templates
# ----------------------------------------------------------------------
@router.get("/task-templates", response_model=List[AdminTaskTemplate])
async def list_task_templates(
    include_retired: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    return get_sale_ready_admin_service(db).list_task_templates(include_retired)


@router.post("/task-templates", response_model=AdminTaskTemplate, status_code=status.HTTP_201_CREATED)
async def create_task_template(
    body: TaskTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """Reaches engagements created from now on; live engagements are unaffected."""
    service = get_sale_ready_admin_service(db)
    return _run(lambda: service.create_task_template(body.model_dump()))


@router.patch("/task-templates/{template_id}", response_model=AdminTaskTemplate)
async def update_task_template(
    template_id: UUID,
    body: TaskTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    service = get_sale_ready_admin_service(db)
    return _run(lambda: service.update_task_template(template_id, body.model_dump(exclude_unset=True)))


@router.delete("/task-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def retire_task_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """Retires the template. Tasks already created from it are left alone."""
    service = get_sale_ready_admin_service(db)
    _run(lambda: service.retire_task_template(template_id))


@router.post("/task-templates/reorder", response_model=List[AdminTaskTemplate])
async def reorder_task_templates(
    body: ReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    service = get_sale_ready_admin_service(db)
    return _run(lambda: service.reorder_task_templates(body.ids))


# ----------------------------------------------------------------------
# Due diligence checklist
# ----------------------------------------------------------------------
@router.get("/dd-categories", response_model=List[DDCategoryOption])
async def list_dd_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """The fixed category / sub-item structure a new checklist item is filed under."""
    return get_sale_ready_admin_service(db).dd_categories()


@router.get("/dd-templates", response_model=List[AdminDDTemplate])
async def list_dd_templates(
    include_retired: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    return get_sale_ready_admin_service(db).list_dd_templates(include_retired)


@router.post("/dd-templates", response_model=AdminDDTemplate, status_code=status.HTTP_201_CREATED)
async def create_dd_template(
    body: DDTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """Filed under an existing sub-item, which fixes its stage and category."""
    service = get_sale_ready_admin_service(db)
    return _run(lambda: service.create_dd_template(body.model_dump()))


@router.patch("/dd-templates/{template_id}", response_model=AdminDDTemplate)
async def update_dd_template(
    template_id: UUID,
    body: DDTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    service = get_sale_ready_admin_service(db)
    return _run(lambda: service.update_dd_template(template_id, body.model_dump(exclude_unset=True)))


@router.delete("/dd-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def retire_dd_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """Retires the item. Engagements that already carry it keep it."""
    service = get_sale_ready_admin_service(db)
    _run(lambda: service.retire_dd_template(template_id))


@router.post("/dd-templates/reorder", response_model=List[AdminDDTemplate])
async def reorder_dd_templates(
    body: ReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    service = get_sale_ready_admin_service(db)
    return _run(lambda: service.reorder_dd_templates(body.ids))
