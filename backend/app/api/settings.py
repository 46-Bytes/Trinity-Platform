from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from pathlib import Path
import os
import shutil
import time

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
        user.first_name = first_name.strip() or None
    if last_name is not None:
        user.last_name = last_name.strip() or None

    # Keep full name in sync if we have first/last
    if first_name is not None or last_name is not None:
        parts = []
        if user.first_name:
            parts.append(user.first_name)
        if user.last_name:
            parts.append(user.last_name)
        user.name = " ".join(parts) if parts else user.name

    if email is not None:
        if user.auth0_id:
            pass
        else:
            user.email = email.strip() or user.email

    if bio is not None:
        # Requires a 'bio' column on User model
        if hasattr(user, "bio"):
            user.bio = bio.strip() or None

    # Handle profile picture upload
    if profile_picture is not None:
        # Validate file type - only allow JPG, JPEG and PNG
        original_name = os.path.basename(profile_picture.filename or "profilepicture")
        file_ext = os.path.splitext(original_name)[1].lower()
        allowed_extensions = ['.jpg', '.jpeg', '.png']
        
        if file_ext not in allowed_extensions:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail=f"Invalid file type. Only JPG and PNG files are allowed. Received: {file_ext}")
        
        # Base files directory (backend/files)
        base_dir = Path(__file__).resolve().parents[2] / "files"
        # Store profile pictures in files/uploads/users/{user_id}/profilepicture/
        profile_picture_dir = base_dir / "uploads" / "users" / str(user.id) / "profilepicture"
        profile_picture_dir.mkdir(parents=True, exist_ok=True)

        # Remove any existing profile pictures in this directory
        for existing in profile_picture_dir.iterdir():
            if existing.is_file():
                try:
                    existing.unlink()
                except Exception:
                    pass

        # Normalize .jpeg to .jpg
        if file_ext == '.jpeg':
            file_ext = '.jpg'
        filename = f"profilepicture_{int(time.time())}{file_ext}"

        destination = profile_picture_dir / filename

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


@router.delete("/profile/picture")
async def remove_profile_picture(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Remove the current user's profile picture.
    
    This endpoint:
    1. Deletes the profile picture file from the filesystem
    2. Sets the user's picture field to None
    """
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="User not found")

    # If user has a profile picture, delete it
    if user.picture:
        # Base files directory (backend/files)
        base_dir = Path(__file__).resolve().parents[2] / "files"
        
        if user.picture.startswith('/files/'):
            rel_path = user.picture.replace('/files/', '')
            picture_path = base_dir / rel_path
            
            # Delete the file if it exists
            if picture_path.exists() and picture_path.is_file():
                try:
                    picture_path.unlink()
                except Exception as e:
                    # Log error but continue - we'll still clear the DB field
                    print(f"Error deleting profile picture file: {e}")
        
        # Also try to delete entire directory if it's empty
        profile_picture_dir = base_dir / "uploads" / "users" / str(user.id) / "profilepicture"
        if profile_picture_dir.exists():
            try:
                # Remove directory if empty
                if not any(profile_picture_dir.iterdir()):
                    profile_picture_dir.rmdir()
            except Exception:
                pass  # Directory not empty or other error, that's fine
    

    user.picture = None
    
    db.add(user)
    db.commit()
    db.refresh(user)

    return user.to_dict()



