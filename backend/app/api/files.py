"""
File upload API endpoints for diagnostics
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Form
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database import get_db
from app.services.file_service import get_file_service
from app.models.media import Media
from app.models.diagnostic import Diagnostic
from app.utils.auth import get_current_user
from app.models.user import User


router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_files(
    files: List[UploadFile] = File(...),
    diagnostic_id: str = Form(None),
    question_field_name: str = Form(None),
    description: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload files for a diagnostic.
    
    Files are:
    1. Stored locally
    2. Uploaded to OpenAI for AI analysis
    3. Attached to the diagnostic (if diagnostic_id provided)
    
    Args:
        files: List of files to upload
        diagnostic_id: Optional UUID of diagnostic to attach files to
        question_field_name: Which diagnostic question these files answer
        description: Optional description
        
    Returns:
        List of uploaded file metadata
    """
    file_service = get_file_service(db)
    
    try:
        # Parse diagnostic_id if provided
        diagnostic_uuid = None
        if diagnostic_id:
            try:
                diagnostic_uuid = UUID(diagnostic_id)
            except ValueError:
                print(f"  Invalid diagnostic_id: {diagnostic_id}")
        
        # Upload files (pass diagnostic_id to use correct storage path)
        uploaded_media = await file_service.upload_files(
            files=files,
            user_id=current_user.id,
            question_field_name=question_field_name,
            upload_to_openai=True,
            diagnostic_id=diagnostic_uuid
        )
        
        # Attach files to diagnostic if diagnostic_id provided
        if diagnostic_uuid:
            try:
                diagnostic = db.query(Diagnostic).filter(
                    Diagnostic.id == diagnostic_uuid
                ).first()
                
                if diagnostic:
                    for media in uploaded_media:
                        if media not in diagnostic.media:
                            diagnostic.media.append(media)
                    db.commit()
                    print(f"  Attached {len(uploaded_media)} files to diagnostic {diagnostic_id}")
            except ValueError:
                print(f"  Invalid diagnostic_id: {diagnostic_id}")
        
        return {
            "success": True,
            "message": f"Successfully uploaded {len(uploaded_media)} file(s)",
            "files": [media.to_dict() for media in uploaded_media]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File upload failed: {str(e)}"
        )


@router.get("/diagnostic/{diagnostic_id}")
async def get_diagnostic_files(
    diagnostic_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all files attached to a diagnostic.
    
    Args:
        diagnostic_id: UUID of the diagnostic
        
    Returns:
        List of file metadata
    """
    file_service = get_file_service(db)
    
    try:
        files = file_service.get_diagnostic_files(diagnostic_id)
        
        return {
            "success": True,
            "diagnostic_id": str(diagnostic_id),
            "file_count": len(files),
            "files": [media.to_dict() for media in files]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve files: {str(e)}"
        )


@router.delete("/{file_id}")
async def delete_file(
    file_id: UUID,
    hard_delete: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a file (soft delete by default).
    
    Args:
        file_id: UUID of the file to delete
        hard_delete: If true, permanently delete; otherwise soft delete
        
    Returns:
        Success message
    """
    file_service = get_file_service(db)
    
    # Check if file belongs to current user
    media = db.query(Media).filter(Media.id == file_id).first()
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    if media.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this file"
        )
    
    try:
        success = file_service.delete_file(file_id, hard_delete=hard_delete)
        
        if success:
            return {
                "success": True,
                "message": "File deleted successfully"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )


@router.get("/user/files")
async def get_user_files(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all files uploaded by the current user.
    
    Returns:
        List of file metadata
    """
    file_service = get_file_service(db)
    
    try:
        files = file_service.get_user_files(current_user.id)
        
        return {
            "success": True,
            "file_count": len(files),
            "files": [media.to_dict() for media in files]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve files: {str(e)}"
        )

