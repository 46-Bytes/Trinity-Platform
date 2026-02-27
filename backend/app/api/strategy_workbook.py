"""
Strategy Workbook API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status, Form
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional
from uuid import UUID
from pathlib import Path
import io
import logging
import traceback

logger = logging.getLogger(__name__)

from app.database import get_db
from app.utils.auth import get_current_user
from app.models.user import User
from app.models.strategy_workbook import StrategyWorkbook
from app.models.diagnostic import Diagnostic
from app.models.engagement import Engagement
from app.models.media import Media
from app.services.role_check import check_engagement_access
from app.services.strategy_workbook_service import get_strategy_workbook_service
from app.services.strategy_workbook_exporter import get_strategy_workbook_exporter
from app.services.file_service import get_file_service
from app.schemas.strategy_workbook import (
    StrategyWorkbookResponse,
    StrategyWorkbookUploadResponse,
    StrategyWorkbookExtractRequest,
    StrategyWorkbookExtractResponse,
    StrategyWorkbookGenerateRequest,
    StrategyWorkbookGenerateResponse,
    StrategyWorkbookPrecheckRequest,
    StrategyWorkbookPrecheckResponse,
)

router = APIRouter(prefix="/strategy-workbook", tags=["strategy-workbook"])


@router.post("/create-from-diagnostic", status_code=status.HTTP_201_CREATED)
async def create_from_diagnostic(
    diagnostic_id: UUID = Query(..., description="Completed diagnostic ID to create strategy workbook from"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Create a strategy workbook from a completed diagnostic. The diagnostic
    report is stored as context for the workbook. Idempotent: if a workbook
    already exists for this diagnostic, returns the existing workbook.
    """
    diagnostic = db.query(Diagnostic).filter(Diagnostic.id == diagnostic_id).first()
    if not diagnostic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic not found")
    if diagnostic.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Diagnostic must be completed (current status: {diagnostic.status})",
        )
    engagement = db.query(Engagement).filter(
        Engagement.id == diagnostic.engagement_id,
        Engagement.is_deleted == False,
    ).first()
    if not engagement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engagement not found")
    if not check_engagement_access(engagement, current_user, db=db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this engagement",
        )
    service = get_strategy_workbook_service(db)
    try:
        workbook = service.create_from_diagnostic(diagnostic_id=diagnostic_id, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {
        "success": True,
        "workbook_id": str(workbook.id),
        "engagement_id": str(workbook.engagement_id) if workbook.engagement_id else None,
        "diagnostic_id": str(workbook.diagnostic_id) if workbook.diagnostic_id else None,
    }


@router.post("/upload", status_code=status.HTTP_201_CREATED, response_model=StrategyWorkbookUploadResponse)
async def upload_documents(
    files: List[UploadFile] = File(...),
    workbook_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload documents for strategy workbook analysis.

    Files are:
    1. Stored locally
    2. Uploaded to OpenAI for AI analysis
    3. Attached to an existing or new strategy workbook session

    Args:
        files: List of files to upload (PDF, DOCX, XLSX, images, etc.)
        workbook_id: Optional existing workbook ID to upload files to

    Returns:
        Workbook ID and uploaded file metadata
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one file must be uploaded"
        )

    try:
        logger.info(f"Starting strategy workbook upload for user {current_user.id} with {len(files)} files")

        service = get_strategy_workbook_service(db)

        # Use existing workbook if provided, otherwise create a new one
        if workbook_id:
            from uuid import UUID as PyUUID
            workbook = service.get_workbook(PyUUID(workbook_id))
            if not workbook:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Workbook not found"
                )
            logger.info(f"Using existing workbook: {workbook.id}")
        else:
            logger.info("Service created, creating workbook...")
            workbook = service.create_workbook(user_id=current_user.id)
            logger.info(f"Workbook created: {workbook.id}")

        # Upload files
        file_service = get_file_service(db)
        logger.info("Uploading files...")
        uploaded_media = await file_service.upload_files(
            files=files,
            user_id=current_user.id,
            upload_to_openai=True
        )
        logger.info(f"Files uploaded: {len(uploaded_media)} files")

        # Attach files to workbook
        media_ids = [media.id for media in uploaded_media]
        logger.info(f"Attaching {len(media_ids)} files to workbook...")
        workbook = service.attach_files(workbook_id=workbook.id, media_ids=media_ids)
        logger.info("Files attached successfully")

        return StrategyWorkbookUploadResponse(
            workbook_id=workbook.id,
            status=workbook.status,
            uploaded_files=[media.to_dict() for media in uploaded_media],
            message=f"Successfully uploaded {len(uploaded_media)} file(s)"
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Strategy workbook upload failed: {str(e)}\n{error_trace}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File upload failed: {str(e)}"
        )


