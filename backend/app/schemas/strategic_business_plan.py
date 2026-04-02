"""
Strategic Business Plan Pydantic schemas
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime


# ---------------------------------------------------------------------------
# Step 1: Setup & Upload
# ---------------------------------------------------------------------------

class SBPCreate(BaseModel):
    """Schema for creating a new Strategic Business Plan project"""
    engagement_id: Optional[UUID] = Field(None, description="Optional engagement ID")


class SBPSetup(BaseModel):
    """Schema for Step 1 background information"""
    model_config = ConfigDict(populate_by_name=True)

    client_name: str = Field(..., alias="clientName", description="Client / business name")
    industry: str = Field(..., description="Industry sector")
    planning_horizon: str = Field(..., alias="planningHorizon", description="1-year, 3-year, 5-year")
    target_audience: str = Field(..., alias="targetAudience",
                                 description="Primary audience: owners, management team, bank, investors")
    additional_context: Optional[str] = Field(None, alias="additionalContext",
                                              description="Additional context or notes")


class SBPFileUpload(BaseModel):
    """Schema for file upload step"""
    file_ids: List[str] = Field(..., description="List of Claude file IDs")
    file_mappings: Dict[str, str] = Field(..., description="Mapping of filename to Claude file_id")


# ---------------------------------------------------------------------------
# Step 2: Cross-Analysis
# ---------------------------------------------------------------------------

class SBPCrossAnalysisRequest(BaseModel):
    """Request schema for triggering cross-analysis"""
    custom_instructions: Optional[str] = Field(None, description="Additional instructions from advisor")


class SBPCrossAnalysisTheme(BaseModel):
    """A single theme identified in cross-analysis"""
    theme: str = Field(..., description="Theme name")
    description: str = Field(..., description="Description of the theme")
    sources: List[str] = Field(default_factory=list, description="Which documents contributed to this theme")
    signal_strength: str = Field("moderate", description="very_strong, strong, moderate")


class SBPCrossAnalysisResponse(BaseModel):
    """Response schema for cross-analysis"""
    recurring_themes: List[SBPCrossAnalysisTheme] = Field(default_factory=list)
    tensions: List[Dict[str, str]] = Field(default_factory=list, description="Tensions or contradictions found")
    correlations: List[Dict[str, str]] = Field(default_factory=list, description="Correlations between issues")
    data_gaps: List[str] = Field(default_factory=list, description="Missing information that may be needed")
    preliminary_observations: List[str] = Field(default_factory=list)
    tokens_used: int = 0
    model: str = ""


class SBPCrossAnalysisNotes(BaseModel):
    """Schema for saving advisor notes on cross-analysis"""
    notes: str = Field(..., description="Advisor notes/corrections on the cross-analysis")


# ---------------------------------------------------------------------------
# Step 3: Section Drafting
# ---------------------------------------------------------------------------

class SBPSection(BaseModel):
    """Schema for a single plan section"""
    key: str = Field(..., description="Section key identifier")
    title: str = Field(..., description="Section display title")
    status: str = Field("pending", description="pending, drafting, drafted, revision_requested, approved")
    content: Optional[str] = Field(None, description="Section content (markdown/HTML)")
    strategic_implications: Optional[str] = Field(None, description="Strategic implications (for diagnostic sections)")
    revision_notes: Optional[str] = Field(None, description="Advisor's revision request notes")
    revision_history: List[Dict[str, Any]] = Field(default_factory=list, description="Past versions")
    approved_at: Optional[str] = Field(None, description="ISO timestamp of approval")
    draft_count: int = Field(0, description="Number of drafts generated")


class SBPDraftSectionRequest(BaseModel):
    """Request schema for drafting a section"""
    custom_instructions: Optional[str] = Field(None, description="Additional instructions for this section")


class SBPRevisionRequest(BaseModel):
    """Request schema for requesting a section revision"""
    revision_notes: str = Field(..., description="What the advisor wants changed")


class SBPSectionEdit(BaseModel):
    """Schema for inline editing a section's content"""
    content: Optional[str] = Field(None, description="Updated section content")
    strategic_implications: Optional[str] = Field(None, description="Updated strategic implications")


