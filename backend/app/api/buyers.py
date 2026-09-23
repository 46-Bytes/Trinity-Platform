"""
Buyer access: the advisor's controls and the buyer's own read-only portal.

Two routers with deliberately different shapes:

  - /api/engagements/{id}/buyers and /released-folders are advisor controls,
    behind the usual engagement access check. They never appear to a buyer,
    because check_engagement_access default-denies that role;
  - /api/buyer/* is everything a buyer can reach. It is GET-only by
    construction - there is no write verb on it at all - and the engagement is
    resolved from the caller's binding, never from a path parameter, so a buyer
    cannot name someone else's engagement.

Documents are streamed through Trinity, as the brief requires. A buyer never
receives a storage link, and every list, view and download is logged.
"""
import logging
import os
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.buyer import EngagementBuyer
from app.models.engagement import Engagement
from app.models.media import Media
from app.models.user import User, UserRole
from app.schemas.buyer import (
    AccessLogEntry,
    BuyerEngagementView,
    BuyerFolderView,
    BuyerInvite,
    BuyerUpdate,
    BuyerView,
    ReleasedFolderUpdate,
    ReleasedFolderView,
)
from app.services import buyer_rules as rules
from app.services.buyer_service import (
    BuyerConflict,
    BuyerNotFound,
    DataRoomNotConnected,
    get_buyer_service,
)
from app.services.role_check import check_engagement_access
from app.utils.auth import get_current_user

logger = logging.getLogger(__name__)

advisor_router = APIRouter(prefix="/api/engagements", tags=["buyers"])
buyer_router = APIRouter(prefix="/api/buyer", tags=["buyer-portal"])


def _run(action):
    """Map service errors to HTTP: conflict 400, missing record 404."""
    try:
        return action()
    except BuyerNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BuyerConflict as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ----------------------------------------------------------------------
# Advisor controls
# ----------------------------------------------------------------------
def _engagement_for_advisor(engagement_id: UUID, db: Session, user: User) -> Engagement:
    engagement = db.query(Engagement).filter(
        Engagement.id == engagement_id,
        Engagement.is_deleted == False,  # noqa: E712
    ).first()
    if not engagement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engagement not found")
    # Buyers fail this too: check_engagement_access default-denies their role.
    if not check_engagement_access(engagement, user, require_advisor=True, db=db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="You do not have access to this engagement")
    return engagement