@router.post("/extract", response_model=StrategyWorkbookExtractResponse)
async def extract_data(
    request: StrategyWorkbookExtractRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Extract strategic data from uploaded documents using AI.
    
    This endpoint:
    1. Analyzes all uploaded documents
    2. Extracts structured strategic information
    3. Stores extracted data in the workbook
    
    Args:
        request: Contains workbook_id
        
    Returns:
        Extracted data and status
    """
    try:
        service = get_strategy_workbook_service(db)
        
        # Get workbook
        workbook = service.get_workbook(request.workbook_id)
        if not workbook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workbook not found"
            )
        
        # Extract data (optionally using advisor clarification notes)
        extracted_data = await service.extract_data(
            workbook_id=request.workbook_id,
            clarification_notes=request.clarification_notes,
        )
        
        # Refresh workbook
        db.refresh(workbook)
        
        return StrategyWorkbookExtractResponse(
            workbook_id=workbook.id,
            status=workbook.status,
            extracted_data=extracted_data,
            message="Data extraction completed successfully"
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Data extraction failed for workbook {request.workbook_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Data extraction failed for workbook {request.workbook_id}: {str(e)}\n{error_trace}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Data extraction failed: {str(e)}. Check server logs for details."
        )


@router.post("/precheck", response_model=StrategyWorkbookPrecheckResponse)
async def precheck_workbook(
    request: StrategyWorkbookPrecheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Run a lightweight LLM precheck on the uploaded documents to:
    - Confirm they are broadly suitable for extraction
    - Surface any important ambiguities or issues as clarification questions
    """
    try:
        service = get_strategy_workbook_service(db)

        # Get workbook
        workbook = service.get_workbook(request.workbook_id)
        if not workbook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workbook not found",
            )

        result = await service.precheck_workbook(request.workbook_id)

        return StrategyWorkbookPrecheckResponse(
            workbook_id=workbook.id,
            status=result.get("status", "ok"),
            clarification_questions=result.get("clarification_questions", []),
            message=result.get("message", "Precheck completed successfully"),
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Precheck failed for workbook {request.workbook_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(
            f"Precheck failed for workbook {request.workbook_id}: {str(e)}\n{error_trace}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Precheck failed: {str(e)}. Check server logs for details.",
        )


@router.post("/generate", response_model=StrategyWorkbookGenerateResponse)
async def generate_workbook(
    request: StrategyWorkbookGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate the prefilled Excel workbook from extracted data.
    
    This endpoint:
    1. Loads the Strategy Workbook Template
    2. Maps extracted data to the correct cells
    3. Preserves all formatting, dropdowns, and validation
    4. Generates the completed workbook file
    
    Args:
        request: Contains workbook_id and optional review_notes
        
    Returns:
        Download URL and status
    """
    try:
        service = get_strategy_workbook_service(db)
        
        # Get workbook
        workbook = service.get_workbook(request.workbook_id)
        if not workbook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workbook not found"
            )
        
        if workbook.status != "ready":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Workbook status must be 'ready' to generate. Current status: {workbook.status}"
            )
        
        if not workbook.extracted_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No extracted data found. Please run extraction first."
            )
        
        # Update notes if provided
        if request.review_notes:
            workbook.notes = request.review_notes
            db.commit()
        
        # Generate workbook
        exporter = get_strategy_workbook_exporter()
        
        # Create output directory
        base_dir = Path(__file__).resolve().parents[2]  # Go up to backend/
        output_dir = base_dir / "files" / "uploads" / "strategy-workbook" / str(workbook.id)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = output_dir / "Strategy_Workshop_Workbook.xlsx"
        
        # Generate workbook bytes
        workbook_bytes = exporter.generate_workbook(
            extracted_data=workbook.extracted_data,
            output_path=output_path
        )
        
        # Update workbook record
        workbook.generated_workbook_path = str(output_path)
        workbook.status = "completed"
        from datetime import datetime
        workbook.completed_at = datetime.utcnow()
        db.commit()
        
        # Generate download URL
        download_url = f"/api/strategy-workbook/{workbook.id}/download"
        
        logger.info(f"Workbook {workbook.id} generated successfully. Download URL: {download_url}")
        
        return StrategyWorkbookGenerateResponse(
            workbook_id=workbook.id,
            status=workbook.status,
            download_url=download_url,
            message="Workbook generated successfully"
        )
        
    except HTTPException:
        raise
    except FileNotFoundError as e:
        error_trace = traceback.format_exc()
        logger.error(f"Template file not found for workbook {request.workbook_id}: {e}\n{error_trace}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Template file not found: {str(e)}. Ensure 'Strategy Workbook Template.xlsx' is in the correct location."
        )
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Workbook generation failed for workbook {request.workbook_id}: {str(e)}\n{error_trace}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Workbook generation failed: {str(e)}. Check server logs for details."
        )


@router.get("/{workbook_id}", response_model=StrategyWorkbookResponse)
async def get_workbook(
    workbook_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get workbook status and metadata.
    
    Args:
        workbook_id: ID of the workbook
        
    Returns:
        Workbook details
    """
    service = get_strategy_workbook_service(db)
    
    workbook = service.get_workbook(workbook_id)
    if not workbook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workbook not found"
        )
    
    return workbook


@router.get("/{workbook_id}/download")
async def download_workbook(
    workbook_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Download the generated workbook file.
    
    Args:
        workbook_id: ID of the workbook
        
    Returns:
        Excel file download
    """
    service = get_strategy_workbook_service(db)
    
    workbook = service.get_workbook(workbook_id)
    if not workbook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workbook not found"
        )
    
    if not workbook.generated_workbook_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workbook has not been generated yet"
        )
    
    file_path = Path(workbook.generated_workbook_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workbook file not found"
        )
    
    return FileResponse(
        path=str(file_path),
        filename="Strategy_Workshop_Workbook.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

