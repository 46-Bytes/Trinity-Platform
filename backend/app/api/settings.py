from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
import os
import time

from app.database import get_db
from app.models.user import User
from app.services.storage_service import get_storage_service
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
        
        # Store profile pictures under uploads/users/{user_id}/profilepicture/
        storage = get_storage_service()
        prefix = f"uploads/users/{user.id}/profilepicture"
        storage.delete_prefix(prefix)

        # Normalize .jpeg to .jpg
        if file_ext == '.jpeg':
            file_ext = '.jpg'
        filename = f"profilepicture_{int(time.time())}{file_ext}"
        storage_key = f"{prefix}/{filename}"

        try:
            content = await profile_picture.read()
            storage.write_bytes(storage_key, content)
        finally:
            await profile_picture.close()

        # Store relative URL in picture field — the frontend prepends the
        # API base URL for any value that isn't already an absolute URL.
        user.picture = f"/files/{storage_key}"

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
    if user.picture and user.picture.startswith('/files/'):
        try:
            get_storage_service().delete_prefix(f"uploads/users/{user.id}/profilepicture")
        except Exception as e:
            # Log error but continue - we'll still clear the DB field
            print(f"Error deleting profile picture file: {e}")


    user.picture = None
    
    db.add(user)
    db.commit()
    db.refresh(user)

    return user.to_dict()



