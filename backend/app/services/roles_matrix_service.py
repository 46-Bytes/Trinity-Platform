"""
Roles & Responsibilities Matrix Service
Handles business logic for roles matrix records.
"""
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timezone

from app.models.roles_matrix import RolesMatrix
from app.schemas.roles_matrix import RolesMatrixInputsRequest, MatrixRow
import logging

logger = logging.getLogger(__name__)

# Ordered keys of a matrix row, matching the Job Roles columns A-J
MATRIX_ROW_KEYS = [
    "name",
    "role_description",
    "time",
    "priorities",
    "retain",
    "gain",
    "lose",
    "action",
    "resp",
    "when",
]


class RolesMatrixService:
    """Service for managing Roles & Responsibilities matrices"""

    def __init__(self, db: Session):
        self.db = db

    # ==================== CRUD ====================

    def create_matrix(self, user_id: UUID, engagement_id: Optional[UUID] = None) -> RolesMatrix:
        """Create a new roles matrix record."""
        matrix = RolesMatrix(
            created_by_user_id=user_id,
            engagement_id=engagement_id,
            status='inputs',
            current_step=1,
            max_step_reached=1,
        )
        self.db.add(matrix)
        self.db.commit()
        self.db.refresh(matrix)
        logger.info(f"Created roles matrix {matrix.id} for user {user_id}")
        return matrix

    def get_matrix(self, matrix_id: UUID) -> Optional[RolesMatrix]:
        """Get a matrix by ID, excluding soft-deleted records."""
        return self.db.query(RolesMatrix).filter(
            RolesMatrix.id == matrix_id,
            RolesMatrix.is_deleted == False,
        ).first()

    def get_matrices_for_user(self, user_id: UUID) -> List[RolesMatrix]:
        """Get all matrices created by a user, newest first."""
        return self.db.query(RolesMatrix).filter(
            RolesMatrix.created_by_user_id == user_id,
            RolesMatrix.is_deleted == False,
        ).order_by(RolesMatrix.updated_at.desc()).all()

    def get_matrices_by_engagement(
        self, engagement_id: UUID, user_id: Optional[UUID] = None
    ) -> List[RolesMatrix]:
        """
        Get matrices for an engagement, newest first.
        When user_id is provided, only matrices created by that user are returned.
        """
        query = self.db.query(RolesMatrix).filter(
            RolesMatrix.engagement_id == engagement_id,
            RolesMatrix.is_deleted == False,
        )
        if user_id:
            query = query.filter(RolesMatrix.created_by_user_id == user_id)
        return query.order_by(RolesMatrix.updated_at.desc()).all()

    def delete_matrix(self, matrix_id: UUID) -> Optional[RolesMatrix]:
        """Soft delete a matrix."""
        matrix = self.get_matrix(matrix_id)
        if not matrix:
            return None
        matrix.is_deleted = True
        matrix.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        logger.info(f"Soft deleted roles matrix {matrix_id}")
        return matrix

    # ==================== Step 1: Inputs ====================

    def update_files(
        self,
        matrix_id: UUID,
        file_ids: List[str],
        file_mappings: Dict[str, str],
        stored_files: Optional[Dict[str, str]] = None,
    ) -> Optional[RolesMatrix]:
        """
        Attach uploaded files. Appends to whatever is already attached so an
        advisor can upload documents across several batches.
        """
        matrix = self.get_matrix(matrix_id)
        if not matrix:
            return None

        existing_ids = list(matrix.file_ids or [])
        for file_id in file_ids:
            if file_id not in existing_ids:
                existing_ids.append(file_id)
        matrix.file_ids = existing_ids
        matrix.file_mappings = {**(matrix.file_mappings or {}), **file_mappings}
        if stored_files is not None:
            matrix.stored_files = {**(matrix.stored_files or {}), **stored_files}
        matrix.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(matrix)
        logger.info(f"Attached {len(file_ids)} file(s) to roles matrix {matrix_id}")
        return matrix

    def update_inputs(
        self, matrix_id: UUID, inputs: RolesMatrixInputsRequest
    ) -> Optional[RolesMatrix]:
        """Save the advisor's staff list, included roles and pasted notes."""
        matrix = self.get_matrix(matrix_id)
        if not matrix:
            return None

        matrix.staff = [member.model_dump() for member in inputs.staff]
        matrix.included_roles = list(inputs.included_roles)
        matrix.pasted_notes = inputs.pasted_notes
        matrix.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(matrix)
        logger.info(f"Updated inputs for roles matrix {matrix_id}")
        return matrix

    # ==================== Step 2: Extraction ====================

    def update_extracted_responsibilities(
        self,
        matrix_id: UUID,
        extracted: Dict[str, Any],
        tokens_used: Optional[int] = None,
        model: Optional[str] = None,
    ) -> Optional[RolesMatrix]:
        """Save the extracted responsibilities and advance the status."""
        matrix = self.get_matrix(matrix_id)
        if not matrix:
            return None

        matrix.extracted_responsibilities = extracted
        matrix.status = 'extracted'
        self._record_ai_usage(matrix, tokens_used, model)
        matrix.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(matrix)
        logger.info(f"Saved extracted responsibilities for roles matrix {matrix_id}")
        return matrix

    # ==================== Step 3/4: Matrix ====================

    def update_matrix_rows(
        self,
        matrix_id: UUID,
        rows: List[Dict[str, Any]],
        edited: bool = False,
        tokens_used: Optional[int] = None,
        model: Optional[str] = None,
    ) -> Optional[RolesMatrix]:
        """
        Save matrix rows. `edited=True` marks them as advisor-edited rather than
        freshly generated.
        """
        matrix = self.get_matrix(matrix_id)
        if not matrix:
            return None

        matrix.matrix_rows = [normalise_row(row) for row in rows]
        matrix.matrix_edited = edited
        matrix.status = 'matrix_built'
        self._record_ai_usage(matrix, tokens_used, model)
        matrix.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(matrix)
        logger.info(f"Saved {len(rows)} matrix row(s) for roles matrix {matrix_id}")
        return matrix

    def mark_completed(self, matrix_id: UUID) -> Optional[RolesMatrix]:
        """Mark the matrix as completed once it has been exported."""
        matrix = self.get_matrix(matrix_id)
        if not matrix:
            return None

        matrix.status = 'completed'
        if not matrix.completed_at:
            matrix.completed_at = datetime.now(timezone.utc)
        matrix.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(matrix)
        return matrix

    # ==================== Step progress ====================

    def update_step_progress(
        self,
        matrix_id: UUID,
        current_step: Optional[int] = None,
        max_step_reached: Optional[int] = None,
    ) -> Optional[RolesMatrix]:
        """Persist the advisor's position in the workflow."""
        matrix = self.get_matrix(matrix_id)
        if not matrix:
            return None

        if current_step is not None:
            matrix.current_step = current_step
        if max_step_reached is not None:
            matrix.max_step_reached = max(max_step_reached, matrix.max_step_reached or 0)
        matrix.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(matrix)
        return matrix

    # ==================== Helpers ====================

    @staticmethod
    def _record_ai_usage(
        matrix: RolesMatrix, tokens_used: Optional[int], model: Optional[str]
    ) -> None:
        """Accumulate token usage and record the model that produced the output."""
        if tokens_used:
            matrix.ai_tokens_used = (matrix.ai_tokens_used or 0) + tokens_used
        if model:
            matrix.ai_model_used = model


def normalise_row(row: Any) -> Dict[str, Optional[str]]:
    """
    Coerce a row (dict or Pydantic model) into the canonical key set.
    Unknown keys are dropped and missing values stay blank — nothing is guessed.
    """
    if isinstance(row, MatrixRow):
        data = row.model_dump()
    elif hasattr(row, "model_dump"):
        data = row.model_dump()
    elif isinstance(row, dict):
        data = row
    else:
        data = {}

    normalised: Dict[str, Optional[str]] = {}
    for key in MATRIX_ROW_KEYS:
        value = data.get(key)
        if value is None:
            normalised[key] = None
            continue
        text = str(value).strip()
        normalised[key] = text or None
    return normalised


def get_roles_matrix_service(db: Session) -> RolesMatrixService:
    """Dependency function to get the roles matrix service"""
    return RolesMatrixService(db)
