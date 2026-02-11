"""
BBA Tool API: Phases 1 & 2

This module implements the backend for the Benchmark Business Advisory (BBA)
tool, including:

Phase 1 – Diagnostic Report Builder
-----------------------------------
- Step 1: File Upload
- Step 2: Context Capture / Questionnaire
- Step 3: Draft Findings
- Step 4: Expand Findings
- Step 5: Snapshot Table
- Step 6: 12-Month Plan
- Step 7: Review & Edit
- Export: Word document generation

Phase 2 – Excel Task List Generator (Engagement Planner)
--------------------------------------------------------
- Task planner context setup (advisors, capacity, start month/year)
- Recommendation-by-recommendation task generation & preview
- Excel (.xlsx) advisor task list export
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime
from pathlib import Path
import tempfile
import os
import logging
import io
from app.services.openai_service import OpenAIService
from app.services.bba_service import get_bba_service, BBAService
from app.services.bba_conversation_engine import get_bba_conversation_engine
from app.services.bba_task_planner_service import get_bba_task_planner_service
from app.services.bba_task_list_export import get_bba_task_list_exporter
from app.utils.auth import get_current_user
from app.models.user import User
from app.database import get_db
from app.services.bba_report_export import BBAReportExporter
from app.schemas.bba import (
    BBAQuestionnaire, 
    BBAResponse,
    BBADraftFindingsRequest,
    BBAFindingsEdit,
    BBAEditRequest,
    BBATaskPlannerSettings,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/poc", tags=["bba"])


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
        temp_file_path = None
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
                    if temp_file_path and os.path.exists(temp_file_path):
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


# =============================================================================
# STEP 3: Draft Findings
# =============================================================================

@router.post("/{project_id}/step3/generate", status_code=status.HTTP_200_OK)
async def generate_draft_findings(
    project_id: UUID,
    request: Optional[BBADraftFindingsRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Step 3: Generate draft findings from uploaded files.
    
    Analyses all uploaded documents and proposes a ranked list of
    top 10 findings with one-line summaries.
    
    Args:
        project_id: BBA project ID
        request: Optional additional instructions
        
    Returns:
        Draft findings for review
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
    
    # Check prerequisites
    if not bba.file_ids or len(bba.file_ids) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files uploaded. Please upload files first (Step 1)."
        )
    
    if not bba.client_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Questionnaire not completed. Please complete Step 2 first."
        )
    
    try:
        engine = get_bba_conversation_engine()
        custom_instructions = request.custom_instructions if request else None
        
        result = await engine.generate_draft_findings(bba, custom_instructions)
        
        # Save to database
        updated_bba = bba_service.update_draft_findings(
            bba_id=project_id,
            findings=result.get("findings", {}),
            tokens_used=result.get("tokens_used", 0),
            model=result.get("model", "")
        )
        
        return {
            "success": True,
            "message": "Draft findings generated successfully",
            "findings": result.get("findings", {}),
            "tokens_used": result.get("tokens_used", 0),
            "model": result.get("model", ""),
            "project": updated_bba.to_dict()
        }
        
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prompt template not found: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to generate draft findings: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate draft findings: {str(e)}"
        )


@router.post("/{project_id}/step3/confirm", status_code=status.HTTP_200_OK)
async def confirm_draft_findings(
    project_id: UUID,
    edited_findings: Optional[BBAFindingsEdit] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Confirm draft findings (optionally with edits) before proceeding.
    
    Args:
        project_id: BBA project ID
        edited_findings: Optional edited findings
        
    Returns:
        Confirmation status
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
    
    if not bba.draft_findings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No draft findings to confirm. Generate findings first."
        )
    
    # Convert edited findings to dict if provided
    findings_dict = None
    if edited_findings:
        findings_dict = {
            "findings": [f.model_dump() for f in edited_findings.findings]
        }
    
    updated_bba = bba_service.confirm_draft_findings(project_id, findings_dict)
    
    return {
        "success": True,
        "message": "Draft findings confirmed",
        "edited": edited_findings is not None,
        "project": updated_bba.to_dict()
    }


# =============================================================================
# STEP 4: Expand Findings
# =============================================================================

@router.post("/{project_id}/step4/generate", status_code=status.HTTP_200_OK)
async def expand_findings(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Step 4: Expand findings into full paragraphs.
    
    Takes the draft findings and writes 1-3 paragraphs per finding
    describing the issue and its implications.
    
    Args:
        project_id: BBA project ID
        
    Returns:
        Expanded findings
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
    
    if not bba.draft_findings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No draft findings. Complete Step 3 first."
        )
    
    try:
        engine = get_bba_conversation_engine()
        result = await engine.expand_findings(bba)
        
        # Save to database
        updated_bba = bba_service.update_expanded_findings(
            bba_id=project_id,
            expanded_findings=result.get("expanded_findings", {}),
            tokens_used=result.get("tokens_used", 0),
            model=result.get("model", "")
        )
        
        return {
            "success": True,
            "message": "Findings expanded successfully",
            "expanded_findings": result.get("expanded_findings", {}),
            "tokens_used": result.get("tokens_used", 0),
            "model": result.get("model", ""),
            "project": updated_bba.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Failed to expand findings: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to expand findings: {str(e)}"
        )


# =============================================================================
# STEP 5: Snapshot Table
# =============================================================================

@router.post("/{project_id}/step5/generate", status_code=status.HTTP_200_OK)
async def generate_snapshot_table(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Step 5: Generate the Key Findings & Recommendations Snapshot table.
    
    Creates a concise three-column table:
    Priority Area | Key Findings | Recommendations
    
    Args:
        project_id: BBA project ID
        
    Returns:
        Snapshot table data
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
    
    if not bba.expanded_findings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No expanded findings. Complete Step 4 first."
        )
    
    try:
        engine = get_bba_conversation_engine()
        result = await engine.generate_snapshot_table(bba)
        
        # Save to database
        updated_bba = bba_service.update_snapshot_table(
            bba_id=project_id,
            snapshot_table=result.get("snapshot_table", {}),
            tokens_used=result.get("tokens_used", 0),
            model=result.get("model", "")
        )
        
        return {
            "success": True,
            "message": "Snapshot table generated successfully",
            "snapshot_table": result.get("snapshot_table", {}),
            "tokens_used": result.get("tokens_used", 0),
            "model": result.get("model", ""),
            "project": updated_bba.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Failed to generate snapshot table: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate snapshot table: {str(e)}"
        )


# =============================================================================
# STEP 6: 12-Month Plan
# =============================================================================

@router.post("/{project_id}/step6/generate", status_code=status.HTTP_200_OK)
async def generate_12month_plan(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Step 6: Generate the 12-Month Recommendations Plan.
    
    For each finding, creates a recommendation with:
    - Purpose
    - Key Objectives (3-5 bullets)
    - Actions to Complete (5-10 points)
    - BBA Support Outline
    - Expected Outcomes
    
    Args:
        project_id: BBA project ID
        
    Returns:
        12-month plan data
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
    
    if not bba.expanded_findings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No expanded findings. Complete Step 4 first."
        )
    
    try:
        engine = get_bba_conversation_engine()
        result = await engine.generate_12month_plan(bba)
        
        # Extract plan notes if present
        plan_data = result.get("twelve_month_plan", {})
        plan_notes = plan_data.get("plan_notes", None)
        
        # Save to database
        updated_bba = bba_service.update_twelve_month_plan(
            bba_id=project_id,
            twelve_month_plan=plan_data,
            plan_notes=plan_notes,
            tokens_used=result.get("tokens_used", 0),
            model=result.get("model", "")
        )
        
        return {
            "success": True,
            "message": "12-month plan generated successfully",
            "twelve_month_plan": plan_data,
            "tokens_used": result.get("tokens_used", 0),
            "model": result.get("model", ""),
            "project": updated_bba.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Failed to generate 12-month plan: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate 12-month plan: {str(e)}"
        )


# =============================================================================
# STEP 7: Review & Edit
# =============================================================================

@router.patch("/{project_id}/review/edit", status_code=status.HTTP_200_OK)
async def apply_report_edits(
    project_id: UUID,
    edit_request: BBAEditRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Step 7: Apply edits to the report.
    
    Handles edit requests such as:
    - Re-ranking findings
    - Adjusting timing
    - Changing language
    - Adding/removing recommendations
    
    Args:
        project_id: BBA project ID
        edit_request: Edit instructions
        
    Returns:
        Updated report sections
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
    
    try:
        engine = get_bba_conversation_engine()
        edits = edit_request.model_dump()
        
        result = await engine.apply_edits(bba, edits)
        
        # Apply updates to database
        updated_sections = result.get("updated_report", {})
        updated_bba = bba_service.apply_edits(project_id, updated_sections)
        
        return {
            "success": True,
            "message": "Edits applied successfully",
            "changes_made": result.get("changes_made", []),
            "warnings": result.get("warnings", []),
            "tokens_used": result.get("tokens_used", 0),
            "project": updated_bba.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Failed to apply edits: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply edits: {str(e)}"
        )


@router.post("/{project_id}/executive-summary/generate", status_code=status.HTTP_200_OK)
async def generate_executive_summary(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Generate the Executive Summary section.
    
    Args:
        project_id: BBA project ID
        
    Returns:
        Executive summary text
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
    
    if not bba.expanded_findings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No expanded findings. Complete Step 4 first."
        )
    
    try:
        engine = get_bba_conversation_engine()
        result = await engine.generate_executive_summary(bba)
        
        # Save to database
        updated_bba = bba_service.update_executive_summary(
            bba_id=project_id,
            executive_summary=result.get("executive_summary", ""),
            tokens_used=result.get("tokens_used", 0),
            model=result.get("model", "")
        )
        
        return {
            "success": True,
            "message": "Executive summary generated successfully",
            "executive_summary": result.get("executive_summary", ""),
            "tokens_used": result.get("tokens_used", 0),
            "project": updated_bba.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Failed to generate executive summary: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate executive summary: {str(e)}"
        )


# =============================================================================
# EXPORT: Word Document
# =============================================================================

@router.post("/{project_id}/export/docx", status_code=status.HTTP_200_OK)
async def export_to_word(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export the complete report to Word document (.docx).
    
    Args:
        project_id: BBA project ID
        
    Returns:
        Word document file download
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
    
    # Check that we have enough data to export
    if not bba.expanded_findings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Report not ready for export. Complete at least Step 4."
        )
    
    try:
        
        exporter = BBAReportExporter()
        doc_bytes = exporter.generate_report(bba)
        
        # Update final report in database
        final_report = {
            "executive_summary": bba.executive_summary,
            "snapshot_table": bba.snapshot_table,
            "expanded_findings": bba.expanded_findings,
            "twelve_month_plan": bba.twelve_month_plan,
            "exported_at": datetime.utcnow().isoformat()
        }
        bba_service.update_final_report(project_id, final_report)
        
        # Create filename
        client_name = bba.client_name or "Client"
        filename = f"{client_name.replace(' ', '_')} - Diagnostic Findings and Recommendations Report.docx"
        
        # Return as streaming response
        return StreamingResponse(
            io.BytesIO(doc_bytes),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Word export not available. Install python-docx."
        )
    except Exception as e:
        logger.error(f"Failed to export to Word: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export to Word: {str(e)}"
        )


# =============================================================================
# PHASE 2 – Excel Task Planner (Engagement Planner)
# =============================================================================


@router.post("/{project_id}/tasks/settings", status_code=status.HTTP_200_OK)
async def configure_task_planner_settings(
    project_id: UUID,
    settings: BBATaskPlannerSettings,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Configure Phase 2 task planner settings for a BBA project.

    Captures:
    - Lead and support advisors
    - Total advisors on the engagement
    - Maximum advisor hours per month
    - Engagement start month/year

    These values are stored on the BBA record and reused for task generation
    and Excel export.
    """
    bba_service = get_bba_service(db)
    bba = bba_service.get_bba(project_id)

    if not bba:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="BBA project not found",
        )

    if bba.created_by_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this project",
        )

    # Require that the 12‑month plan exists before enabling the task planner
    if not bba.twelve_month_plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "12-month plan has not been generated yet. "
                "Complete Step 6 before configuring the task planner."
            ),
        )

    task_planner_service = get_bba_task_planner_service(db)
    updated_bba = task_planner_service.save_settings(project_id, settings)

    return {
        "success": True,
        "message": "Task planner settings saved successfully",
        "settings": settings.model_dump(),
        "project": updated_bba.to_dict(),
    }


