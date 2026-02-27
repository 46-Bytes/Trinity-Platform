"""
Pydantic schemas for Strategy Workbook model
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


# Base schema with common fields
class StrategyWorkbookBase(BaseModel):
    """Base strategy workbook schema"""
    notes: Optional[str] = Field(None, description="User notes or review comments")


# Schema for creating a workbook (upload documents)
class StrategyWorkbookCreate(BaseModel):
    """Schema for creating a new strategy workbook"""
    pass  # Created via file upload endpoint


# Schema for workbook response
class StrategyWorkbookResponse(BaseModel):
    """Schema for strategy workbook response"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    engagement_id: Optional[UUID] = None
    diagnostic_id: Optional[UUID] = None
    created_by_user_id: Optional[UUID] = None
    diagnostic_context: Optional[Dict[str, Any]] = None
    status: str = Field(..., description="draft, extracting, ready, failed")
    uploaded_media_ids: Optional[List[UUID]] = Field(default=[], description="Array of uploaded Media IDs")
    template_path: Optional[str] = None
    generated_workbook_path: Optional[str] = None
    extracted_data: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


# Schema for extraction request
class StrategyWorkbookExtractRequest(BaseModel):
    """Schema for triggering extraction"""
    workbook_id: UUID = Field(..., description="ID of the workbook to extract data for")
    clarification_notes: Optional[str] = Field(
        default=None,
        description="Optional advisor notes about uncertainties or clarifications for the uploaded documents",
    )


# Schema for extraction response
class StrategyWorkbookExtractResponse(BaseModel):
    """Schema for extraction response"""
    workbook_id: UUID
    status: str
    extracted_data: Optional[Dict[str, Any]] = None
    message: str


class StrategyWorkbookPrecheckRequest(BaseModel):
  """Schema for running a precheck on uploaded documents"""
  workbook_id: UUID = Field(..., description="ID of the workbook to precheck")


class StrategyWorkbookPrecheckResponse(BaseModel):
  """Schema for precheck response"""
  workbook_id: UUID
  status: str = Field(..., description="'ok' or 'needs_clarification'")
  clarification_questions: List[str] = Field(default_factory=list)
  message: str


# Schema for generation request
class StrategyWorkbookGenerateRequest(BaseModel):
    """Schema for generating workbook"""
    workbook_id: UUID = Field(..., description="ID of the workbook to generate")
    review_notes: Optional[str] = Field(None, description="Optional review notes before generation")


# Schema for generation response
class StrategyWorkbookGenerateResponse(BaseModel):
    """Schema for generation response"""
    workbook_id: UUID
    status: str
    download_url: Optional[str] = None
    message: str


# Schema for uploaded files response
class StrategyWorkbookUploadResponse(BaseModel):
    """Schema for upload response"""
    workbook_id: UUID
    status: str
    uploaded_files: List[Dict[str, Any]] = Field(default=[], description="List of uploaded file metadata")
    message: str

