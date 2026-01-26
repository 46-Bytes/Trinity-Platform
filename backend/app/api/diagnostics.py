"""
Diagnostic API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, BackgroundTasks, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from pathlib import Path
from datetime import datetime
import os
import shutil
import logging
import time

logger = logging.getLogger(__name__)

from app.database import get_db, SessionLocal
from app.schemas.diagnostic import (
    DiagnosticCreate,
    DiagnosticResponse,
    DiagnosticDetail,
    DiagnosticResults,
    DiagnosticResponseUpdate,
    DiagnosticSubmit,
    DiagnosticListItem
)
from app.services.diagnostic_service import get_diagnostic_service
from app.services.file_service import get_file_service
from app.services.report_service import ReportService
from app.services.role_check import check_engagement_access
from app.utils.file_loader import load_diagnostic_questions
from app.utils.background_task_manager import background_task_manager
from app.utils.auth import get_current_user
from app.models.user import User, UserRole
from app.models.diagnostic import Diagnostic
from app.models.engagement import Engagement
from app.models.media import Media
import asyncio


router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.post("/create", response_model=DiagnosticResponse, status_code=status.HTTP_201_CREATED)
async def create_diagnostic(
    diagnostic_data: DiagnosticCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new diagnostic for an engagement.
    
    **Workflow Step 1**: Create diagnostic with questions loaded from JSON.
    
    Args:
        diagnostic_data: Diagnostic creation data
        
    Returns:
        Created diagnostic with questions structure
        
    Example:
        ```json
        {
            "engagement_id": "uuid",
            "created_by_user_id": "uuid",
            "diagnostic_type": "business_health_assessment",
            "diagnostic_version": "1.0"
        }
        ```
    """
    service = get_diagnostic_service(db)
    
    try:
        diagnostic = await service.create_diagnostic(
            engagement_id=diagnostic_data.engagement_id,
            created_by_user_id=diagnostic_data.created_by_user_id,
            diagnostic_type=diagnostic_data.diagnostic_type,
            diagnostic_version=diagnostic_data.diagnostic_version
        )
        
        return diagnostic
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create diagnostic: {str(e)}"
        )


@router.patch("/{diagnostic_id}/responses", response_model=DiagnosticDetail)
async def update_diagnostic_responses(
    diagnostic_id: UUID,
    update_data: DiagnosticResponseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update diagnostic responses (incremental autosave).
    
    **Workflow Step 2**: User fills out questions, responses saved incrementally.
    
    Args:
        diagnostic_id: UUID of the diagnostic
        update_data: Response updates
        
    Returns:
        Updated diagnostic with full details including user_responses
        
    Example:
        ```json
        {
            "user_responses": {
                "financial_performance_since_acquisition": "Better",
                "key_reports_review_frequency": "Weekly"
            },
            "status": "in_progress"
        }
        ```
    """
    service = get_diagnostic_service(db)
    
    try:
        diagnostic = await service.update_responses(
            diagnostic_id=diagnostic_id,
            user_responses=update_data.user_responses,
            status=update_data.status
        )
        
        # Return full diagnostic detail (includes user_responses)
        return diagnostic
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update responses: {str(e)}"
        )


@router.post("/{diagnostic_id}/upload-file")
async def upload_diagnostic_file(
    diagnostic_id: UUID,
    file: UploadFile = File(...),
    question_field_name: str = Query(
        None,
        description="Optional diagnostic question field name this file answers",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a supporting file for a diagnostic.

    This is a convenience wrapper around the shared FileService:

    - Stores the file locally under the per-user uploads directory
    - Uploads the file to OpenAI for analysis
    - Creates a `Media` record linked to the current user
    - Attaches the `Media` record to the given diagnostic

    The endpoint returns lightweight metadata that can be stored in
    `diagnostic.user_responses` by the frontend.
    """
    diagnostic_service = get_diagnostic_service(db)

    # Ensure diagnostic exists and the user has access (service will raise if not)
    diagnostic = diagnostic_service.get_diagnostic(diagnostic_id)
    if not diagnostic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnostic {diagnostic_id} not found",
        )

    # Use the shared file service so logic is consistent with /files/upload
    file_service = get_file_service(db)

    # Upload single file (store locally + OpenAI)
    # Use diagnostic_id for the file path: uploads/diagnostic/{diagnostic_id}/
    media = await file_service.upload_file(
        file=file,
        user_id=current_user.id,
        question_field_name=question_field_name,
        upload_to_openai=True,
        diagnostic_id=diagnostic_id,
    )

    # Attach to diagnostic via many-to-many relationship if not already linked
    if media not in diagnostic.media:
        diagnostic.media.append(media)
        db.commit()

    # Build a relative path for frontend display (relative to upload root)
    upload_root = file_service.upload_dir
    try:
        rel_path = Path(media.file_path).relative_to(upload_root).as_posix()
    except Exception:
        # Fallback to full path string if something goes wrong
        rel_path = media.file_path

    return {
        "file_name": media.file_name,
        "file_type": media.file_type,
        "file_size": media.file_size,
        "relative_path": rel_path,
        # Extra fields the frontend may use later
        "media_id": str(media.id),
        "openai_file_id": media.openai_file_id,
        "question_field_name": media.question_field_name,
        "uploaded_by_user_id": str(media.user_id),  # Include uploader's user_id for filtering
    }


