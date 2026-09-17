"""
Help / Video User Guide API endpoints.

Viewing the help section is open to all authenticated users. Managing content
(create / update / delete / reorder categories and videos) is restricted to
super_admin and admin.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from uuid import UUID

from ..database import get_db
from ..models.user import User, UserRole
from ..models.help_video import HelpVideoCategory, HelpVideo
from ..schemas.help_video import (
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse,
    CategoryWithVideos,
    VideoCreate,
    VideoUpdate,
    VideoResponse,
    ReorderRequest,
)
from ..utils.auth import get_current_user, require_role
from ..utils.youtube import extract_youtube_id

router = APIRouter(prefix="/api/help", tags=["help"])

# Only super_admin and admin may manage help content.
admin_required = require_role([UserRole.SUPER_ADMIN, UserRole.ADMIN])


# ------------------------------ Helpers -----------------------------

def _get_category_or_404(db: Session, category_id: UUID) -> HelpVideoCategory:
    category = db.query(HelpVideoCategory).filter(
        HelpVideoCategory.id == category_id,
        HelpVideoCategory.is_deleted == False,
    ).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")
    return category


def _get_video_or_404(db: Session, video_id: UUID) -> HelpVideo:
    video = db.query(HelpVideo).filter(
        HelpVideo.id == video_id,
        HelpVideo.is_deleted == False,
    ).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")
    return video


def _next_category_position(db: Session) -> int:
    max_position = db.query(func.max(HelpVideoCategory.position)).filter(
        HelpVideoCategory.is_deleted == False,
    ).scalar()
    return (max_position + 1) if max_position is not None else 0


def _next_video_position(db: Session, category_id: UUID) -> int:
    max_position = db.query(func.max(HelpVideo.position)).filter(
        HelpVideo.category_id == category_id,
        HelpVideo.is_deleted == False,
    ).scalar()
    return (max_position + 1) if max_position is not None else 0


# --------------------- Public (any authenticated user) --------------------

@router.get("/categories", response_model=List[CategoryWithVideos])
async def list_categories_with_videos(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all categories with their ordered, non-deleted videos."""
    categories = (
        db.query(HelpVideoCategory)
        .filter(HelpVideoCategory.is_deleted == False)
        .order_by(HelpVideoCategory.position.asc(), HelpVideoCategory.created_at.asc())
        .all()
    )

    result: List[CategoryWithVideos] = []
    for category in categories:
        videos = (
            db.query(HelpVideo)
            .filter(HelpVideo.category_id == category.id, HelpVideo.is_deleted == False)
            .order_by(HelpVideo.position.asc(), HelpVideo.created_at.asc())
            .all()
        )
        result.append(
            CategoryWithVideos(
                id=category.id,
                name=category.name,
                description=category.description,
                position=category.position,
                created_at=category.created_at,
                updated_at=category.updated_at,
                videos=[VideoResponse.model_validate(v) for v in videos],
            )
        )

    return result


# ----------------------- Category management (admin) ----------------------

@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    data: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """Create a new category (appended to the end)."""
    category = HelpVideoCategory(
        name=data.name,
        description=data.description,
        position=_next_category_position(db),
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return CategoryResponse.model_validate(category)


@router.patch("/categories/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: UUID,
    data: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """Update a category's name/description."""
    category = _get_category_or_404(db, category_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    db.commit()
    db.refresh(category)
    return CategoryResponse.model_validate(category)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """Soft-delete a category and its videos."""
    category = _get_category_or_404(db, category_id)
    category.is_deleted = True
    db.query(HelpVideo).filter(
        HelpVideo.category_id == category.id,
        HelpVideo.is_deleted == False,
    ).update({HelpVideo.is_deleted: True}, synchronize_session=False)
    db.commit()
    return None


@router.post("/categories/reorder", response_model=List[CategoryResponse])
async def reorder_categories(
    data: ReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """Rewrite category positions to match the given order."""
    categories = db.query(HelpVideoCategory).filter(
        HelpVideoCategory.id.in_(data.ordered_ids),
        HelpVideoCategory.is_deleted == False,
    ).all()
    category_map = {c.id: c for c in categories}
    for index, category_id in enumerate(data.ordered_ids):
        category = category_map.get(category_id)
        if category:
            category.position = index
    db.commit()

    updated = db.query(HelpVideoCategory).filter(
        HelpVideoCategory.is_deleted == False,
    ).order_by(HelpVideoCategory.position.asc()).all()
    return [CategoryResponse.model_validate(c) for c in updated]


# ------------------------- Video management (admin) -----------------------

@router.post("/videos", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
async def create_video(
    data: VideoCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """Create a video from a pasted YouTube URL (appended to its category)."""
    category = _get_category_or_404(db, data.category_id)

    video_id = extract_youtube_id(data.youtube_url)
    if video_id is None:  # defensive — schema already validated
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid YouTube URL.",
        )

    video = HelpVideo(
        category_id=category.id,
        youtube_video_id=video_id,
        title=data.title,
        description=data.description,
        position=_next_video_position(db, category.id),
        created_by_user_id=current_user.id,
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return VideoResponse.model_validate(video)


@router.patch("/videos/{video_id}", response_model=VideoResponse)
async def update_video(
    video_id: UUID,
    data: VideoUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """Update a video's title/description/category/URL."""
    video = _get_video_or_404(db, video_id)
    update_data = data.model_dump(exclude_unset=True)

    new_category_id = update_data.pop("category_id", None)
    youtube_url = update_data.pop("youtube_url", None)

    # Moving to a different category → append to the end of the new category.
    if new_category_id is not None and new_category_id != video.category_id:
        _get_category_or_404(db, new_category_id)
        video.category_id = new_category_id
        video.position = _next_video_position(db, new_category_id)

    if youtube_url is not None:
        extracted = extract_youtube_id(youtube_url)
        if extracted is None:  # defensive — schema already validated
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid YouTube URL.",
            )
        video.youtube_video_id = extracted

    for field, value in update_data.items():
        setattr(video, field, value)

    db.commit()
    db.refresh(video)
    return VideoResponse.model_validate(video)


@router.delete("/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(
    video_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """Soft-delete a video."""
    video = _get_video_or_404(db, video_id)
    video.is_deleted = True
    db.commit()
    return None


@router.post("/categories/{category_id}/videos/reorder", response_model=List[VideoResponse])
async def reorder_videos(
    category_id: UUID,
    data: ReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """Rewrite video positions within a category to match the given order."""
    _get_category_or_404(db, category_id)
    videos = db.query(HelpVideo).filter(
        HelpVideo.id.in_(data.ordered_ids),
        HelpVideo.category_id == category_id,
        HelpVideo.is_deleted == False,
    ).all()
    video_map = {v.id: v for v in videos}
    for index, vid in enumerate(data.ordered_ids):
        video = video_map.get(vid)
        if video:
            video.position = index
    db.commit()

    updated = db.query(HelpVideo).filter(
        HelpVideo.category_id == category_id,
        HelpVideo.is_deleted == False,
    ).order_by(HelpVideo.position.asc()).all()
    return [VideoResponse.model_validate(v) for v in updated]
