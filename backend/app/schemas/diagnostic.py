"""
Pydantic schemas for Diagnostic model
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from decimal import Decimal


# Base schema with common fields
class DiagnosticBase(BaseModel):
    """Base diagnostic schema"""
    diagnostic_type: str = Field(default="business_health_assessment", description="Type of diagnostic")
    diagnostic_version: str = Field(default="1.0", description="Version of diagnostic questions")


# Schema for creating a diagnostic
class DiagnosticCreate(DiagnosticBase):
    """Schema for creating a new diagnostic"""
    engagement_id: UUID = Field(..., description="The engagement this diagnostic belongs to")
    created_by_user_id: UUID = Field(..., description="Who is launching this diagnostic")
    questions: Dict[str, Any] = Field(..., description="All 200 questions structure from JSON file")


# Schema for updating diagnostic responses (incremental saves)
class DiagnosticResponseUpdate(BaseModel):
    """Schema for updating user responses (autosave)"""
    user_responses: Dict[str, Any] = Field(..., description="User's answers to questions")
    status: Optional[str] = Field(None, description="Update status if needed (e.g., in_progress)")


# Schema for submitting diagnostic for processing
class DiagnosticSubmit(BaseModel):
    """Schema for submitting diagnostic for AI processing"""
    completed_by_user_id: UUID = Field(..., description="Who completed the diagnostic")


# Schema for diagnostic response
class DiagnosticResponse(DiagnosticBase):
    """Schema for diagnostic response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    engagement_id: UUID
    created_by_user_id: UUID
    completed_by_user_id: Optional[UUID] = None
    status: str
    overall_score: Optional[Decimal] = None
    report_url: Optional[str] = None
    tasks_generated_count: int = 0
    ai_model_used: Optional[str] = None
    ai_tokens_used: Optional[int] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: datetime
    
# Schema for diagnostic with full data (questions, responses, scoring)
class DiagnosticDetail(DiagnosticResponse):
    """Schema for detailed diagnostic view including all data"""
    questions: Dict[str, Any]
    user_responses: Optional[Dict[str, Any]] = None
    scoring_data: Optional[Dict[str, Any]] = None
    ai_analysis: Optional[Dict[str, Any]] = None
    module_scores: Optional[Dict[str, Any]] = None
    report_html: Optional[str] = None


# Schema for diagnostic results page
class DiagnosticResults(BaseModel):
    """Schema for diagnostic results view"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    engagement_id: UUID
    status: str
    overall_score: Optional[Decimal] = None
    module_scores: Optional[Dict[str, Any]] = None
    ai_analysis: Optional[Dict[str, Any]] = None
    report_url: Optional[str] = None
    tasks_generated_count: int = 0
    completed_at: Optional[datetime] = None


# Schema for diagnostic list item
class DiagnosticListItem(DiagnosticResponse):
    """Schema for diagnostic in list view"""
    engagement_name: Optional[str] = Field(None, description="Name of the engagement this belongs to")

