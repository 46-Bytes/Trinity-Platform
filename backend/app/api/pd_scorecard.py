"""
PD & Role Scorecard API.

Backs the Position Description generator:
- Step 1: Inputs (upload the roles matrix, or reuse a completed one)
- Step 2: Confirm the roles found in the matrix
- Step 3: Per role — generate, edit, approve and export the Position Description
- Step 4: Per role — generate, edit, approve and export the Half-Yearly Scorecard
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from uuid import UUID
from pathlib import Path
import tempfile
import os
import logging

from app.database import get_db
from app.utils.auth import require_role
from app.models.user import User, UserRole
from app.models.engagement import Engagement
from app.services.claude_service import ClaudeService
from app.services.role_check import check_engagement_access
from app.services.pd_scorecard_service import get_pd_scorecard_service, rows_for_role
from app.services.pd_scorecard_engine import get_pd_scorecard_engine
from app.services.pd_export import get_position_description_exporter
from app.services.scorecard_export import get_scorecard_exporter
from app.config import settings
from app.schemas.pd_scorecard import (
    PDScorecardInputsRequest,
    PDScorecardExtractRequest,
    PDScorecardRolesUpdateRequest,
    PDGenerateRequest,
    PDUpdateRequest,
    ScorecardGenerateRequest,
    ScorecardUpdateRequest,
    PDScorecardStepProgressRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pd-scorecard", tags=["pd-scorecard"])

# ==================== Permissions ====================
#
# Three lists rather than one, so client access can be enabled per capability
# without touching the data model. The module specification has the advisor
# produce the first two position descriptions and the client generate the
# remainder, which maps to READ_ROLES and ROLE_WORK_ROLES only.
#
# To enable client access later, add UserRole.CLIENT to READ_ROLES and
# ROLE_WORK_ROLES. BUILD_SETUP_ROLES stays advisor-only: clients work inside a
# build the advisor has already set up, they do not create or configure one.
# Record-level scoping already admits clients via check_engagement_access.

_ADVISOR_ROLES = [
    UserRole.ADVISOR,
    UserRole.ADMIN,
    UserRole.SUPER_ADMIN,
    UserRole.FIRM_ADMIN,
    UserRole.FIRM_ADVISOR,
]

# Creating a build, uploading the matrix, and confirming the role list.
BUILD_SETUP_ROLES = list(_ADVISOR_ROLES)

# Generating, editing, approving and exporting a single role's PD and scorecard.
ROLE_WORK_ROLES = list(_ADVISOR_ROLES)

# Reading a build and its roles.
READ_ROLES = list(_ADVISOR_ROLES)

MAX_UPLOAD_FILES = 20


def _uploads_base() -> Path:
    """Base directory for persisting the uploaded matrix and reference PDs."""
    base = Path(settings.UPLOAD_DIR)
    if not base.is_absolute():
        base = Path(__file__).resolve().parent.parent.parent / base
    return base / "pd-scorecard"


def _sanitize_filename(filename: str) -> str:
    """Return a safe filename (no path separators or traversal)."""
    name = os.path.basename(filename or "")
    safe = "".join(c for c in name if c.isalnum() or c in "._- ").strip()
    if not safe:
        ext = os.path.splitext(name)[1]
        safe = f"file{ext}" if ext else "file"
    return safe[:200]


def _download_name(role_title: str, suffix: str, extension: str) -> str:
    """Build a safe download filename from the role title."""
    safe = "".join(c if c.isalnum() or c in " -_" else " " for c in (role_title or "Role"))
    safe = " ".join(safe.split()) or "Role"
    return f"{safe} - {suffix}.{extension}"


def _get_build_or_404(build_id: UUID, db: Session):
    """Load a build or raise 404."""
    service = get_pd_scorecard_service(db)
    build = service.get_build(build_id)
    if not build:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PD & scorecard build not found",
        )
    return build


def _check_build_access(build, current_user: User, db: Session) -> None:
    """
    Authorise access to a build.

    Allowed for the creator, or for any user with access to the linked
    engagement. Raises 403 otherwise. check_engagement_access already scopes
    clients to their own engagement, so this needs no change when client access
    is enabled.
    """
    if build.created_by_user_id == current_user.id:
        return
    engagement = None
    if build.engagement_id:
        engagement = db.query(Engagement).filter(
            Engagement.id == build.engagement_id,
            Engagement.is_deleted == False,
        ).first()
    if not engagement or not check_engagement_access(engagement, current_user, db=db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this PD & scorecard build",
        )


def _get_role_or_404(build_id: UUID, role_id: UUID, db: Session):
    """Load a role and confirm it belongs to the given build."""
    service = get_pd_scorecard_service(db)
    role = service.get_role(role_id)
    if not role or role.pd_scorecard_id != build_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found in this build",
        )
    return role


# ==================== Listing & creation ====================

@router.get("/", status_code=status.HTTP_200_OK)
async def list_builds(
    engagement_id: Optional[UUID] = Query(None, description="Filter builds by engagement ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(READ_ROLES)),
) -> Dict[str, Any]:
    """List the current user's PD & scorecard builds, optionally filtered by engagement."""
    service = get_pd_scorecard_service(db)
    if engagement_id:
        builds = service.get_builds_by_engagement(engagement_id, current_user.id)
    else:
        builds = service.get_builds_for_user(current_user.id)
    return {
        "builds": [b.to_dict(include_roles=False) for b in builds],
        "count": len(builds),
    }


