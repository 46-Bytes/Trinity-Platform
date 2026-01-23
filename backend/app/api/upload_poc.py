"""
POC: File Upload API endpoint for OpenAI Files API integration
This is a standalone POC, separate from the main file upload system.
Now uses database (BBA model) instead of session storage.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from uuid import UUID
import tempfile
import os
import logging
from app.services.openai_service import OpenAIService
from app.services.bba_service import get_bba_service, BBAService
from app.utils.auth import get_current_user
from app.models.user import User
from app.database import get_db
from app.schemas.bba import BBAQuestionnaire, BBAResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/poc", tags=["upload-poc"])


@router.post("/create-project", status_code=status.HTTP_201_CREATED)
async def create_bba_project(
    engagement_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Create a new BBA project.
    
    Returns:
        Dictionary with project ID
    """
    bba_service = get_bba_service(db)
    bba = bba_service.create_bba(
        user_id=current_user.id,
        engagement_id=engagement_id
    )
    
    return {
        "success": True,
        "project_id": str(bba.id),
        "status": bba.status
    }


@router.post("/{project_id}/upload", status_code=status.HTTP_200_OK)
async def upload_files_poc(
    project_id: UUID,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Upload multiple files to OpenAI Files API and store in BBA project.
    
    This endpoint:
    1. Accepts multiple file uploads
    2. Uploads each file to OpenAI Files API
    3. Gets file_id for each file
    4. Stores file_ids in BBA project in database
    
    Args:
        project_id: BBA project ID
        files: List of files to upload
        
    Returns:
        Dictionary with uploaded files and their OpenAI file_ids
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided"
        )
    
    # Verify project exists and belongs to user
    bba_service = get_bba_service(db)
    bba = bba_service.get_bba(project_id)
    if not bba:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="BBA project not found"
        )
    
    if bba.created_by_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this project"
        )
    
    # Initialize OpenAI service
    openai_service = OpenAIService()
    
    # Results storage
    results = []
    file_mapping = {}
    file_ids = []
    
    # Process each file
    for file in files:
        try:
            # Read file content
            file_content = await file.read()
            file_size = len(file_content)
            
            logger.info(f"Processing file: {file.filename} (size: {file_size} bytes)")
            
            # Create temporary file for OpenAI upload
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name
            
            try:
                # Upload to OpenAI Files API
                openai_result = await openai_service.upload_file(
                    file_path=temp_file_path,
                    purpose="assistants"  # Standard purpose for file uploads
                )
                
                if openai_result and openai_result.get("id"):
                    file_id = openai_result["id"]
                    filename = file.filename
                    
                    # Store mapping and file_id
                    file_mapping[filename] = file_id
                    file_ids.append(file_id)
                    
                    results.append({
                        "filename": filename,
                        "file_id": file_id,
                        "status": "success",
                        "size": file_size,
                        "openai_info": {
                            "bytes": openai_result.get("bytes"),
                            "purpose": openai_result.get("purpose"),
                            "created_at": openai_result.get("created_at")
                        }
                    })
                    
                    logger.info(f"Successfully uploaded {filename} to OpenAI. File ID: {file_id}")
                else:
                    results.append({
                        "filename": file.filename,
                        "file_id": None,
                        "status": "error",
                        "error": "OpenAI upload returned no file_id"
                    })
                    logger.error(f"OpenAI upload failed for {file.filename}: No file_id returned")
                    
            except Exception as openai_error:
                logger.error(f"OpenAI upload error for {file.filename}: {str(openai_error)}", exc_info=True)
                results.append({
                    "filename": file.filename,
                    "file_id": None,
                    "status": "error",
                    "error": str(openai_error)
                })
            finally:
                # Clean up temporary file
                try:
                    if os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup temp file {temp_file_path}: {str(cleanup_error)}")
                    
        except Exception as e:
            logger.error(f"Error processing file {file.filename}: {str(e)}", exc_info=True)
            results.append({
                "filename": file.filename,
                "file_id": None,
                "status": "error",
                "error": str(e)
            })
    
    # Update BBA project with file information
    if file_ids:
        # Merge with existing file_ids if any
        existing_file_ids = bba.file_ids or []
        existing_file_mappings = bba.file_mappings or {}
        
        updated_file_ids = list(set(existing_file_ids + file_ids))
        updated_file_mappings = {**existing_file_mappings, **file_mapping}
        
        bba_service.update_files(
            bba_id=project_id,
            file_ids=updated_file_ids,
            file_mappings=updated_file_mappings
        )
        
        logger.info(f"Updated BBA project {project_id} with {len(updated_file_ids)} file(s)")
    
    # Return results
    return {
        "success": True,
        "message": f"Processed {len(files)} file(s)",
        "files": results,
        "file_mapping": file_mapping,
        "total_files": len(files),
        "successful_uploads": len([r for r in results if r["status"] == "success"]),
        "project_id": str(project_id)
    }


@router.post("/{project_id}/submit-questionnaire", status_code=status.HTTP_200_OK)
async def submit_questionnaire(
    project_id: UUID,
    questionnaire: BBAQuestionnaire,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Submit questionnaire data for BBA project (Step 2).
    
    Args:
        project_id: BBA project ID
        questionnaire: Questionnaire data
        
    Returns:
        Updated BBA project data
    """
    # Verify project exists and belongs to user
    bba_service = get_bba_service(db)
    bba = bba_service.get_bba(project_id)
    if not bba:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="BBA project not found"
        )
    
    if bba.created_by_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this project"
        )
    
    # Update BBA with questionnaire data
    updated_bba = bba_service.update_questionnaire(project_id, questionnaire)
    
    if not updated_bba:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update questionnaire"
        )
    
    return {
        "success": True,
        "message": "Questionnaire submitted successfully",
        "project": updated_bba.to_dict()
    }


@router.get("/{project_id}", status_code=status.HTTP_200_OK)
async def get_bba_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get BBA project by ID.
    
    Args:
        project_id: BBA project ID
        
    Returns:
        BBA project data
    """
    bba_service = get_bba_service(db)
    bba = bba_service.get_bba(project_id)
    
    if not bba:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="BBA project not found"
        )
    
    if bba.created_by_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this project"
        )
    
    return {
        "success": True,
        "project": bba.to_dict()
    }


@router.get("/", status_code=status.HTTP_200_OK)
async def list_bba_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get all BBA projects for the current user.
    
    Returns:
        List of BBA projects
    """
    bba_service = get_bba_service(db)
    projects = bba_service.get_user_bba_projects(current_user.id)
    
    return {
        "success": True,
        "projects": [project.to_dict() for project in projects],
        "count": len(projects)
    }
