"""
Roles & Responsibilities Matrix API.

Backs the HR Planning Tool workflow:
- Step 1: Inputs (upload PDs/notes, key staff, confirmed roles)
- Step 2: Extract responsibilities from the inputs
- Step 3: Build the matrix rows
- Step 4: Review, edit and export to Excel
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
from app.services.roles_matrix_service import get_roles_matrix_service
from app.services.roles_matrix_engine import get_roles_matrix_engine
from app.services.roles_matrix_export import get_roles_matrix_exporter
from app.config import settings
from app.schemas.roles_matrix import (
    RolesMatrixInputsRequest,
    RolesMatrixExtractRequest,
    RolesMatrixGenerateRequest,
    RolesMatrixUpdateRequest,
    RolesMatrixStepProgressRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/roles-matrix", tags=["roles-matrix"])

# The tool is advisor-facing; clients do not build roles matrices.
ADVISOR_ROLES = [
    UserRole.ADVISOR,
    UserRole.ADMIN,
    UserRole.SUPER_ADMIN,
    UserRole.FIRM_ADMIN,
    UserRole.FIRM_ADVISOR,
]

MAX_UPLOAD_FILES = 20


def _uploads_base() -> Path:
    """Base directory for persisting uploaded position descriptions and notes."""
    base = Path(settings.UPLOAD_DIR)
    if not base.is_absolute():
        base = Path(__file__).resolve().parent.parent.parent / base
    return base / "roles-matrix"


def _sanitize_filename(filename: str) -> str:
    """Return a safe filename (no path separators or traversal)."""
    name = os.path.basename(filename or "")
    safe = "".join(c for c in name if c.isalnum() or c in "._- ").strip()
    if not safe:
        ext = os.path.splitext(name)[1]
        safe = f"file{ext}" if ext else "file"
    return safe[:200]


def _get_matrix_or_404(matrix_id: UUID, db: Session):
    """Load a matrix or raise 404."""
    service = get_roles_matrix_service(db)
    matrix = service.get_matrix(matrix_id)
    if not matrix:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Roles matrix not found",
        )
    return matrix


def _check_matrix_access(matrix, current_user: User, db: Session) -> None:
    """
    Authorise access to a roles matrix.

    Allowed for the creator, or for any user with access to the linked
    engagement. Raises 403 otherwise.
    """
    if matrix.created_by_user_id == current_user.id:
        return
    engagement = None
    if matrix.engagement_id:
        engagement = db.query(Engagement).filter(
            Engagement.id == matrix.engagement_id,
            Engagement.is_deleted == False,
        ).first()
    if not engagement or not check_engagement_access(engagement, current_user, db=db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this roles matrix",
        )


# ==================== Listing & creation ====================

@router.get("/", status_code=status.HTTP_200_OK)
async def list_roles_matrices(
    engagement_id: Optional[UUID] = Query(None, description="Filter matrices by engagement ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADVISOR_ROLES)),
) -> Dict[str, Any]:
    """List the current user's roles matrices, optionally filtered by engagement."""
    service = get_roles_matrix_service(db)
    if engagement_id:
        matrices = service.get_matrices_by_engagement(engagement_id, current_user.id)
    else:
        matrices = service.get_matrices_for_user(current_user.id)
    return {"matrices": [m.to_dict() for m in matrices], "count": len(matrices)}


@router.post("/create-project", status_code=status.HTTP_201_CREATED)
async def create_roles_matrix(
    engagement_id: Optional[UUID] = Query(None, description="Optional engagement to link the matrix to"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADVISOR_ROLES)),
) -> Dict[str, Any]:
    """Create a new roles matrix."""
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

    service = get_roles_matrix_service(db)
    matrix = service.create_matrix(user_id=current_user.id, engagement_id=engagement_id)
    return {
        "success": True,
        "matrix_id": str(matrix.id),
        "engagement_id": str(matrix.engagement_id) if matrix.engagement_id else None,
        "status": matrix.status,
    }


