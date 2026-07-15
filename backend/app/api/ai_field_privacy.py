"""
AI Field Privacy API — admin/superadmin control over which fields are sent to Claude.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import logging

from ..database import get_db
from ..models.user import User, UserRole
from ..models.ai_field_privacy import AIFieldPrivacy
from ..schemas.ai_field_privacy import (
    AIFieldPrivacyBulkUpdate,
    AIFieldPrivacyItemDetail,
    AIFieldPrivacyResponse,
)
from ..utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai-field-privacy", tags=["ai-field-privacy"])

ALLOWED_TYPES = {"sale_ready", "value_builder"}


def _require_admin(current_user: User) -> None:
    if current_user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin or superadmin can manage AI field privacy settings",
        )


def _validate_type(questionnaire_type: str) -> None:
    if questionnaire_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"questionnaire_type must be one of: {', '.join(ALLOWED_TYPES)}",
        )


@router.get("/{questionnaire_type}", response_model=AIFieldPrivacyResponse)
async def get_field_configs(
    questionnaire_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all stored AI privacy configs for the given questionnaire type."""
    _require_admin(current_user)
    _validate_type(questionnaire_type)

    rows = (
        db.query(AIFieldPrivacy)
        .filter(AIFieldPrivacy.questionnaire_type == questionnaire_type)
        .all()
    )

    fields = [AIFieldPrivacyItemDetail.model_validate(row) for row in rows]
    return AIFieldPrivacyResponse(questionnaire_type=questionnaire_type, fields=fields)


@router.put("/{questionnaire_type}", response_model=AIFieldPrivacyResponse)
async def update_field_configs(
    questionnaire_type: str,
    payload: AIFieldPrivacyBulkUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upsert AI privacy flags for a list of fields."""
    _require_admin(current_user)
    _validate_type(questionnaire_type)

    for item in payload.fields:
        existing = (
            db.query(AIFieldPrivacy)
            .filter(
                AIFieldPrivacy.questionnaire_type == questionnaire_type,
                AIFieldPrivacy.field_name == item.field_name,
            )
            .first()
        )
        if existing:
            existing.include_in_ai = item.include_in_ai
            existing.updated_by_user_id = current_user.id
        else:
            db.add(
                AIFieldPrivacy(
                    questionnaire_type=questionnaire_type,
                    field_name=item.field_name,
                    include_in_ai=item.include_in_ai,
                    updated_by_user_id=current_user.id,
                )
            )

    db.commit()
    logger.info(
        f"[AIFieldPrivacy] {current_user.email} updated {len(payload.fields)} fields "
        f"for {questionnaire_type}"
    )

    rows = (
        db.query(AIFieldPrivacy)
        .filter(AIFieldPrivacy.questionnaire_type == questionnaire_type)
        .all()
    )
    fields = [AIFieldPrivacyItemDetail.model_validate(row) for row in rows]
    return AIFieldPrivacyResponse(questionnaire_type=questionnaire_type, fields=fields)