@router.post("/create-project", status_code=status.HTTP_201_CREATED)
async def create_build(
    engagement_id: Optional[UUID] = Query(None, description="Optional engagement to link the build to"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(BUILD_SETUP_ROLES)),
) -> Dict[str, Any]:
    """Create a new PD & scorecard build."""
    if engagement_id:
        engagement = db.query(Engagement).filter(
            Engagement.id == engagement_id,
            Engagement.is_deleted == False,
        ).first()
        if not engagement:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engagement not found")
        if not check_engagement_access(engagement, current_user, db=db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this engagement",
            )

    service = get_pd_scorecard_service(db)
    build = service.create_build(user_id=current_user.id, engagement_id=engagement_id)
    return {
        "success": True,
        "build_id": str(build.id),
        "engagement_id": str(build.engagement_id) if build.engagement_id else None,
        "status": build.status,
    }


@router.get("/{build_id}", status_code=status.HTTP_200_OK)
async def get_build(
    build_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(READ_ROLES)),
) -> Dict[str, Any]:
    """Get a build with its roles and all step data."""
    build = _get_build_or_404(build_id, db)
    _check_build_access(build, current_user, db)
    return {"success": True, "build": build.to_dict()}


@router.delete("/{build_id}", status_code=status.HTTP_200_OK)
async def delete_build(
    build_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(BUILD_SETUP_ROLES)),
) -> Dict[str, Any]:
    """Soft delete a build."""
    build = _get_build_or_404(build_id, db)
    _check_build_access(build, current_user, db)

    service = get_pd_scorecard_service(db)
    service.delete_build(build_id)
    return {"success": True, "message": "PD & scorecard build deleted"}


# ==================== Step 1: Inputs ====================