@router.get("/{matrix_id}", status_code=status.HTTP_200_OK)
async def get_roles_matrix(
    matrix_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADVISOR_ROLES)),
) -> Dict[str, Any]:
    """Get a roles matrix with all step data."""
    matrix = _get_matrix_or_404(matrix_id, db)
    _check_matrix_access(matrix, current_user, db)
    return {"success": True, "matrix": matrix.to_dict()}


@router.delete("/{matrix_id}", status_code=status.HTTP_200_OK)
async def delete_roles_matrix(
    matrix_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADVISOR_ROLES)),
) -> Dict[str, Any]:
    """Soft delete a roles matrix."""
    matrix = _get_matrix_or_404(matrix_id, db)
    _check_matrix_access(matrix, current_user, db)

    service = get_roles_matrix_service(db)
    service.delete_matrix(matrix_id)
    return {"success": True, "message": "Roles matrix deleted"}


# ==================== Step 1: Inputs ====================

@router.post("/{matrix_id}/upload", status_code=status.HTTP_200_OK)
async def upload_documents(
    matrix_id: UUID,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADVISOR_ROLES)),
) -> Dict[str, Any]:
    """
    Upload position descriptions, responsibilities lists, org charts or notes.

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

    matrix = _get_matrix_or_404(matrix_id, db)
    _check_matrix_access(matrix, current_user, db)

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
                matrix_dir = _uploads_base() / str(matrix_id)
                matrix_dir.mkdir(parents=True, exist_ok=True)
                (matrix_dir / safe_name).write_bytes(file_content)
                stored_file_mapping[filename] = f"{matrix_id}/{safe_name}"
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
        service = get_roles_matrix_service(db)
        matrix = service.update_files(
            matrix_id=matrix_id,
            file_ids=file_ids,
            file_mappings=file_mapping,
            stored_files=stored_file_mapping,
        )

    return {
        "success": bool(file_ids),
        "message": f"Processed {len(files)} file(s)",
        "files": results,
        "matrix": matrix.to_dict() if matrix else None,
    }


@router.patch("/{matrix_id}/inputs", status_code=status.HTTP_200_OK)
async def save_inputs(
    matrix_id: UUID,
    inputs: RolesMatrixInputsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADVISOR_ROLES)),
) -> Dict[str, Any]:
    """Save the key staff list, the confirmed roles and any pasted notes."""
    matrix = _get_matrix_or_404(matrix_id, db)
    _check_matrix_access(matrix, current_user, db)

    service = get_roles_matrix_service(db)
    matrix = service.update_inputs(matrix_id, inputs)
    return {"success": True, "matrix": matrix.to_dict()}


# ==================== Step 2: Extract ====================

@router.post("/{matrix_id}/extract", status_code=status.HTTP_200_OK)
async def extract_responsibilities(
    matrix_id: UUID,
    request: Optional[RolesMatrixExtractRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADVISOR_ROLES)),
) -> Dict[str, Any]:
    """Extract responsibilities per person from the uploaded files and notes."""
    matrix = _get_matrix_or_404(matrix_id, db)
    _check_matrix_access(matrix, current_user, db)

    if not matrix.file_ids and not matrix.pasted_notes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload at least one document or paste some notes before extracting",
        )
    if not matrix.staff:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add the key staff names and roles before extracting",
        )

    engine = get_roles_matrix_engine()
    try:
        result = await engine.extract_responsibilities(
            matrix, custom_instructions=request.custom_instructions if request else None
        )
    except FileNotFoundError as e:
        logger.error(f"Roles matrix prompt missing for matrix {matrix_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Prompt template not found. Please contact support.",
        )
    except Exception as e:
        logger.error(f"Extraction failed for roles matrix {matrix_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Extraction failed. Please try again or contact support.",
        )

    service = get_roles_matrix_service(db)
    matrix = service.update_extracted_responsibilities(
        matrix_id=matrix_id,
        extracted=result["extracted"],
        tokens_used=result.get("tokens_used"),
        model=result.get("model"),
    )

    return {
        "success": True,
        "extracted_responsibilities": matrix.extracted_responsibilities,
        "matrix": matrix.to_dict(),
    }


# ==================== Step 3: Build the matrix ====================

@router.post("/{matrix_id}/matrix/generate", status_code=status.HTTP_200_OK)
async def generate_matrix(
    matrix_id: UUID,
    request: Optional[RolesMatrixGenerateRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADVISOR_ROLES)),
) -> Dict[str, Any]:
    """Build the matrix rows from the extracted responsibilities."""
    matrix = _get_matrix_or_404(matrix_id, db)
    _check_matrix_access(matrix, current_user, db)

    if not matrix.extracted_responsibilities:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Run extraction before building the matrix",
        )

    engine = get_roles_matrix_engine()
    try:
        result = await engine.build_matrix(
            matrix, custom_instructions=request.custom_instructions if request else None
        )
    except ValueError as e:
        logger.warning(f"Matrix build rejected for roles matrix {matrix_id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except FileNotFoundError as e:
        logger.error(f"Roles matrix prompt missing for matrix {matrix_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Prompt template not found. Please contact support.",
        )
    except Exception as e:
        logger.error(f"Matrix generation failed for roles matrix {matrix_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Matrix generation failed. Please try again or contact support.",
        )

    service = get_roles_matrix_service(db)
    matrix = service.update_matrix_rows(
        matrix_id=matrix_id,
        rows=result["matrix_rows"],
        edited=False,
        tokens_used=result.get("tokens_used"),
        model=result.get("model"),
    )

    return {
        "success": True,
        "matrix_rows": matrix.matrix_rows,
        "matrix": matrix.to_dict(),
    }


@router.patch("/{matrix_id}/matrix", status_code=status.HTTP_200_OK)
async def save_matrix(
    matrix_id: UUID,
    request: RolesMatrixUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADVISOR_ROLES)),
) -> Dict[str, Any]:
    """Save advisor edits to the matrix rows."""
    matrix = _get_matrix_or_404(matrix_id, db)
    _check_matrix_access(matrix, current_user, db)

    service = get_roles_matrix_service(db)
    matrix = service.update_matrix_rows(
        matrix_id=matrix_id,
        rows=[row.model_dump() for row in request.matrix_rows],
        edited=True,
    )
    return {"success": True, "matrix": matrix.to_dict()}


# ==================== Step progress ====================

@router.patch("/{matrix_id}/step-progress", status_code=status.HTTP_200_OK)
async def update_step_progress(
    matrix_id: UUID,
    request: RolesMatrixStepProgressRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADVISOR_ROLES)),
) -> Dict[str, Any]:
    """Persist which step the advisor is on."""
    matrix = _get_matrix_or_404(matrix_id, db)
    _check_matrix_access(matrix, current_user, db)

    service = get_roles_matrix_service(db)
    matrix = service.update_step_progress(
        matrix_id=matrix_id,
        current_step=request.current_step,
        max_step_reached=request.max_step_reached or request.current_step,
    )
    return {"success": True, "matrix": matrix.to_dict()}


# ==================== Export ====================

@router.post("/{matrix_id}/export/excel")
async def export_matrix_to_excel(
    matrix_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ADVISOR_ROLES)),
):
    """Export the matrix into a copy of the HR Planning Tool workbook."""
    matrix = _get_matrix_or_404(matrix_id, db)
    _check_matrix_access(matrix, current_user, db)

    if not matrix.matrix_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Build the matrix before exporting",
        )

    try:
        exporter = get_roles_matrix_exporter()
        stream = exporter.generate_workbook_bytes(matrix.matrix_rows)
    except FileNotFoundError as e:
        logger.error(f"Roles matrix template missing for matrix {matrix_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Template file not found. Please contact support.",
        )
    except Exception as e:
        logger.error(f"Excel export failed for roles matrix {matrix_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Excel export failed. Please try again or contact support.",
        )

    service = get_roles_matrix_service(db)
    service.mark_completed(matrix_id)

    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="Roles_and_Responsibilities_Matrix.xlsx"'},
    )