@advisor_router.get("/{engagement_id}/buyers", response_model=List[BuyerView])
async def list_buyers(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _engagement_for_advisor(engagement_id, db, current_user)
    return get_buyer_service(db).list_buyers(engagement)


@advisor_router.post("/{engagement_id}/buyers", response_model=BuyerView,
                     status_code=status.HTTP_201_CREATED)
async def invite_buyer(
    engagement_id: UUID,
    body: BuyerInvite,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Invite a buyer to this engagement.

    Creates the Auth0 account and sends the password-setup email through the
    same path every other invited user takes. An email already belonging to a
    non-buyer account is refused and that account is left untouched.
    """
    engagement = _engagement_for_advisor(engagement_id, db, current_user)
    service = get_buyer_service(db)
    return _run(lambda: service.invite(
        engagement, body.email, current_user,
        first_name=body.first_name, last_name=body.last_name,
        nda_signed_date=body.nda_signed_date,
    ))


@advisor_router.patch("/{engagement_id}/buyers/{binding_id}", response_model=BuyerView)
async def update_buyer(
    engagement_id: UUID,
    binding_id: UUID,
    body: BuyerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record the NDA signed date. It does not gate access."""
    engagement = _engagement_for_advisor(engagement_id, db, current_user)
    service = get_buyer_service(db)
    return _run(lambda: service.update(engagement, binding_id, body.model_dump(exclude_unset=True)))


@advisor_router.post("/{engagement_id}/buyers/{binding_id}/revoke", response_model=BuyerView)
async def revoke_buyer(
    engagement_id: UUID,
    binding_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """End access. A soft delete - the row, the history and the log all survive."""
    engagement = _engagement_for_advisor(engagement_id, db, current_user)
    service = get_buyer_service(db)
    return _run(lambda: service.revoke(engagement, binding_id))


@advisor_router.post("/{engagement_id}/buyers/{binding_id}/restore", response_model=BuyerView)
async def restore_buyer(
    engagement_id: UUID,
    binding_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-grant a revoked buyer, on the same row."""
    engagement = _engagement_for_advisor(engagement_id, db, current_user)
    service = get_buyer_service(db)
    return _run(lambda: service.restore(engagement, binding_id))


@advisor_router.get("/{engagement_id}/released-folders", response_model=List[ReleasedFolderView])
async def list_released_folders(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engagement = _engagement_for_advisor(engagement_id, db, current_user)
    return get_buyer_service(db).list_released_folders(engagement)


@advisor_router.put("/{engagement_id}/released-folders", response_model=List[ReleasedFolderView])
async def set_released_folders(
    engagement_id: UUID,
    body: ReleasedFolderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Replace the set of folders visible to buyers. Folders left out are withdrawn.

    Released per DD sub-item, which is the folder the brief and the mockup
    describe. Nothing is released by default.
    """
    engagement = _engagement_for_advisor(engagement_id, db, current_user)
    service = get_buyer_service(db)
    return _run(lambda: service.set_released_folders(
        engagement, [f.model_dump() for f in body.folders], current_user,
    ))


@advisor_router.get("/{engagement_id}/buyer-access-log", response_model=List[AccessLogEntry])
async def buyer_access_log(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Every open and download by a buyer on this engagement, newest first."""
    engagement = _engagement_for_advisor(engagement_id, db, current_user)
    return get_buyer_service(db).access_log(engagement)


# ----------------------------------------------------------------------
# Buyer portal - GET only
# ----------------------------------------------------------------------
def require_buyer_engagement(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EngagementBuyer:
    """
    Resolve the one engagement this buyer may see.

    The engagement comes from the binding, never from the request, so a buyer
    cannot reach another engagement by changing a path parameter. A revoked
    buyer has no live binding and is refused here.
    """
    if current_user.role != UserRole.BUYER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="This area is for buyer accounts")
    binding = get_buyer_service(db).live_binding_for_user(current_user.id)
    if binding is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Your access to this data room has ended")
    return binding


@buyer_router.get("/me/engagement", response_model=BuyerEngagementView)
async def my_engagement(
    db: Session = Depends(get_db),
    binding: EngagementBuyer = Depends(require_buyer_engagement),
    current_user: User = Depends(get_current_user),
):
    service = get_buyer_service(db)
    engagement = db.query(Engagement).filter(Engagement.id == binding.engagement_id).first()
    folders = service.list_released_folders(engagement)
    service.log(binding.engagement_id, current_user, rules.ACTION_LIST, detail="engagement")
    return {
        "engagement_id": binding.engagement_id,
        "engagement_name": engagement.engagement_name if engagement else None,
        "business_name": engagement.business_name if engagement else None,
        "nda_signed_date": binding.nda_signed_date,
        "released_folder_count": len(folders),
    }


@buyer_router.get("/me/folders", response_model=List[ReleasedFolderView])
async def my_folders(
    db: Session = Depends(get_db),
    binding: EngagementBuyer = Depends(require_buyer_engagement),
    current_user: User = Depends(get_current_user),
):
    """Only the folders the advisor has released. Nothing else is listed."""
    service = get_buyer_service(db)
    engagement = db.query(Engagement).filter(Engagement.id == binding.engagement_id).first()
    folders = service.list_released_folders(engagement)
    service.log(binding.engagement_id, current_user, rules.ACTION_LIST, detail="folders")
    return folders


@buyer_router.get("/me/folders/{category_code}/{sub_item_code}", response_model=BuyerFolderView)
async def my_folder(
    category_code: str,
    sub_item_code: str,
    db: Session = Depends(get_db),
    binding: EngagementBuyer = Depends(require_buyer_engagement),
    current_user: User = Depends(get_current_user),
):
    """
    A released folder's contents.

    Empty until the Drive work lands - no document is filed against a DD
    sub-item yet. An unreleased folder is a 404, not an empty list, so its
    existence is not disclosed.
    """
    service = get_buyer_service(db)
    if not service.is_released(binding.engagement_id, category_code, sub_item_code):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    try:
        documents = service.documents_in_folder(binding.engagement_id, category_code, sub_item_code)
    except DataRoomNotConnected:
        # The folder is released and real; its contents are not reachable yet.
        documents = []
    service.log(binding.engagement_id, current_user, rules.ACTION_VIEW,
                detail=rules.folder_key(category_code, sub_item_code))
    return {
        "category_code": category_code,
        "sub_item_code": sub_item_code,
        "documents": [
            {"id": m.id, "file_name": m.file_name, "file_size": m.file_size,
             "file_type": m.file_type, "created_at": m.created_at}
            for m in documents
        ],
    }


@buyer_router.get("/me/documents/{media_id}/download")
async def download_document(
    media_id: UUID,
    db: Session = Depends(get_db),
    binding: EngagementBuyer = Depends(require_buyer_engagement),
    current_user: User = Depends(get_current_user),
):
    """
    Stream a released document through Trinity.

    Refused while the data room is unconnected. The release check is the only
    thing standing between a buyer and a document they were not shown, and it
    cannot be answered until a document knows which folder it is in - so this
    refuses first and looks nothing up. Nothing here may be relaxed without
    implementing BuyerService.media_is_released; the order below is the point.
    """
    service = get_buyer_service(db)
    try:
        released = service.media_is_released(binding.engagement_id, media_id)
    except DataRoomNotConnected as e:
        logger.info("Buyer %s attempted a download before the data room exists", current_user.id)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    if not released:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    media = db.query(Media).filter(
        Media.id == media_id,
        Media.engagement_id == binding.engagement_id,
        Media.is_active == True,  # noqa: E712
        Media.deleted_at.is_(None),
    ).first()
    if not media or not os.path.exists(media.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    service.log(binding.engagement_id, current_user, rules.ACTION_DOWNLOAD, media_id=media.id)
    return FileResponse(path=media.file_path, filename=media.file_name,
                        media_type=media.file_type or "application/octet-stream")
