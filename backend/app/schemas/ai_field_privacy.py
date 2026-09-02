"""
Pydantic schemas for AI Field Privacy configuration.
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from uuid import UUID


class AIFieldPrivacyItem(BaseModel):
    """Single field privacy setting."""
    field_name: str = Field(..., description="Matches the 'name' key in the questionnaire JSON")
    include_in_ai: bool = Field(True, description="True = send to Claude; False = strip from AI payload")


class AIFieldPrivacyBulkUpdate(BaseModel):
    """Bulk update payload — list of field configs to upsert."""
    fields: List[AIFieldPrivacyItem] = Field(..., description="Field configs to upsert")


class AIFieldPrivacyItemDetail(AIFieldPrivacyItem):
    """Field privacy setting with metadata."""
    updated_at: Optional[datetime] = None
    updated_by_user_id: Optional[UUID] = None

    model_config = {"from_attributes": True}


class AIFieldPrivacyResponse(BaseModel):
    """Response for GET — all stored configs for a questionnaire type."""
    questionnaire_type: str
    fields: List[AIFieldPrivacyItemDetail]
