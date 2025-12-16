from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from pathlib import Path
import os
import shutil

from app.database import get_db
from app.models.user import User
from app.utils.auth import get_current_user


router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/profile")
async def get_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the current user's profile settings.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    return current_user.to_dict()


@router.put("/profile")
async def update_profile(
    first_name: str = Form(None),
    last_name: str = Form(None),
    email: str = Form(None),
    bio: str = Form(None),
    profile_picture: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update the current user's profile information and optional profile picture.

    Accepts multipart/form-data with:
      - first_name (optional)
      - last_name (optional)
      - email (optional)
      - bio (optional)
      - profile_picture (optional file)
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Update basic fields
    if first_name is not None:
        user.given_name = first_name.strip() or None
    if last_name is not None:
        user.family_name = last_name.strip() or None

    # Keep full name in sync if we have first/last
    if first_name is not None or last_name is not None:
        parts = []
        if user.given_name:
            parts.append(user.given_name)
        if user.family_name:
            parts.append(user.family_name)
        user.name = " ".join(parts) if parts else user.name

    if email is not None:
        user.email = email.strip() or user.email

    if bio is not None:
        # Requires a 'bio' column on User model
        if hasattr(user, "bio"):
            user.bio = bio.strip() or None

    # Handle profile picture upload
    if profile_picture is not None:
        # Base files directory (backend/files)
        base_dir = Path(__file__).resolve().parents[2] / "files"
        uploads_dir = base_dir / "uploads" / "users" / str(user.id)
        uploads_dir.mkdir(parents=True, exist_ok=True)

        for existing in uploads_dir.iterdir():
            if existing.is_file():
                try:
                    existing.unlink()
                except Exception:
                    pass

        # Sanitize filename
        original_name = os.path.basename(profile_picture.filename or "profile-picture")
        safe_name = original_name.replace("..", "_").replace("/", "_").replace("\\", "_")

        destination = uploads_dir / safe_name

        try:
            with destination.open("wb") as buffer:
                shutil.copyfileobj(profile_picture.file, buffer)
        finally:
            await profile_picture.close()

        # Store relative URL/path in picture field
        rel_path = destination.relative_to(base_dir).as_posix()
        user.picture = f"/files/{rel_path}"

    db.add(user)
    db.commit()
    db.refresh(user)

    return user.to_dict()