@router.delete("/{diagnostic_id}/delete-file", response_model=DiagnosticDetail)
async def delete_diagnostic_file(
    diagnostic_id: UUID,
    field_name: str = Query(..., description="The question field name (e.g., 'supporting_documents')"),
    file_name: str = Query(..., description="The file name to delete (must match file_name in metadata)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a supporting file for a diagnostic.
    
    This endpoint:
    1. Deletes the file from disk
    2. Removes the file metadata from user_responses[field_name]
    
    Args:
        diagnostic_id: UUID of the diagnostic
        field_name: The question field name (e.g., "supporting_documents")
        file_name: The file name to delete (must match file_name in metadata)
        
    Returns:
        Updated diagnostic with file removed from user_responses
    """
    logger.info(f"DELETE file endpoint called - diagnostic_id: {diagnostic_id}, field_name: {field_name}, file_name: {file_name}")
    logger.info(f"Current user: {current_user.email if current_user else 'None'}")
    
    try:
        service = get_diagnostic_service(db)
        logger.info(f"Service created: {service}")
        
        # Ensure diagnostic exists and the user has access
        diagnostic = service.get_diagnostic(diagnostic_id)
        if not diagnostic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Diagnostic {diagnostic_id} not found"
            )
        
        # Get current user_responses
        user_responses = diagnostic.user_responses or {}
        logger.info(f"Current user_responses keys: {list(user_responses.keys())}")
        
        # Get the file list for this field
        field_value = user_responses.get(field_name)
        if not field_value:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No files found for field '{field_name}'"
            )
        
        logger.info(f"Field value type: {type(field_value)}, value: {field_value}")
        
        # Normalize to array
        files_list = field_value if isinstance(field_value, list) else [field_value]
        logger.info(f"Files list: {files_list}")
        logger.info(f"Looking for file_name: '{file_name}' (type: {type(file_name)})")
        
        # Find the file to remove - use exact matching
        file_to_remove = None
        for idx, file_meta in enumerate(files_list):
            file_name_in_meta = file_meta.get("file_name")
            logger.info(f"Comparing file[{idx}]: '{file_name_in_meta}' (type: {type(file_name_in_meta)}) == '{file_name}'")
            if file_name_in_meta == file_name:
                file_to_remove = file_meta
                logger.info(f"Found matching file at index {idx}")
                break
        
        if not file_to_remove:
            available_files = [f.get("file_name") for f in files_list]
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File '{file_name}' not found in field '{field_name}'. Available files: {available_files}"
            )
        
        # Delete file from disk
        base_dir = Path(__file__).resolve().parents[2] / "files"
        relative_path = file_to_remove.get("relative_path")
        logger.info(f"Relative path: {relative_path}")
        logger.info(f"Base dir: {base_dir}")
        
        if relative_path:
            file_path = base_dir / relative_path
            logger.info(f"Full file path: {file_path}")
            logger.info(f"File exists: {file_path.exists()}")
            if file_path.exists():
                try:
                    file_path.unlink()
                    logger.info(f"File deleted successfully: {file_path}")
                except Exception as e:
                    # Log error but continue with metadata removal
                    logger.warning(f"Could not delete file {file_path}: {str(e)}")
        
        # Remove file from user_responses
        # Use exact matching to ensure we remove the correct file
        updated_files = []
        removed_count = 0
        for f in files_list:
            file_name_in_meta = f.get("file_name")
            # Exact match (case-sensitive)
            if file_name_in_meta != file_name:
                updated_files.append(f)
            else:
                removed_count += 1
                logger.info(f"Removing file: {file_name_in_meta} (matched {file_name})")

        # Soft-delete corresponding Media record and detach from diagnostic, if media_id is present
        media_id = file_to_remove.get("media_id") if file_to_remove else None
        if media_id:
            try:
                media_obj = db.query(Media).filter(Media.id == media_id).first()
                if media_obj:
                    if not media_obj.deleted_at:
                        media_obj.deleted_at = datetime.utcnow()
                    if diagnostic and media_obj in diagnostic.media:
                        diagnostic.media.remove(media_obj)

                    db.flush()
            except Exception as e:
                logger.warning(f"Failed to soft-delete Media record for file '{file_name}': {str(e)}")
        
        if removed_count == 0:
            logger.warning(f"No files were removed! File '{file_name}' was not found in files_list")
        
        logger.info(f"Updated files list: {updated_files}")
        logger.info(f"Original files count: {len(files_list)}, Updated files count: {len(updated_files)}")
        
        # Update user_responses
        # IMPORTANT: We need to explicitly set the field to None or [] to remove it,
        # because update_responses uses dict.update() which doesn't remove missing keys
        updated_responses = {}
        if len(updated_files) == 0:
            # Set to None to explicitly remove the field
            updated_responses[field_name] = None
            logger.info(f"Setting field '{field_name}' to None (no files left)")
        else:
            # Update with remaining files (preserve array/single format)
            if isinstance(field_value, list):
                updated_responses[field_name] = updated_files
            else:
                # If it was a single file, now it's empty or should be null
                updated_responses[field_name] = updated_files[0] if updated_files else None
            logger.info(f"Updated field '{field_name}' with {len(updated_files)} remaining file(s)")
        
        # Update diagnostic via service
        logger.info(f"Calling service.update_responses with updated_responses: {updated_responses}")
        diagnostic = await service.update_responses(
            diagnostic_id=diagnostic_id,
            user_responses=updated_responses,
            status=None  # Don't change status
        )
        
        logger.info(f"File deletion completed successfully for {file_name}")
        return diagnostic
        
    except Exception as e:
        logger.error(f"Error in delete_diagnostic_file: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )


@router.post("/{diagnostic_id}/submit", response_model=DiagnosticResponse)
async def submit_diagnostic(
    diagnostic_id: UUID,
    submit_data: DiagnosticSubmit,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit diagnostic and trigger AI processing pipeline (asynchronous background job).
    
    This endpoint returns immediately with status "processing".
    The actual AI processing runs in the background and may take 10-15 minutes.
    
    **Workflow Step 3**: Main AI processing workflow (runs in background):
    1. Generate Q&A extract
    2. Generate summary
    3. Process scores with GPT
    4. Calculate module averages and rankings
    5. Determine RAG status
    6. Generate roadmap
    7. Generate advisor report
    8. Auto-generate tasks
    9. Generate PDF report
    
    **Frontend should poll GET /diagnostics/{diagnostic_id} to check status:**
    - "processing" = Still running
    - "completed" = Ready, PDF available for download
    - "failed" = Error occurred
    
    Args:
        diagnostic_id: UUID of the diagnostic
        submit_data: Submission data
        background_tasks: FastAPI background tasks
        
    Returns:
        Diagnostic with status "processing" (will be updated to "completed" when done)
        
    Example:
        ```json
        {
            "completed_by_user_id": "uuid"
        }
        ```
    """
    response.headers["Connection"] = "keep-alive"
    response.headers["Keep-Alive"] = "timeout=1800, max=100"

    service = get_diagnostic_service(db)
    
    # Get diagnostic first to verify it exists
    diagnostic = service.get_diagnostic(diagnostic_id)
    if not diagnostic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnostic {diagnostic_id} not found"
        )
    
    if not diagnostic.user_responses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot submit diagnostic without responses"
        )
    
    # Auto-tag diagnostic if submitted by Admin/Super Admin and tag is empty
    if current_user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        if not diagnostic.tag or diagnostic.tag.strip() == "":
            diagnostic.tag = "Diagnostic report by Admin"
    
    # Update status to processing immediately
    diagnostic.status = "processing"
    diagnostic.completed_by_user_id = submit_data.completed_by_user_id
    db.commit()
    db.refresh(diagnostic)
    
    # Add background task for processing
    async def process_diagnostic_background():
        """Background task to process diagnostic and generate PDF"""
        # Create a new database session for background task
        background_db = SessionLocal()
        task = None
        pipeline_start_time = time.time()
        
        try:
            logger.info(f"🚀 Starting background processing for diagnostic {diagnostic_id}")
            logger.info(f"[Background Task] Task registered at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Check if shutdown was initiated before starting
            if background_task_manager.is_shutting_down():
                logger.warning(f"  Shutdown detected before starting diagnostic {diagnostic_id} processing")
                # Update status back to draft or leave as processing
                try:
                    diagnostic_obj = background_db.query(Diagnostic).filter(Diagnostic.id == diagnostic_id).first()
                    if diagnostic_obj:
                        diagnostic_obj.status = "draft"  # Reset to draft so user can resubmit
                        background_db.commit()
                except Exception as e:
                    logger.error(f"Failed to reset diagnostic status: {e}")
                finally:
                    background_db.close()
                return
            
            # Get current task for tracking
            task = asyncio.current_task()
            if task:
                background_task_manager.register_task(task, diagnostic_id)
                logger.info(f"[Background Task] Task registered with background_task_manager")
            
            background_service = get_diagnostic_service(background_db)
            diagnostic_obj = background_service.get_diagnostic(diagnostic_id)
            
            if not diagnostic_obj:
                logger.error(f"  Diagnostic {diagnostic_id} not found in background task")
                return
            
            logger.info(f"[Background Task] Starting diagnostic pipeline processing...")
            logger.info(f"[Background Task] Diagnostic status: {diagnostic_obj.status}")
            logger.info(f"[Background Task] Diagnostic engagement_id: {diagnostic_obj.engagement_id}")
            
            # Process the diagnostic pipeline (with shutdown checks)
            await background_service._process_diagnostic_pipeline(diagnostic_obj, check_shutdown=True)
            
            pipeline_elapsed = time.time() - pipeline_start_time
            logger.info(f"[Background Task] ✅ Diagnostic pipeline completed in {pipeline_elapsed:.2f} seconds ({pipeline_elapsed/60:.2f} minutes)")
            
            # Generate PDF report after processing is complete
            try:
                logger.info(f"📄 Generating PDF report for diagnostic {diagnostic_id}")
                
                # Get user for report
                report_user_id = diagnostic_obj.completed_by_user_id or diagnostic_obj.created_by_user_id
                report_user = background_db.query(User).filter(User.id == report_user_id).first()
                
                if report_user:
                    # Build question text map
                    question_text_map = {}
                    diagnostic_questions = diagnostic_obj.questions or {}
                    for page in diagnostic_questions.get("pages", []):
                        for element in page.get("elements", []):
                            element_name = element.get("name")
                            element_title = element.get("title", element_name)
                            if element_name:
                                question_text_map[element_name] = element_title
                    
                    # Generate PDF (this will be stored/cached for download)
                    pdf_bytes = ReportService.generate_pdf_report(
                        diagnostic=diagnostic_obj,
                        user=report_user,
                        question_text_map=question_text_map
                    )
                    logger.info(f"  PDF report generated successfully ({len(pdf_bytes)} bytes)")
                else:
                    logger.warning(f"  Could not find user for PDF generation")
                    
            except Exception as pdf_error:
                logger.error(f"  PDF generation failed (non-critical): {str(pdf_error)}", exc_info=True)
                # Don't fail the whole process if PDF generation fails
            
            # Update status to completed
            diagnostic_obj.status = "completed"
            diagnostic_obj.completed_at = datetime.utcnow()
            
            # Update engagement status
            engagement = background_db.query(Engagement).filter(
                Engagement.id == diagnostic_obj.engagement_id
            ).first()
            if engagement and engagement.status != "completed":
                engagement.status = "completed"
                if not engagement.completed_at:
                    engagement.completed_at = datetime.utcnow()
                logger.info(f"  Updated engagement {engagement.id} status to 'completed'")
            
            background_db.commit()
            
            total_elapsed = time.time() - pipeline_start_time
            logger.info(f"[Background Task] ✅✅✅ Background processing completed successfully for diagnostic {diagnostic_id} ✅✅✅")
            logger.info(f"[Background Task] Total processing time: {total_elapsed:.2f} seconds ({total_elapsed/60:.2f} minutes)")
            logger.info(f"[Background Task] Completed at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            
        except asyncio.CancelledError:
            elapsed = time.time() - pipeline_start_time
            logger.warning(f"[Background Task] ⚠️ Background processing cancelled for diagnostic {diagnostic_id} (shutdown detected)")
            logger.warning(f"[Background Task] Processing was cancelled after {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")
            # Update status to indicate it was cancelled
            try:
                diagnostic_obj = background_db.query(Diagnostic).filter(Diagnostic.id == diagnostic_id).first()
                if diagnostic_obj:
                    diagnostic_obj.status = "draft"  # Reset to draft so user can resubmit after redeploy
                    background_db.commit()
                    logger.info(f"[Background Task] Updated diagnostic {diagnostic_id} status to 'draft' (cancelled due to shutdown)")
            except Exception as update_error:
                logger.error(f"[Background Task] Failed to update diagnostic status after cancellation: {str(update_error)}")
            raise  # Re-raise to properly handle cancellation
        except Exception as e:
            elapsed = time.time() - pipeline_start_time
            error_msg = str(e)
            error_type = type(e).__name__
            
            logger.error(f"[Background Task] ❌❌❌ Background processing FAILED for diagnostic {diagnostic_id} ❌❌❌")
            logger.error(f"[Background Task] Failed after {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")
            logger.error(f"[Background Task] Error type: {error_type}")
            logger.error(f"[Background Task] Error message: {error_msg}")
            logger.error(f"[Background Task] Full exception traceback:", exc_info=True)
            
            # Check if shutdown was the cause
            if background_task_manager.is_shutting_down():
                logger.warning(f"[Background Task] Shutdown was detected - this may have caused the failure")
                try:
                    diagnostic_obj = background_db.query(Diagnostic).filter(Diagnostic.id == diagnostic_id).first()
                    if diagnostic_obj:
                        diagnostic_obj.status = "draft"
                        background_db.commit()
                        logger.info(f"[Background Task] Updated diagnostic {diagnostic_id} status to 'draft' (shutdown detected)")
                except Exception as update_error:
                    logger.error(f"[Background Task] Failed to update diagnostic status: {str(update_error)}")
            else:
                logger.error(f"[Background Task] This was NOT a shutdown-related failure")
                # Update status to failed
                try:
                    diagnostic_obj = background_service.get_diagnostic(diagnostic_id)
                    if diagnostic_obj:
                        diagnostic_obj.status = "failed"
                        background_db.commit()
                        logger.info(f"[Background Task] Updated diagnostic {diagnostic_id} status to 'failed'")
                    else:
                        logger.error(f"[Background Task] Could not find diagnostic {diagnostic_id} to update status")
                except Exception as update_error:
                    logger.error(f"[Background Task] Failed to update diagnostic status to 'failed': {str(update_error)}")
        finally:
            background_db.close()
    
    # Add the background task
    background_tasks.add_task(process_diagnostic_background)
    
    logger.info(f"  Diagnostic {diagnostic_id} submitted, processing in background")
    
    return diagnostic


@router.get("/{diagnostic_id}/status")
async def get_diagnostic_status(
    diagnostic_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get diagnostic processing status (optimized for polling).
    
    This lightweight endpoint is designed for frontend polling to check
    if background processing is complete.
    
    Returns:
        {
            "status": "processing" | "completed" | "failed" | "draft",
            "completed_at": "2024-01-01T00:00:00" | null,
            "error": "error message" | null
        }
    """
    diagnostic = db.query(Diagnostic).filter(Diagnostic.id == diagnostic_id).first()
    
    if not diagnostic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnostic {diagnostic_id} not found"
        )
    
    return {
        "status": diagnostic.status,
        "completed_at": diagnostic.completed_at.isoformat() if diagnostic.completed_at else None,
        "error": None  # Could add error field to Diagnostic model if needed
    }


@router.get("/{diagnostic_id}", response_model=DiagnosticDetail)
async def get_diagnostic(
    diagnostic_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed diagnostic information.
    
    Returns complete diagnostic with questions, responses, scores, and AI analysis.
    
    Args:
        diagnostic_id: UUID of the diagnostic
        
    Returns:
        Detailed diagnostic data
    """
    service = get_diagnostic_service(db)
    
    diagnostic = service.get_diagnostic(diagnostic_id)
    
    if not diagnostic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnostic {diagnostic_id} not found"
        )
    
    return diagnostic


@router.get("/{diagnostic_id}/results", response_model=DiagnosticResults)
async def get_diagnostic_results(
    diagnostic_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get diagnostic results (scores, roadmap, report).
    
    Lightweight endpoint for displaying results without full questions/responses.
    
    Args:
        diagnostic_id: UUID of the diagnostic
        
    Returns:
        Diagnostic results with scores and AI analysis
    """
    service = get_diagnostic_service(db)
    
    diagnostic = service.get_diagnostic(diagnostic_id)
    
    if not diagnostic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnostic {diagnostic_id} not found"
        )
    
    if diagnostic.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Diagnostic is not yet completed"
        )
    
    return diagnostic


@router.get("/engagement/{engagement_id}", response_model=List[DiagnosticListItem])
async def list_engagement_diagnostics(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all diagnostics for an engagement.
    
    Args:
        engagement_id: UUID of the engagement
        
    Returns:
        List of diagnostics for the engagement
    """
    service = get_diagnostic_service(db)
    
    diagnostics = service.get_engagement_diagnostics(engagement_id)
    
    return diagnostics


@router.post("/{diagnostic_id}/regenerate-report", response_model=DiagnosticResponse)
async def regenerate_diagnostic_report(
    diagnostic_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Regenerate advisor report for a completed diagnostic.
    
    Useful for refreshing the report without reprocessing all scores.
    
    Args:
        diagnostic_id: UUID of the diagnostic
        
    Returns:
        Updated diagnostic with new report
    """
    service = get_diagnostic_service(db)
    
    try:
        diagnostic = await service.regenerate_report(diagnostic_id)
        
        return diagnostic
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate report: {str(e)}"
        )


@router.patch("/{diagnostic_id}/tag")
async def update_diagnostic_tag(
    diagnostic_id: UUID,
    tag: str = Form(None, description="Tag text (null to remove tag)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update tag for a diagnostic report (advisor-only).
    
    Args:
        diagnostic_id: UUID of the diagnostic
        tag: Tag text (null to remove tag)
        
    Returns:
        Success message
    """
    
    if current_user.role not in [UserRole.ADVISOR, UserRole.FIRM_ADVISOR, UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only advisors can tag documents"
        )
    
    diagnostic = db.query(Diagnostic).filter(Diagnostic.id == diagnostic_id).first()
    if not diagnostic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diagnostic not found"
        )
    
    engagement = db.query(Engagement).filter(Engagement.id == diagnostic.engagement_id).first()
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found"
        )
    
    if not check_engagement_access(engagement, current_user) and current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to tag this diagnostic"
        )
    
    diagnostic.tag = tag.strip() if tag and tag.strip() else None
    db.commit()
    db.refresh(diagnostic)
    
    return {
        "success": True,
        "message": "Tag updated successfully",
        "diagnostic_id": str(diagnostic_id),
        "tag": diagnostic.tag
    }


@router.get("/{diagnostic_id}/download")
async def download_diagnostic_report(
    diagnostic_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Download diagnostic report as PDF.
    
    Generates a comprehensive PDF report containing:
    - Header (User, Date)
    - Diagnostic Summary
    - Diagnostic Advice
    - Scoring Section (Scored Responses, Client Summary, Roadmap)
    - All Responses
    
    Args:
        diagnostic_id: UUID of the diagnostic
        
    Returns:
        PDF file download
    """
    try:
        diagnostic = db.query(Diagnostic).filter(Diagnostic.id == diagnostic_id).first()
        
        if not diagnostic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Diagnostic not found"
            )
        
        if diagnostic.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Diagnostic must be completed before downloading report"
            )
        
        question_text_map = {}
        diagnostic_questions = diagnostic.questions or {}
        
        for page in diagnostic_questions.get("pages", []):
            for element in page.get("elements", []):
                element_name = element.get("name")
                element_title = element.get("title", element_name)
                if element_name:
                    question_text_map[element_name] = element_title
        
        report_user_id = diagnostic.completed_by_user_id or diagnostic.created_by_user_id
        report_user = db.query(User).filter(User.id == report_user_id).first()
        
        if not report_user:
            report_user = current_user
        
        pdf_bytes = ReportService.generate_pdf_report(
            diagnostic=diagnostic,
            user=report_user,
            question_text_map=question_text_map
        )
        
        filename = ReportService.get_download_filename(diagnostic, report_user)
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating PDF report: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate report: {str(e)}"
        )

