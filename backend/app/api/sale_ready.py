"""
Sale Ready API: the roadmap, stage detail, tasks and the DD checklist.

Owners (clients) may read the roadmap and the DD checklist only; everything
else, including stage detail, is advisor and admin only.
"""
import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.engagement import Engagement
from app.models.media import Media
from app.models.user import User
from app.schemas.sale_ready import (
    CloseoutUpdate,
    DataRoomFile,
    DataRoomView,
    FileRename,
    RegisterEntry,
    RegisterEntryUpdate,
    CloseoutView,
    CloseProgramRequest,
    DDChecklist,
    DDItem,
    DDItemUpdate,
    ModuleOrderUpdate,
    SalePlannerUpdate,
    SalePlannerView,
    SaleReadyGuideView,
    SaleReadyRoadmap,
    StageDetail,
    StageTaskCreate,
    StageTaskUpdate,
    StageUpdate,
)
from app.services.buyer_service import get_buyer_service
from app.services.data_room_service import DataRoomError, get_data_room_service
from app.services.drive_client import DriveUnavailable, drive_enabled
from app.services.drive_folder_service import SharedDriveFolder, get_drive_folder_service
from app.services.engagement_status import can_change_engagement_status
from app.services.program_registry import PROGRAM_SALE_READY
from app.services.role_check import check_engagement_access
from app.services.sale_ready_planner_service import CloseoutPermissionError, get_sale_ready_planner_service
from app.services.sale_ready_service import SaleReadyNotFound, get_sale_ready_service
from app.utils import content_disposition
from app.utils.auth import get_current_user, get_original_user, deny_buyers

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sale-ready", tags=["sale-ready"],
    # Buyers are external parties confined to their own portal.
    dependencies=[Depends(deny_buyers)],
)
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
@router.get("/engagements/{engagement_id}/guide", response_model=SaleReadyGuideView)
async def get_guide(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """This engagement's program guide, frozen when it was created."""
    engagement = _engagement(engagement_id, db, current_user, require_advisor=True)
    return get_sale_ready_service(db).get_guide(engagement, current_user)


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


# ----------------------------------------------------------------------
# Data room
# ----------------------------------------------------------------------
def _file_view(media: Media, names: dict) -> dict:
    """
    A file as an advisor or owner sees it. The Drive link, never the Drive id.

    Every caller is on this router, so deny_buyers already rules a buyer out;
    the buyer's own document schema has no field for a link either way.
    """
    return {
        "id": media.id,
        "file_name": media.file_name,
        "file_size": media.file_size,
        "file_type": media.file_type,
        "category_code": media.dd_category_code,
        "sub_item_code": media.dd_sub_item_code,
        "uploaded_by_name": names.get(media.user_id),
        "source": media.source,
        "created_at": media.created_at,
        "drive_web_link": media.drive_web_link,
    }


def _uploader_names(db: Session, files) -> dict:
    ids = {f.user_id for f in files if f.user_id}
    if not ids:
        return {}
    return {u.id: (u.name or u.email) for u in db.query(User).filter(User.id.in_(ids)).all()}


@router.get("/engagements/{engagement_id}/data-room", response_model=DataRoomView)
async def get_data_room(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Every DD folder, whether it is released to buyers, and what is filed in it.

    Readable by the owner as well as advisors, because the brief gives them
    Files. Both receive the Drive links for the folders, so they can open one
    in Drive when they want to; Trinity stays the primary interface and
    neither role authenticates into Drive to use Trinity.

    Buyers cannot reach this endpoint at all - deny_buyers on the router, and
    check_engagement_access below - and their own schemas carry no link.
    """
    engagement = _engagement(engagement_id, db, current_user, require_advisor=False)
    data_room = get_data_room_service(db)
    buyers = get_buyer_service(db)
    drive_folders = get_drive_folder_service(db)

    files = data_room.files_for_engagement(engagement.id)
    names = _uploader_names(db, files)

    counts = {}
    for f in files:
        key = (f.dd_category_code, f.dd_sub_item_code)
        counts[key] = counts.get(key, 0) + 1

    released = {
        (f["category_code"], f["sub_item_code"])
        for f in buyers.list_released_folders(engagement)
    }
    # Only folders Trinity has actually created in Drive have a link; the rest
    # are created on first upload, so their link is simply not there yet.
    links = drive_folders.mapped_web_links(engagement.id)
    folders = [
        {
            "category_code": key[0],
            "category": value.get("category"),
            "sub_item_code": key[1],
            "sub_item": value.get("sub_item"),
            "released_to_buyers": key in released,
            "file_count": counts.get(key, 0),
            "drive_web_link": links.get(key),
        }
        for key, value in sorted(buyers.folder_names(engagement.id).items())
    ]

    connected = drive_enabled()
    return {
        "status": {
            "connected": connected,
            "message": None if connected else
            "The Google Drive data room is not connected yet, so uploads are unavailable.",
        },
        "folders": folders,
        "files": [_file_view(f, names) for f in files],
        "data_room_web_link": links.get((None, None)),
    }


@router.post("/engagements/{engagement_id}/data-room/{category_code}/{sub_item_code}/files",
             response_model=DataRoomFile, status_code=status.HTTP_201_CREATED)
async def upload_data_room_file(
    engagement_id: UUID,
    category_code: str,
    sub_item_code: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload one document into a DD sub-item's folder.

    Streamed straight to Drive; Trinity keeps no copy. The DD items in that
    folder move to In progress unless an advisor has already answered them.
    """
    engagement = _engagement(engagement_id, db, current_user, require_advisor=True)
    try:
        media = get_data_room_service(db).upload(
            engagement, category_code, sub_item_code,
            file.file, file.filename or "document", file.content_type, current_user,
            size=getattr(file, "size", None),
        )
    except DataRoomError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except SharedDriveFolder as e:
        logger.error("Data room upload refused for engagement %s: %s", engagement_id, e)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="This engagement's Drive folder is shared with another engagement.")
    except DriveUnavailable as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    return _file_view(media, _uploader_names(db, [media]))


@router.get("/engagements/{engagement_id}/data-room/files/{media_id}/download")
async def download_data_room_file(
    engagement_id: UUID,
    media_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream a document to an advisor or owner. Authenticated, never a Drive link."""
    engagement = _engagement(engagement_id, db, current_user, require_advisor=False)
    service = get_data_room_service(db)
    media = service.get_file(engagement.id, media_id)
    if media is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    try:
        chunks = service.download_stream(media)
    except DriveUnavailable as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    return StreamingResponse(
        chunks,
        media_type=media.file_type or "application/octet-stream",
        headers={"Content-Disposition": content_disposition.attachment(media.file_name)},
    )


@router.patch("/engagements/{engagement_id}/data-room/files/{media_id}", response_model=DataRoomFile)
async def rename_data_room_file(
    engagement_id: UUID,
    media_id: UUID,
    body: FileRename,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _engagement(engagement_id, db, current_user, require_advisor=True)
    service = get_data_room_service(db)
    media = service.get_file(engagement.id, media_id)
    if media is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    try:
        media = service.rename(media, body.file_name)
    except DataRoomError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DriveUnavailable as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    return _file_view(media, _uploader_names(db, [media]))


@router.delete("/engagements/{engagement_id}/data-room/files/{media_id}",
               status_code=status.HTTP_204_NO_CONTENT)
async def delete_data_room_file(
    engagement_id: UUID,
    media_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trashed in Drive and soft-deleted here, so the access log keeps its subject."""
    engagement = _engagement(engagement_id, db, current_user, require_advisor=True)
    service = get_data_room_service(db)
    media = service.get_file(engagement.id, media_id)
    if media is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    try:
        service.delete(media)
    except DriveUnavailable as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    return None


# ----------------------------------------------------------------------
# Document register
# ----------------------------------------------------------------------
@router.get("/engagements/{engagement_id}/stages/{stage_code}/register",
            response_model=List[RegisterEntry])
async def get_document_register(
    engagement_id: UUID,
    stage_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generated from the files in this stage's folders, as the brief requires."""
    engagement = _engagement(engagement_id, db, current_user, require_advisor=True)
    return get_data_room_service(db).register_for_stage(engagement.id, stage_code)


@router.patch("/engagements/{engagement_id}/stages/{stage_code}/register/{media_id}",
              response_model=RegisterEntry)
async def update_document_register(
    engagement_id: UUID,
    stage_code: str,
    media_id: UUID,
    body: RegisterEntryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save the advisor-typed fields. Name, date and link come from the file."""
    engagement = _engagement(engagement_id, db, current_user, require_advisor=True)
    try:
        return get_data_room_service(db).update_register_entry(
            engagement, stage_code, media_id, body.model_dump(exclude_unset=True),
        )
    except DataRoomError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
