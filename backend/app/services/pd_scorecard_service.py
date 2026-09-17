"""
PD & Role Scorecard Service
Handles business logic for PD & scorecard builds and their per-role records.
"""
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
import logging

from app.models.pd_scorecard import PDScorecard, PDScorecardRole
from app.schemas.pd_scorecard import (
    PDScorecardInputsRequest,
    RoleInput,
    PDContent,
    ScorecardContent,
)

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


class PDScorecardService:
    """Service for managing PD & Role Scorecard builds"""

    def __init__(self, db: Session):
        self.db = db

    # ==================== CRUD ====================

    def create_build(self, user_id: UUID, engagement_id: Optional[UUID] = None) -> PDScorecard:
        """Create a new PD & scorecard build."""
        build = PDScorecard(
            created_by_user_id=user_id,
            engagement_id=engagement_id,
            status='inputs',
            current_step=1,
            max_step_reached=1,
        )
        self.db.add(build)
        self.db.commit()
        self.db.refresh(build)
        logger.info(f"Created PD scorecard build {build.id} for user {user_id}")
        return build

    def get_build(self, build_id: UUID) -> Optional[PDScorecard]:
        """Get a build by ID, excluding soft-deleted records."""
        return self.db.query(PDScorecard).filter(
            PDScorecard.id == build_id,
            PDScorecard.is_deleted == False,
        ).first()

    def get_builds_for_user(self, user_id: UUID) -> List[PDScorecard]:
        """Get all builds created by a user, newest first."""
        return self.db.query(PDScorecard).filter(
            PDScorecard.created_by_user_id == user_id,
            PDScorecard.is_deleted == False,
        ).order_by(PDScorecard.updated_at.desc()).all()

    def get_builds_by_engagement(
        self, engagement_id: UUID, user_id: Optional[UUID] = None
    ) -> List[PDScorecard]:
        """
        Get builds for an engagement, newest first.
        When user_id is provided, only builds created by that user are returned.
        """
        query = self.db.query(PDScorecard).filter(
            PDScorecard.engagement_id == engagement_id,
            PDScorecard.is_deleted == False,
        )
        if user_id:
            query = query.filter(PDScorecard.created_by_user_id == user_id)
        return query.order_by(PDScorecard.updated_at.desc()).all()

    def delete_build(self, build_id: UUID) -> Optional[PDScorecard]:
        """Soft delete a build."""
        build = self.get_build(build_id)
        if not build:
            return None
        build.is_deleted = True
        build.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        logger.info(f"Soft deleted PD scorecard build {build_id}")
        return build

    # ==================== Step 1: Inputs ====================

    def update_files(
        self,
        build_id: UUID,
        file_ids: List[str],
        file_mappings: Dict[str, str],
        stored_files: Optional[Dict[str, str]] = None,
    ) -> Optional[PDScorecard]:
        """
        Attach uploaded files. Appends to whatever is already attached so the
        matrix and any reference PDs can arrive in separate batches.
        """
        build = self.get_build(build_id)
        if not build:
            return None

        existing_ids = list(build.file_ids or [])
        for file_id in file_ids:
            if file_id not in existing_ids:
                existing_ids.append(file_id)
        build.file_ids = existing_ids
        build.file_mappings = {**(build.file_mappings or {}), **file_mappings}
        if stored_files is not None:
            build.stored_files = {**(build.stored_files or {}), **stored_files}
        build.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(build)
        logger.info(f"Attached {len(file_ids)} file(s) to PD scorecard build {build_id}")
        return build

    def update_inputs(
        self, build_id: UUID, inputs: PDScorecardInputsRequest
    ) -> Optional[PDScorecard]:
        """Save the client name, FY range, reference PD flags and notes."""
        build = self.get_build(build_id)
        if not build:
            return None

        build.client_name = inputs.client_name
        build.fy_range = inputs.fy_range
        build.reference_pd_files = list(inputs.reference_pd_files)
        build.pasted_notes = inputs.pasted_notes
        build.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(build)
        logger.info(f"Updated inputs for PD scorecard build {build_id}")
        return build

    # ==================== Step 2: Roles ====================

    def update_matrix_rows(
        self,
        build_id: UUID,
        rows: List[Dict[str, Any]],
        tokens_used: Optional[int] = None,
        model: Optional[str] = None,
    ) -> Optional[PDScorecard]:
        """Save the parsed matrix rows and advance the status."""
        build = self.get_build(build_id)
        if not build:
            return None

        build.matrix_rows = [normalise_matrix_row(row) for row in rows]
        build.status = 'roles_identified'
        self._record_ai_usage(build, tokens_used, model)
        build.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(build)
        logger.info(f"Saved {len(rows)} matrix row(s) for PD scorecard build {build_id}")
        return build

    def replace_roles(
        self, build_id: UUID, roles: List[RoleInput]
    ) -> Optional[PDScorecard]:
        """
        Save the confirmed role list in display order.

        Roles carrying an ID are updated in place so their drafts survive; roles
        without one are created. Any existing role missing from the request is
        soft deleted rather than dropped, so approved work is never lost.
        """
        build = self.get_build(build_id)
        if not build:
            return None

        existing = {
            role.id: role
            for role in self.db.query(PDScorecardRole).filter(
                PDScorecardRole.pd_scorecard_id == build_id,
                PDScorecardRole.is_deleted == False,
            ).all()
        }

        seen_ids = set()
        now = datetime.now(timezone.utc)

        for order, role_input in enumerate(roles):
            role = existing.get(role_input.id) if role_input.id else None
            if role:
                role.role_title = role_input.role_title
                role.person_name = role_input.person_name
                role.included = role_input.included
                role.sort_order = order
                role.updated_at = now
                seen_ids.add(role.id)
            else:
                role = PDScorecardRole(
                    pd_scorecard_id=build_id,
                    role_title=role_input.role_title,
                    person_name=role_input.person_name,
                    included=role_input.included,
                    sort_order=order,
                )
                self.db.add(role)

        for role_id, role in existing.items():
            if role_id not in seen_ids:
                role.is_deleted = True
                role.updated_at = now

        build.status = 'in_progress'
        build.updated_at = now

        self.db.commit()
        self.db.refresh(build)
        logger.info(f"Saved {len(roles)} role(s) for PD scorecard build {build_id}")
        return build

    def attach_source_responsibilities(
        self, role_id: UUID, responsibilities: Dict[str, Any]
    ) -> Optional[PDScorecardRole]:
        """Cache the matrix rows attributed to a role, grouped by retain/gain/lose."""
        role = self.get_role(role_id)
        if not role:
            return None

        role.source_responsibilities = responsibilities
        role.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(role)
        return role

    # ==================== Roles ====================

    def get_role(self, role_id: UUID) -> Optional[PDScorecardRole]:
        """Get a role by ID, excluding soft-deleted records."""
        return self.db.query(PDScorecardRole).filter(
            PDScorecardRole.id == role_id,
            PDScorecardRole.is_deleted == False,
        ).first()

    def get_roles(self, build_id: UUID, included_only: bool = False) -> List[PDScorecardRole]:
        """Get a build's roles in display order."""
        query = self.db.query(PDScorecardRole).filter(
            PDScorecardRole.pd_scorecard_id == build_id,
            PDScorecardRole.is_deleted == False,
        )
        if included_only:
            query = query.filter(PDScorecardRole.included == True)
        return query.order_by(PDScorecardRole.sort_order).all()

    # ==================== Step 3: Position Description ====================

    def update_pd_content(
        self,
        role_id: UUID,
        pd_content: Dict[str, Any],
        tokens_used: Optional[int] = None,
        model: Optional[str] = None,
    ) -> Optional[PDScorecardRole]:
        """
        Save a PD draft. Saving always returns the role to draft state — an edit
        after approval must be re-approved.
        """
        role = self.get_role(role_id)
        if not role:
            return None

        role.pd_content = pd_content
        role.pd_status = 'draft'
        role.pd_approved_at = None
        role.updated_at = datetime.now(timezone.utc)

        if tokens_used or model:
            self._record_ai_usage(role.pd_scorecard, tokens_used, model)

        self.db.commit()
        self.db.refresh(role)
        logger.info(f"Saved PD draft for role {role_id}")
        return role

    def approve_pd(self, role_id: UUID) -> Optional[PDScorecardRole]:
        """Mark a PD as approved, unlocking scorecard generation."""
        role = self.get_role(role_id)
        if not role:
            return None
        if not role.pd_content:
            raise ValueError("Generate the position description before approving it")

        role.pd_status = 'approved'
        role.pd_approved_at = datetime.now(timezone.utc)
        role.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(role)
        logger.info(f"Approved PD for role {role_id}")
        return role

    # ==================== Step 4: Scorecard ====================

    def update_scorecard_content(
        self,
        role_id: UUID,
        scorecard_content: Dict[str, Any],
        tokens_used: Optional[int] = None,
        model: Optional[str] = None,
    ) -> Optional[PDScorecardRole]:
        """Save a scorecard draft, returning the role to draft state."""
        role = self.get_role(role_id)
        if not role:
            return None

        role.scorecard_content = scorecard_content
        role.scorecard_status = 'draft'
        role.scorecard_approved_at = None
        role.updated_at = datetime.now(timezone.utc)

        if tokens_used or model:
            self._record_ai_usage(role.pd_scorecard, tokens_used, model)

        self.db.commit()
        self.db.refresh(role)
        logger.info(f"Saved scorecard draft for role {role_id}")
        return role

    def approve_scorecard(self, role_id: UUID) -> Optional[PDScorecardRole]:
        """Mark a scorecard as approved and complete the build if every role is done."""
        role = self.get_role(role_id)
        if not role:
            return None
        if not role.scorecard_content:
            raise ValueError("Generate the scorecard before approving it")

        now = datetime.now(timezone.utc)
        role.scorecard_status = 'approved'
        role.scorecard_approved_at = now
        role.updated_at = now

        self.db.commit()
        self.db.refresh(role)
        logger.info(f"Approved scorecard for role {role_id}")

        self._refresh_completion(role.pd_scorecard_id)
        self.db.refresh(role)
        return role

    def _refresh_completion(self, build_id: UUID) -> None:
        """Mark the build complete once every included role has both approvals."""
        build = self.get_build(build_id)
        if not build:
            return

        roles = self.get_roles(build_id, included_only=True)
        all_done = bool(roles) and all(
            role.pd_status == 'approved' and role.scorecard_status == 'approved'
            for role in roles
        )

        if all_done:
            build.status = 'completed'
            if not build.completed_at:
                build.completed_at = datetime.now(timezone.utc)
        elif build.status == 'completed':
            # A new role or a re-edit reopens the build.
            build.status = 'in_progress'

        build.updated_at = datetime.now(timezone.utc)
        self.db.commit()

    # ==================== Step progress ====================

    def update_step_progress(
        self,
        build_id: UUID,
        current_step: Optional[int] = None,
        max_step_reached: Optional[int] = None,
    ) -> Optional[PDScorecard]:
        """Persist the user's position in the workflow."""
        build = self.get_build(build_id)
        if not build:
            return None

        if current_step is not None:
            build.current_step = current_step
        if max_step_reached is not None:
            build.max_step_reached = max(max_step_reached, build.max_step_reached or 0)
        build.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(build)
        return build

    # ==================== Helpers ====================

    @staticmethod
    def _record_ai_usage(
        build: PDScorecard, tokens_used: Optional[int], model: Optional[str]
    ) -> None:
        """Accumulate token usage and record the model that produced the output."""
        if not build:
            return
        if tokens_used:
            build.ai_tokens_used = (build.ai_tokens_used or 0) + tokens_used
        if model:
            build.ai_model_used = model