@router.post("/{build_id}/upload", status_code=status.HTTP_200_OK)
async def upload_documents(
    build_id: UUID,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(BUILD_SETUP_ROLES)),
) -> Dict[str, Any]:
    """
    Upload the completed Roles & Responsibilities matrix and any reference PDs.

    Each file is sent to the Claude Files API for analysis and persisted to disk.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided",
        )
    if len(files) > MAX_UPLOAD_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many files. Maximum {MAX_UPLOAD_FILES} files per upload.",
        )

    build = _get_build_or_404(build_id, db)
    _check_build_access(build, current_user, db)

    claude_service = ClaudeService()

    results: List[Dict[str, Any]] = []
    file_mapping: Dict[str, str] = {}
    file_ids: List[str] = []
    stored_file_mapping: Dict[str, str] = {}

    for upload in files:
        filename = upload.filename or "file"
        temp_file_path = None
        try:
            file_content = await upload.read()
        except Exception as e:
            logger.error(f"Error reading file {filename}: {str(e)}", exc_info=True)
            results.append({"filename": filename, "file_id": None, "status": "error", "error": str(e)})
            continue

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name

            upload_result = await claude_service.upload_file(
                file_path=temp_file_path,
                purpose="assistants",
            )

            if not upload_result or not upload_result.get("id"):
                results.append({
                    "filename": filename,
                    "file_id": None,
                    "status": "error",
                    "error": "Upload to AI provider failed",
                })
                continue

            file_id = upload_result["id"]
            safe_name = _sanitize_filename(filename)

            # Persist a copy so the advisor can re-download what was analysed
            try:
                build_dir = _uploads_base() / str(build_id)
                build_dir.mkdir(parents=True, exist_ok=True)
                (build_dir / safe_name).write_bytes(file_content)
                stored_file_mapping[filename] = f"{build_id}/{safe_name}"
            except Exception as store_err:
                logger.warning(f"Failed to persist file {filename} to disk: {store_err}")

            file_ids.append(file_id)
            file_mapping[filename] = file_id
            results.append({
                "filename": filename,
                "file_id": file_id,
                "status": "success",
                "size": len(file_content),
            })

        except Exception as e:
            logger.error(f"Error uploading file {filename}: {str(e)}", exc_info=True)
            results.append({"filename": filename, "file_id": None, "status": "error", "error": str(e)})
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass

    if file_ids:
        service = get_pd_scorecard_service(db)
        build = service.update_files(
            build_id=build_id,
            file_ids=file_ids,
            file_mappings=file_mapping,
            stored_files=stored_file_mapping,
        )

    return {
        "success": bool(file_ids),
        "message": f"Processed {len(files)} file(s)",
        "files": results,
        "build": build.to_dict() if build else None,
    }


@router.patch("/{build_id}/inputs", status_code=status.HTTP_200_OK)
async def save_inputs(
    build_id: UUID,
    inputs: PDScorecardInputsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(BUILD_SETUP_ROLES)),
) -> Dict[str, Any]:
    """Save the client name, FY range, reference PD flags and any pasted notes."""
    build = _get_build_or_404(build_id, db)
    _check_build_access(build, current_user, db)

    service = get_pd_scorecard_service(db)
    build = service.update_inputs(build_id, inputs)
    return {"success": True, "build": build.to_dict()}


# ==================== Step 2: Roles ====================

@router.post("/{build_id}/extract", status_code=status.HTTP_200_OK)
async def extract_roles(
    build_id: UUID,
    request: Optional[PDScorecardExtractRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(BUILD_SETUP_ROLES)),
) -> Dict[str, Any]:
    """Parse the uploaded matrix into rows and the roles it contains."""
    build = _get_build_or_404(build_id, db)
    _check_build_access(build, current_user, db)

    if not build.file_ids and not build.pasted_notes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload the roles matrix or paste its contents before extracting",
        )

    engine = get_pd_scorecard_engine()
    try:
        result = await engine.extract_roles(
            build, custom_instructions=request.custom_instructions if request else None
        )
    except FileNotFoundError as e:
        logger.error(f"PD scorecard prompt missing for build {build_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Prompt template not found. Please contact support.",
        )
    except Exception as e:
        logger.error(f"Role extraction failed for build {build_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Extraction failed. Please try again or contact support.",
        )

    service = get_pd_scorecard_service(db)
    build = service.update_matrix_rows(
        build_id=build_id,
        rows=result["matrix_rows"],
        tokens_used=result.get("tokens_used"),
        model=result.get("model"),
    )

    return {
        "success": True,
        "matrix_rows": build.matrix_rows,
        "suggested_roles": result.get("roles", []),
        "build": build.to_dict(),
    }


@router.patch("/{build_id}/roles", status_code=status.HTTP_200_OK)
async def save_roles(
    build_id: UUID,
    request: PDScorecardRolesUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(BUILD_SETUP_ROLES)),
) -> Dict[str, Any]:
    """Save the confirmed role list, in display order."""
    build = _get_build_or_404(build_id, db)
    _check_build_access(build, current_user, db)

    service = get_pd_scorecard_service(db)
    build = service.replace_roles(build_id, request.roles)

    # Cache each role's own matrix rows so generation and the UI agree on scope.
    for role in service.get_roles(build_id):
        service.attach_source_responsibilities(
            role.id,
            rows_for_role(build.matrix_rows or [], role.role_title, role.person_name),
        )

    db.refresh(build)
    return {"success": True, "build": build.to_dict()}


@router.get("/{build_id}/roles", status_code=status.HTTP_200_OK)
async def list_roles(
    build_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(READ_ROLES)),
) -> Dict[str, Any]:
    """List a build's roles in display order."""
    build = _get_build_or_404(build_id, db)
    _check_build_access(build, current_user, db)

    service = get_pd_scorecard_service(db)
    roles = service.get_roles(build_id)
    return {"success": True, "roles": [r.to_dict() for r in roles], "count": len(roles)}


