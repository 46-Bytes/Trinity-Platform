"""
BBA (Business Benchmark Analysis) Pydantic schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime


class BBABase(BaseModel):
    """Base schema for BBA"""
    engagement_id: Optional[UUID] = Field(None, description="Optional engagement ID")


class BBACreate(BBABase):
    """Schema for creating a new BBA project"""
    pass


class BBAFileUpload(BaseModel):
    """Schema for file upload step"""
    file_ids: List[str] = Field(..., description="List of OpenAI file IDs")
    file_mappings: Dict[str, str] = Field(..., description="Mapping of filename to file_id")


class BBAQuestionnaire(BaseModel):
    """Schema for questionnaire (Step 2)"""
    client_name: str = Field(..., description="Client name")
    industry: str = Field(..., description="Industry")
    company_size: str = Field(..., description="Company size: startup, small, medium, large, enterprise")
    locations: str = Field(..., description="Locations")
    exclusions: Optional[str] = Field(None, description="Areas or topics to exclude")
    constraints: Optional[str] = Field(None, description="Constraints or limitations")
    preferred_ranking: Optional[str] = Field(None, description="How findings should be ranked")
    strategic_priorities: str = Field(..., description="Strategic priorities for next 12 months")
    exclude_sale_readiness: bool = Field(False, description="Whether to exclude sale-readiness")


class BBAUpdate(BaseModel):
    """Schema for updating BBA"""
    status: Optional[str] = None
    file_ids: Optional[List[str]] = None
    file_mappings: Optional[Dict[str, str]] = None
    client_name: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    locations: Optional[str] = None
    exclusions: Optional[str] = None
    constraints: Optional[str] = None
    preferred_ranking: Optional[str] = None
    strategic_priorities: Optional[str] = None
    exclude_sale_readiness: Optional[bool] = None


class BBAResponse(BBABase):
    """Schema for BBA response"""
    id: UUID
    created_by_user_id: UUID
    status: str
    file_ids: Optional[List[str]] = None
    file_mappings: Optional[Dict[str, str]] = None
    client_name: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    locations: Optional[str] = None
    exclusions: Optional[str] = None
    constraints: Optional[str] = None
    preferred_ranking: Optional[str] = None
    strategic_priorities: Optional[str] = None
    exclude_sale_readiness: bool = False
    draft_findings: Optional[Dict[str, Any]] = None
    draft_findings_edited: bool = False
    expanded_findings: Optional[Dict[str, Any]] = None
    snapshot_table: Optional[Dict[str, Any]] = None
    ai_model_used: Optional[str] = None
    ai_tokens_used: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    questionnaire_completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BBAListItem(BaseModel):
    """Schema for BBA list item (summary)"""
    id: UUID
    engagement_id: Optional[UUID] = None
    status: str
    client_name: Optional[str] = None
    industry: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

