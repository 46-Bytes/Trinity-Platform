"""
POC: File Upload API endpoint for OpenAI Files API integration
This is a standalone POC, separate from the main file upload system.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Request
from typing import List, Dict, Any
import tempfile
import os
import logging
from app.services.openai_service import OpenAIService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["upload-poc"])


@router.post("/upload", status_code=status.HTTP_200_OK)
async def upload_files_poc(
    request: Request,
    files: List[UploadFile] = File(...)
) -> Dict[str, Any]:
    """
    POC endpoint to upload multiple files and forward them to OpenAI Files API.
    
    This endpoint:
    1. Accepts multiple file uploads
    2. Uploads each file to OpenAI Files API
    3. Gets file_id for each file
    4. Stores filename → file_id mapping in session state
    
    Args:
        files: List of files to upload
        request: FastAPI request object (for session access)
        
    Returns:
        Dictionary with uploaded files and their OpenAI file_ids
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided"
        )
    
    # Initialize OpenAI service
    openai_service = OpenAIService()
    
    # Results storage
    results = []
    file_mapping = {}
    
    # Process each file
    for file in files:
        try:
            # Read file content
            file_content = await file.read()
            file_size = len(file_content)
            
            logger.info(f"Processing file: {file.filename} (size: {file_size} bytes)")
            
            # Create temporary file for OpenAI upload
            # OpenAI Files API requires a file-like object
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
                    
                    # Store mapping
                    file_mapping[filename] = file_id
                    
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
    
    # Store file mapping in session state
    if request:
        # Initialize session if it doesn't exist
        if "file_mappings" not in request.session:
            request.session["file_mappings"] = {}
        
        # Update session with new mappings
        request.session["file_mappings"].update(file_mapping)
        request.session.modified = True
        
        logger.info(f"Stored {len(file_mapping)} file mappings in session")
    
    # Return results
    return {
        "success": True,
        "message": f"Processed {len(files)} file(s)",
        "files": results,
        "file_mapping": file_mapping,
        "total_files": len(files),
        "successful_uploads": len([r for r in results if r["status"] == "success"])
    }


@router.get("/upload/mappings")
async def get_file_mappings(request: Request) -> Dict[str, Any]:
    """
    Get current file_id mappings from session state.
    
    Args:
        request: FastAPI request object (for session access)
        
    Returns:
        Dictionary with filename → file_id mappings
    """
    if not request or "file_mappings" not in request.session:
        return {
            "success": True,
            "file_mappings": {},
            "count": 0
        }
    
    file_mappings = request.session.get("file_mappings", {})
    
    return {
        "success": True,
        "file_mappings": file_mappings,
        "count": len(file_mappings)
    }


@router.delete("/upload/mappings")
async def clear_file_mappings(request: Request) -> Dict[str, Any]:
    """
    Clear all file_id mappings from session state.
    
    Args:
        request: FastAPI request object (for session access)
        
    Returns:
        Success message
    """
    if request and "file_mappings" in request.session:
        request.session["file_mappings"] = {}
        request.session.modified = True
    
    return {
        "success": True,
        "message": "File mappings cleared"
    }