def normalise_matrix_row(row: Any) -> Dict[str, Optional[str]]:
    """
    Coerce a matrix row into the canonical key set. Unknown keys are dropped and
    missing values stay blank — nothing is guessed.
    """
    if hasattr(row, "model_dump"):
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


def rows_for_role(
    matrix_rows: List[Dict[str, Any]], role_title: str, person_name: Optional[str] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Pull the matrix rows belonging to one role and group them by flag.

    The matrix sets `name` only on the first row of each person's block, so rows
    are attributed by walking down and carrying the last name seen.
    """
    targets = {t.strip().lower() for t in (role_title, person_name) if t and t.strip()}
    grouped: Dict[str, List[Dict[str, Any]]] = {"retain": [], "gain": [], "lose": []}

    current_name: Optional[str] = None
    for row in matrix_rows or []:
        name = (row or {}).get("name")
        if name and name.strip():
            current_name = name.strip()

        if not current_name or current_name.lower() not in targets:
            continue
        if not (row or {}).get("role_description"):
            continue

        for flag in ("retain", "gain", "lose"):
            value = (row or {}).get(flag)
            if value and str(value).strip().upper().startswith("Y"):
                grouped[flag].append(row)

    return grouped


def get_pd_scorecard_service(db: Session) -> PDScorecardService:
    """Dependency function to get the PD scorecard service"""
    return PDScorecardService(db)