# ==================== Step 3: Position Description ====================

@router.post("/{build_id}/roles/{role_id}/pd/generate", status_code=status.HTTP_200_OK)
async def generate_pd(
    build_id: UUID,
    role_id: UUID,
    request: Optional[PDGenerateRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ROLE_WORK_ROLES)),
) -> Dict[str, Any]:
    """Generate the Position Description draft for one role."""
    build = _get_build_or_404(build_id, db)
    _check_build_access(build, current_user, db)
    role = _get_role_or_404(build_id, role_id, db)

    engine = get_pd_scorecard_engine()
    try:
        result = await engine.generate_pd(
            build, role, custom_instructions=request.custom_instructions if request else None
        )
    except ValueError as e:
        logger.warning(f"PD generation rejected for role {role_id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except FileNotFoundError as e:
        logger.error(f"PD scorecard prompt missing for build {build_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Prompt template not found. Please contact support.",
        )
    except Exception as e:
        logger.error(f"PD generation failed for role {role_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Position description generation failed. Please try again or contact support.",
        )

    service = get_pd_scorecard_service(db)
    role = service.update_pd_content(
        role_id=role_id,
        pd_content=result["pd_content"],
        tokens_used=result.get("tokens_used"),
        model=result.get("model"),
    )

    return {"success": True, "role": role.to_dict()}


@router.patch("/{build_id}/roles/{role_id}/pd", status_code=status.HTTP_200_OK)
async def save_pd(
    build_id: UUID,
    role_id: UUID,
    request: PDUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ROLE_WORK_ROLES)),
) -> Dict[str, Any]:
    """Save edits to the Position Description draft."""
    build = _get_build_or_404(build_id, db)
    _check_build_access(build, current_user, db)
    _get_role_or_404(build_id, role_id, db)

    service = get_pd_scorecard_service(db)
    role = service.update_pd_content(
        role_id=role_id,
        pd_content=request.pd_content.model_dump(),
    )
    return {"success": True, "role": role.to_dict()}


@router.post("/{build_id}/roles/{role_id}/pd/approve", status_code=status.HTTP_200_OK)
async def approve_pd(
    build_id: UUID,
    role_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ROLE_WORK_ROLES)),
) -> Dict[str, Any]:
    """Approve the Position Description, unlocking scorecard generation."""
    build = _get_build_or_404(build_id, db)
    _check_build_access(build, current_user, db)
    _get_role_or_404(build_id, role_id, db)

    service = get_pd_scorecard_service(db)
    try:
        role = service.approve_pd(role_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"success": True, "role": role.to_dict()}


@router.post("/{build_id}/roles/{role_id}/pd/export")
async def export_pd(
    build_id: UUID,
    role_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ROLE_WORK_ROLES)),
):
    """Export the approved Position Description as a Word document."""
    build = _get_build_or_404(build_id, db)
    _check_build_access(build, current_user, db)
    role = _get_role_or_404(build_id, role_id, db)

    if not role.pd_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Generate the position description before exporting",
        )

    try:
        exporter = get_position_description_exporter()
        stream = exporter.generate_document_bytes(
            role_title=role.role_title,
            pd_content=role.pd_content,
            client_name=build.client_name,
            fy_range=build.fy_range,
        )
    except Exception as e:
        logger.error(f"PD export failed for role {role_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Word export failed. Please try again or contact support.",
        )

    filename = _download_name(role.role_title, "Position Description", "docx")
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ==================== Step 4: Scorecard ====================