@router.post("/{project_id}/tasks/preview", status_code=status.HTTP_200_OK)
async def preview_task_planner(
    project_id: UUID,
    settings: Optional[BBATaskPlannerSettings] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Generate a preview of Phase 2 task planner rows for a BBA project.

    - Uses existing stored settings, or updates them if a new settings payload
      is provided in the request body.
    - Builds Client and BBA task rows for each recommendation in the 12‑month
      plan.
    - Calculates total BBA hours and monthly capacity utilisation.
    - Stores tasks and summary back on the BBA record.
    """
    bba_service = get_bba_service(db)
    bba = bba_service.get_bba(project_id)

    if not bba:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="BBA project not found",
        )

    if bba.created_by_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this project",
        )

    if not bba.twelve_month_plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "12-month plan has not been generated yet. "
                "Complete Step 6 before generating the task planner."
            ),
        )

    openai_service = OpenAIService()
    task_planner_service = get_bba_task_planner_service(db, openai_service)

    # Determine effective settings: use provided payload if present,
    # otherwise fall back to stored settings.
    if settings:
        effective_settings = settings
        task_planner_service.save_settings(project_id, effective_settings)
    else:
        try:
            effective_settings = task_planner_service.load_settings(bba)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

    try:
        tasks, summary = await task_planner_service.generate_tasks_and_summary(
            bba=bba,
            settings=effective_settings,
        )
        updated_bba = task_planner_service.save_tasks_and_summary(
            bba_id=project_id,
            tasks=tasks,
            summary=summary,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "Failed to generate task planner preview for BBA %s: %s",
            project_id,
            str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate task planner preview: {str(e)}",
        )

    return {
        "success": True,
        "message": "Task planner preview generated successfully",
        "settings": effective_settings.model_dump(),
        "tasks": tasks,
        "summary": summary,
        "project": updated_bba.to_dict(),
    }


@router.post("/{project_id}/tasks/export/excel")
async def export_task_planner_excel(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate the Excel (.xlsx) advisor task list for a BBA project.

    Behaviour:
    - Uses stored task planner settings (must be configured first)
    - Uses stored task rows & summary if present
      – otherwise regenerates them from the 12‑month plan
    - Returns a streaming Excel file download
    """
    bba_service = get_bba_service(db)
    bba = bba_service.get_bba(project_id)

    if not bba:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="BBA project not found",
        )

    if bba.created_by_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this project",
        )

    if not bba.twelve_month_plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "12-month plan has not been generated yet. "
                "Complete Step 6 before exporting the Excel task list."
            ),
        )

    openai_service = OpenAIService()
    task_planner_service = get_bba_task_planner_service(db, openai_service)

    try:
        settings = task_planner_service.load_settings(bba)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Use existing tasks/summary if available; otherwise regenerate
    tasks = bba.task_planner_tasks
    summary = bba.task_planner_summary

    if not tasks or not summary:
        try:
            tasks, summary = await task_planner_service.generate_tasks_and_summary(
                bba=bba,
                settings=settings,
            )
            task_planner_service.save_tasks_and_summary(
                bba_id=project_id,
                tasks=tasks,
                summary=summary,
            )
        except Exception as e:
            logger.error(
                "Failed to generate task planner data for Excel export (BBA %s): %s",
                project_id,
                str(e),
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate task planner data for Excel export: {str(e)}",
            )

    try:
        exporter = get_bba_task_list_exporter()
        excel_bytes = exporter.generate_workbook_bytes(tasks=tasks, summary=summary or {})
    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "Failed to generate Excel workbook for BBA %s: %s",
            project_id,
            str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate Excel workbook: {str(e)}",
        )

    # Build a safe filename for the download
    client_name = bba.client_name or "Client"
    safe_client_name = "".join(
        c for c in client_name if c.isalnum() or c in (" ", "_", "-")
    ).strip() or "Client"
    safe_client_name = safe_client_name.replace(" ", "_")
    file_name = f"{safe_client_name}_Advisor_Task_List.xlsx"

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{file_name}"',
        },
    )
