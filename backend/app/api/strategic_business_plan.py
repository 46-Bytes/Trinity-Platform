"""
Strategic Business Plan API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional
from uuid import UUID
from pathlib import Path
import logging
import shutil
import uuid as uuid_mod

logger = logging.getLogger(__name__)

from app.database import get_db
from app.utils.auth import get_current_user
from app.models.user import User
from app.models.strategic_business_plan import StrategicBusinessPlan
from app.models.diagnostic import Diagnostic
from app.models.engagement import Engagement
from app.services.role_check import check_engagement_access
from app.services.sbp_service import get_sbp_service, SBPService
from app.schemas.strategic_business_plan import (
    SBPCreate,
    SBPSetup,
    SBPFileUpload,
    SBPCrossAnalysisRequest,
    SBPCrossAnalysisNotes,
    SBPDraftSectionRequest,
    SBPRevisionRequest,
    SBPSectionEdit,
    SBPAssembleRequest,
    SBPExportRequest,
    SBPStepProgressUpdate,
    SBPPresentationSlideEdit,
    SBPResponse,
    SBPListItem,
)

router = APIRouter(prefix="/strategic-business-plan", tags=["strategic-business-plan"])

# Upload directory
UPLOAD_DIR = Path(__file__).resolve().parents[2] / "files" / "uploads" / "sbp"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls", ".pptx", ".txt", ".csv", ".png", ".jpg", ".jpeg"}


def _get_plan_or_404(plan_id: UUID, db: Session) -> StrategicBusinessPlan:
    service = get_sbp_service(db)
    plan = service.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategic Business Plan not found")
    return plan


def _check_plan_access(plan: StrategicBusinessPlan, current_user: User, db: Session):
    if plan.engagement_id:
        engagement = db.query(Engagement).filter(
            Engagement.id == plan.engagement_id,
            Engagement.is_deleted == False,
        ).first()
        if engagement and not check_engagement_access(engagement, current_user, db=db):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_plan(
    engagement_id: Optional[UUID] = Query(None, description="Optional engagement ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    if engagement_id:
        engagement = db.query(Engagement).filter(
            Engagement.id == engagement_id,
            Engagement.is_deleted == False,
        ).first()
        if not engagement:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engagement not found")
        if not check_engagement_access(engagement, current_user, db=db):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    service = get_sbp_service(db)
    plan = service.create_plan(user_id=current_user.id, engagement_id=engagement_id)
    return {
        "success": True,
        "plan_id": str(plan.id),
        "engagement_id": str(plan.engagement_id) if plan.engagement_id else None,
    }


@router.post("/create-from-diagnostic", status_code=status.HTTP_201_CREATED)
async def create_from_diagnostic(
    diagnostic_id: UUID = Query(..., description="Completed diagnostic ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    diagnostic = db.query(Diagnostic).filter(Diagnostic.id == diagnostic_id).first()
    if not diagnostic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic not found")
    if diagnostic.engagement_id:
        engagement = db.query(Engagement).filter(
            Engagement.id == diagnostic.engagement_id,
            Engagement.is_deleted == False,
        ).first()
        if engagement and not check_engagement_access(engagement, current_user, db=db):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    service = get_sbp_service(db)
    plan = service.create_plan_from_diagnostic(diagnostic_id=diagnostic_id, user_id=current_user.id)
    return {
        "success": True,
        "plan_id": str(plan.id),
        "engagement_id": str(plan.engagement_id) if plan.engagement_id else None,
    }


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

@router.get("/{plan_id}")
async def get_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    plan = _get_plan_or_404(plan_id, db)
    _check_plan_access(plan, current_user, db)
    return plan.to_dict()


@router.get("/")
async def list_plans(
    engagement_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    service = get_sbp_service(db)
    if engagement_id:
        plans = service.get_plans_by_engagement(engagement_id, user_id=current_user.id)
    else:
        plans = (
            db.query(StrategicBusinessPlan)
            .filter(StrategicBusinessPlan.created_by_user_id == current_user.id)
            .order_by(StrategicBusinessPlan.updated_at.desc())
            .all()
        )
    return [p.to_dict() for p in plans]


# ---------------------------------------------------------------------------
# Step 1: Reset plan data (re-upload from scratch)
# ---------------------------------------------------------------------------

@router.post("/{plan_id}/reset")
async def reset_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    plan = _get_plan_or_404(plan_id, db)
    _check_plan_access(plan, current_user, db)
    service = get_sbp_service(db)
    plan = service.reset_plan_data(plan_id)
    return {"success": True, "plan": plan.to_dict()}


# ---------------------------------------------------------------------------
# Step 1: Upload files
# ---------------------------------------------------------------------------

@router.post("/{plan_id}/upload")
async def upload_files(
    plan_id: UUID,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    plan = _get_plan_or_404(plan_id, db)
    _check_plan_access(plan, current_user, db)

    plan_dir = UPLOAD_DIR / str(plan_id)
    plan_dir.mkdir(parents=True, exist_ok=True)

    file_ids = list(plan.file_ids or [])
    file_mappings = dict(plan.file_mappings or {})
    stored_files = dict(plan.stored_files or {})

    # Upload files to Claude Files API (same pattern as BBA tool)
    from app.services.claude_service import ClaudeService
    import tempfile
    import os

    claude_service = ClaudeService()

    uploaded = []
    for upload_file in files:
        ext = Path(upload_file.filename or "").suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type '{ext}' not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
            )

        content = await upload_file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File '{upload_file.filename}' exceeds 100 MB limit",
            )

        # 1. Save locally
        local_id = str(uuid_mod.uuid4())
        safe_name = f"{local_id}{ext}"
        file_path = plan_dir / safe_name
        with open(file_path, "wb") as f:
            f.write(content)

        # 2. Upload to Claude Files API
        claude_file_id = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            claude_result = await claude_service.upload_file(
                file_path=tmp_path,
                purpose="user_data",
            )
            if claude_result:
                claude_file_id = claude_result["id"]
        except Exception as e:
            logger.warning(f"Claude file upload failed for {upload_file.filename}: {e}")
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        # 3. Store Claude file_id (falls back to local UUID if upload failed)
        effective_id = claude_file_id or local_id
        filename = upload_file.filename or safe_name
        file_ids.append(effective_id)
        file_mappings[filename] = effective_id
        stored_files[filename] = f"{plan_id}/{safe_name}"

        uploaded.append({
            "filename": filename,
            "file_id": effective_id,
            "size": len(content),
        })

    service = get_sbp_service(db)
    service.save_file_upload(plan_id, file_ids, file_mappings, stored_files)

    return {"success": True, "uploaded_files": uploaded, "total_files": len(file_ids)}


# ---------------------------------------------------------------------------
# Step 1: Save setup / background info
# ---------------------------------------------------------------------------

@router.post("/{plan_id}/setup")
async def save_setup(
    plan_id: UUID,
    data: SBPSetup,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    plan = _get_plan_or_404(plan_id, db)
    _check_plan_access(plan, current_user, db)

    service = get_sbp_service(db)
    plan = service.save_setup(
        plan_id=plan_id,
        client_name=data.client_name,
        industry=data.industry,
        planning_horizon=data.planning_horizon,
        target_audience=data.target_audience,
        additional_context=data.additional_context,
    )
    return {"success": True, "plan": plan.to_dict()}


# ---------------------------------------------------------------------------
# Step 2: Cross-Analysis
# ---------------------------------------------------------------------------

@router.post("/{plan_id}/cross-analysis")
async def trigger_cross_analysis(
    plan_id: UUID,
    data: Optional[SBPCrossAnalysisRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    plan = _get_plan_or_404(plan_id, db)
    _check_plan_access(plan, current_user, db)

    # Validate that at least one file has been uploaded
    if not plan.file_ids or len(plan.file_ids) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files uploaded. Please upload at least one document before running cross-analysis.",
        )

    try:
        from app.services.sbp_conversation_engine import get_sbp_conversation_engine
        engine = get_sbp_conversation_engine(db)
        result = await engine.perform_cross_analysis(
            plan_id=plan_id,
            custom_instructions=data.custom_instructions if data else None,
        )
        return {"success": True, "cross_analysis": result}
    except Exception as e:
        logger.error(f"Cross-analysis failed for plan {plan_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Cross-analysis failed: {str(e)}")


@router.patch("/{plan_id}/cross-analysis")
async def save_cross_analysis_notes(
    plan_id: UUID,
    data: SBPCrossAnalysisNotes,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    plan = _get_plan_or_404(plan_id, db)
    _check_plan_access(plan, current_user, db)

    service = get_sbp_service(db)
    plan = service.save_cross_analysis_notes(plan_id, data.notes)
    return {"success": True}


# ---------------------------------------------------------------------------
# Step 3: Section Drafting
# ---------------------------------------------------------------------------

@router.post("/{plan_id}/initialise-sections")
async def initialise_sections(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    plan = _get_plan_or_404(plan_id, db)
    _check_plan_access(plan, current_user, db)

    service = get_sbp_service(db)
    plan = service.initialise_sections(plan_id)
    return {"success": True, "sections": plan.sections}


@router.post("/{plan_id}/draft-section/{section_key}")
async def draft_section(
    plan_id: UUID,
    section_key: str,
    data: Optional[SBPDraftSectionRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    plan = _get_plan_or_404(plan_id, db)
    _check_plan_access(plan, current_user, db)

    if not plan.sections:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Sections not initialised. Call initialise-sections first.")

    try:
        from app.services.sbp_conversation_engine import get_sbp_conversation_engine
        engine = get_sbp_conversation_engine(db)
        result = await engine.draft_section(
            plan_id=plan_id,
            section_key=section_key,
            custom_instructions=data.custom_instructions if data else None,
        )
        return {"success": True, "section": result}
    except Exception as e:
        logger.error(f"Section drafting failed for {section_key}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Section drafting failed: {str(e)}")


@router.post("/{plan_id}/revise-section/{section_key}")
async def revise_section(
    plan_id: UUID,
    section_key: str,
    data: SBPRevisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    plan = _get_plan_or_404(plan_id, db)
    _check_plan_access(plan, current_user, db)

    try:
        from app.services.sbp_conversation_engine import get_sbp_conversation_engine
        engine = get_sbp_conversation_engine(db)
        result = await engine.revise_section(
            plan_id=plan_id,
            section_key=section_key,
            revision_notes=data.revision_notes,
        )
        return {"success": True, "section": result}
    except Exception as e:
        logger.error(f"Section revision failed for {section_key}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Section revision failed: {str(e)}")


@router.patch("/{plan_id}/section/{section_key}")
async def edit_section(
    plan_id: UUID,
    section_key: str,
    data: SBPSectionEdit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    plan = _get_plan_or_404(plan_id, db)
    _check_plan_access(plan, current_user, db)

    service = get_sbp_service(db)
    updates = {}
    if data.content is not None:
        updates["content"] = data.content
    if data.strategic_implications is not None:
        updates["strategic_implications"] = data.strategic_implications

    plan = service.update_section(plan_id, section_key, updates)
    # Find updated section
    section = next((s for s in plan.sections if s["key"] == section_key), None)
    return {"success": True, "section": section}


@router.post("/{plan_id}/approve-section/{section_key}")
async def approve_section(
    plan_id: UUID,
    section_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    plan = _get_plan_or_404(plan_id, db)
    _check_plan_access(plan, current_user, db)

    service = get_sbp_service(db)
    plan = service.approve_section(plan_id, section_key)
    return {"success": True, "sections": plan.sections}


@router.post("/{plan_id}/surface-themes")
async def surface_themes(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    plan = _get_plan_or_404(plan_id, db)
    _check_plan_access(plan, current_user, db)

    try:
        from app.services.sbp_conversation_engine import get_sbp_conversation_engine
        engine = get_sbp_conversation_engine(db)
        result = await engine.surface_emerging_themes(plan_id=plan_id)
        return {"success": True, "emerging_themes": result}
    except Exception as e:
        logger.error(f"Theme surfacing failed for plan {plan_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Theme surfacing failed: {str(e)}")


# ---------------------------------------------------------------------------
# Step 4: Plan Assembly
# ---------------------------------------------------------------------------

@router.post("/{plan_id}/assemble")
async def assemble_plan(
    plan_id: UUID,
    data: Optional[SBPAssembleRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    plan = _get_plan_or_404(plan_id, db)
    _check_plan_access(plan, current_user, db)

    service = get_sbp_service(db)
    plan = service.assemble_final_plan(
        plan_id,
        section_order=data.section_order if data else None,
    )
    return {"success": True, "final_plan": plan.final_plan}


# ---------------------------------------------------------------------------
# Step 5: Export
# ---------------------------------------------------------------------------

@router.get("/{plan_id}/export/docx")
async def export_docx(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = _get_plan_or_404(plan_id, db)
    _check_plan_access(plan, current_user, db)

    if not plan.final_plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Plan must be assembled before export")

    try:
        from app.services.sbp_report_export import get_sbp_report_exporter
        exporter = get_sbp_report_exporter()
        file_path = exporter.generate_docx(plan)

        client_name = (plan.client_name or "Client").replace(" ", "_")
        from datetime import datetime
        year = datetime.now().year
        filename = f"Strategic_Business_Plan_{client_name}_{year}.docx"

        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except Exception as e:
        logger.error(f"Export failed for plan {plan_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Export failed: {str(e)}")


@router.get("/{plan_id}/export/employee-docx")
async def export_employee_docx(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = _get_plan_or_404(plan_id, db)
    _check_plan_access(plan, current_user, db)

    if not plan.final_plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Plan must be assembled before export")

    try:
        from app.services.sbp_report_export import get_sbp_employee_exporter
        exporter = get_sbp_employee_exporter()
        file_path = exporter.generate_employee_docx(plan)

        client_name = (plan.client_name or "Client").replace(" ", "_")
        from datetime import datetime
        year = datetime.now().year
        filename = f"Employee_Strategy_Document_{client_name}_{year}.docx"

        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except Exception as e:
        logger.error(f"Employee export failed for plan {plan_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Employee export failed: {str(e)}")


# ---------------------------------------------------------------------------
# Step tracking
# ---------------------------------------------------------------------------

@router.patch("/{plan_id}/step-progress")
async def update_step_progress(
    plan_id: UUID,
    data: SBPStepProgressUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    plan = _get_plan_or_404(plan_id, db)
    _check_plan_access(plan, current_user, db)

    service = get_sbp_service(db)
    plan = service.update_step_progress(plan_id, data.current_step, data.max_step_reached)
    return {
        "success": True,
        "current_step": plan.current_step,
        "max_step_reached": plan.max_step_reached,
    }


# ---------------------------------------------------------------------------
# Step 6: Presentation (placeholder — will be implemented with engine)
# ---------------------------------------------------------------------------

@router.post("/{plan_id}/presentation/generate")
async def generate_presentation(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    plan = _get_plan_or_404(plan_id, db)
    _check_plan_access(plan, current_user, db)

    if not plan.final_plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Plan must be assembled before generating a presentation")

    try:
        from app.services.sbp_presentation_service import get_sbp_presentation_service
        pres_service = get_sbp_presentation_service(db)
        slides = await pres_service.generate_slides(plan_id)
        return {"success": True, "slides": slides}
    except Exception as e:
        logger.error(f"Presentation generation failed for plan {plan_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Presentation generation failed: {str(e)}")


@router.get("/{plan_id}/presentation/export")
async def export_presentation(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = _get_plan_or_404(plan_id, db)
    _check_plan_access(plan, current_user, db)

    if not plan.presentation_slides:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="No presentation slides generated")

    try:
        from app.services.sbp_pptx_export import get_sbp_pptx_exporter
        exporter = get_sbp_pptx_exporter()
        file_path = exporter.generate_pptx(plan)

        client_name = (plan.client_name or "Client").replace(" ", "_")
        filename = f"Strategic_Business_Plan_Presentation_{client_name}.pptx"

        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
    except Exception as e:
        logger.error(f"Presentation export failed for plan {plan_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Presentation export failed: {str(e)}")