class SBPEmergingTheme(BaseModel):
    """A single emerging strategic theme"""
    theme: str
    description: str
    supporting_sections: List[str] = Field(default_factory=list)
    signal_strength: str = Field("moderate")


class SBPEmergingThemesResponse(BaseModel):
    """Response for emerging themes surfacing"""
    themes: List[SBPEmergingTheme] = Field(default_factory=list)
    summary: str = Field("", description="Plain language summary of integrated themes")
    tokens_used: int = 0
    model: str = ""


# ---------------------------------------------------------------------------
# Step 4: Plan Assembly
# ---------------------------------------------------------------------------

class SBPAssembleRequest(BaseModel):
    """Request schema for assembling the final plan"""
    section_order: Optional[List[str]] = Field(None, description="Custom section ordering by key (optional)")


# ---------------------------------------------------------------------------
# Step 5: Export
# ---------------------------------------------------------------------------

class SBPExportRequest(BaseModel):
    """Request schema for export options"""
    include_employee_variant: bool = Field(False, description="Whether to also generate an employee-facing variant")


# ---------------------------------------------------------------------------
# Step tracking
# ---------------------------------------------------------------------------

class SBPStepProgressUpdate(BaseModel):
    """Schema for updating step progress"""
    current_step: Optional[int] = Field(None, ge=1, le=6, description="Current step (1-6)")
    max_step_reached: Optional[int] = Field(None, ge=1, le=6, description="Maximum step reached (1-6)")


# ---------------------------------------------------------------------------
# Step 6: Presentation
# ---------------------------------------------------------------------------

class SBPPresentationSlide(BaseModel):
    """Schema for a single presentation slide"""
    index: int = Field(..., description="Slide position (0-based)")
    type: str = Field(..., description="Slide type: title, section_overview, strategy, financial, roadmap, closing")
    title: str = Field(..., description="Slide title / heading")
    subtitle: Optional[str] = None
    bullets: Optional[List[str]] = None
    rows: Optional[List[Dict[str, Any]]] = None
    approved: bool = Field(False)


class SBPPresentationSlideEdit(BaseModel):
    """Request schema for editing a single slide"""
    title: Optional[str] = None
    subtitle: Optional[str] = None
    bullets: Optional[List[str]] = None
    rows: Optional[List[Dict[str, Any]]] = None
    approved: Optional[bool] = None


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class SBPResponse(BaseModel):
    """Full response schema for a Strategic Business Plan"""
    id: UUID
    engagement_id: Optional[UUID] = None
    diagnostic_id: Optional[UUID] = None
    diagnostic_context: Optional[Dict[str, Any]] = None
    created_by_user_id: UUID
    status: str
    current_step: Optional[int] = None
    max_step_reached: Optional[int] = None
    client_name: Optional[str] = None
    industry: Optional[str] = None
    planning_horizon: Optional[str] = None
    target_audience: Optional[str] = None
    additional_context: Optional[str] = None
    file_ids: Optional[List[str]] = None
    file_mappings: Optional[Dict[str, str]] = None
    file_tags: Optional[Dict[str, str]] = None
    stored_files: Optional[Dict[str, str]] = None
    cross_analysis: Optional[Dict[str, Any]] = None
    cross_analysis_advisor_notes: Optional[str] = None
    sections: Optional[List[Dict[str, Any]]] = None
    current_section_index: Optional[int] = None
    emerging_themes: Optional[Dict[str, Any]] = None
    final_plan: Optional[Dict[str, Any]] = None
    report_version: int = 1
    generated_report_path: Optional[str] = None
    employee_variant_requested: bool = False
    generated_employee_report_path: Optional[str] = None
    presentation_slides: Optional[Dict[str, Any]] = None
    ai_model_used: Optional[str] = None
    ai_tokens_used: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SBPListItem(BaseModel):
    """Schema for list item (summary)"""
    id: UUID
    engagement_id: Optional[UUID] = None
    status: str
    client_name: Optional[str] = None
    industry: Optional[str] = None
    planning_horizon: Optional[str] = None
    current_step: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