@router.post("/{build_id}/roles/{role_id}/scorecard/generate", status_code=status.HTTP_200_OK)
async def generate_scorecard(
    build_id: UUID,
    role_id: UUID,
    request: Optional[ScorecardGenerateRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ROLE_WORK_ROLES)),
) -> Dict[str, Any]:
    """Generate the Half-Yearly Scorecard draft for one role."""
    build = _get_build_or_404(build_id, db)
    _check_build_access(build, current_user, db)
    role = _get_role_or_404(build_id, role_id, db)

    if role.pd_status != 'approved':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approve the position description before creating the scorecard",
        )

    engine = get_pd_scorecard_engine()
    try:
        result = await engine.generate_scorecard(
            build, role, custom_instructions=request.custom_instructions if request else None
        )
    except ValueError as e:
        logger.warning(f"Scorecard generation rejected for role {role_id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except FileNotFoundError as e:
        logger.error(f"PD scorecard prompt missing for build {build_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Prompt template not found. Please contact support.",
        )
    except Exception as e:
        logger.error(f"Scorecard generation failed for role {role_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Scorecard generation failed. Please try again or contact support.",
        )

    service = get_pd_scorecard_service(db)
    role = service.update_scorecard_content(
        role_id=role_id,
        scorecard_content=result["scorecard_content"],
        tokens_used=result.get("tokens_used"),
        model=result.get("model"),
    )

    return {"success": True, "role": role.to_dict()}


@router.patch("/{build_id}/roles/{role_id}/scorecard", status_code=status.HTTP_200_OK)
async def save_scorecard(
    build_id: UUID,
    role_id: UUID,
    request: ScorecardUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ROLE_WORK_ROLES)),
) -> Dict[str, Any]:
    """Save edits to the scorecard draft."""
    build = _get_build_or_404(build_id, db)
    _check_build_access(build, current_user, db)
    _get_role_or_404(build_id, role_id, db)

    service = get_pd_scorecard_service(db)
    role = service.update_scorecard_content(
        role_id=role_id,
        scorecard_content=request.scorecard_content.model_dump(),
    )
    return {"success": True, "role": role.to_dict()}


@router.post("/{build_id}/roles/{role_id}/scorecard/approve", status_code=status.HTTP_200_OK)
async def approve_scorecard(
    build_id: UUID,
    role_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ROLE_WORK_ROLES)),
) -> Dict[str, Any]:
    """Approve the scorecard, completing the role."""
    build = _get_build_or_404(build_id, db)
    _check_build_access(build, current_user, db)
    _get_role_or_404(build_id, role_id, db)

    service = get_pd_scorecard_service(db)
    try:
        role = service.approve_scorecard(role_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"success": True, "role": role.to_dict()}


@router.post("/{build_id}/roles/{role_id}/scorecard/export")
async def export_scorecard(
    build_id: UUID,
    role_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ROLE_WORK_ROLES)),
):
    """Export the approved scorecard as an Excel workbook."""
    build = _get_build_or_404(build_id, db)
    _check_build_access(build, current_user, db)
    role = _get_role_or_404(build_id, role_id, db)

    if not role.scorecard_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Generate the scorecard before exporting",
        )

    try:
        exporter = get_scorecard_exporter()
        stream = exporter.generate_workbook_bytes(
            role_title=role.role_title,
            scorecard_content=role.scorecard_content,
            fy_range=build.fy_range,
        )
    except Exception as e:
        logger.error(f"Scorecard export failed for role {role_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Excel export failed. Please try again or contact support.",
        )

    filename = _download_name(role.role_title, "Role Scorecard - Half-Yearly", "xlsx")
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ==================== Step progress ====================

@router.patch("/{build_id}/step-progress", status_code=status.HTTP_200_OK)
async def update_step_progress(
    build_id: UUID,
    request: PDScorecardStepProgressRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(READ_ROLES)),
) -> Dict[str, Any]:
    """Persist which step the user is on."""
    build = _get_build_or_404(build_id, db)
    _check_build_access(build, current_user, db)

    service = get_pd_scorecard_service(db)
    build = service.update_step_progress(
        build_id=build_id,
        current_step=request.current_step,
        max_step_reached=request.max_step_reached or request.current_step,
    )
    return {"success": True, "build": build.to_dict()}
