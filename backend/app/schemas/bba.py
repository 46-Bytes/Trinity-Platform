"""
BBA (Business Benchmark Analysis) Pydantic schemas
"""
from pydantic import BaseModel, Field, ConfigDict
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
    """
    Schema for questionnaire (Step 2).
    Accepts both camelCase (from frontend) and snake_case.
    """
    model_config = ConfigDict(populate_by_name=True)

    client_name: str = Field(..., alias="clientName", description="Client name")
    industry: str = Field(..., description="Industry")
    company_size: str = Field(..., alias="companySize", description="Company size: startup, small, medium, large, enterprise")
    locations: str = Field(..., description="Locations")
    exclusions: Optional[str] = Field(None, description="Areas or topics to exclude")
    constraints: Optional[str] = Field(None, description="Constraints or limitations")
    preferred_ranking: Optional[str] = Field(None, alias="preferredRanking", description="How findings should be ranked")
    strategic_priorities: str = Field(..., alias="strategicPriorities", description="Strategic priorities for next 12 months")
    exclude_sale_readiness: bool = Field(False, alias="excludeSaleReadiness", description="Whether to exclude sale-readiness")


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


class BBAStepProgressUpdate(BaseModel):
    """Schema for updating BBA step progress"""
    current_step: Optional[int] = Field(None, ge=1, le=9, description="Current step the user is on (1-9)")
    max_step_reached: Optional[int] = Field(None, ge=1, le=9, description="Maximum step the user has reached (1-9)")


# Step 3: Draft Findings schemas
class BBAFinding(BaseModel):
    """Schema for a single finding"""
    rank: int = Field(..., description="Finding rank (1-10)")
    title: str = Field(..., description="Finding title")
    summary: str = Field(..., description="One-line summary")
    priority_area: str = Field(..., description="Category/theme")
    impact: str = Field("medium", description="Impact level: high, medium, low")
    urgency: str = Field("short-term", description="Urgency: immediate, short-term, medium-term")


class BBADraftFindingsRequest(BaseModel):
    """Request schema for generating draft findings"""
    custom_instructions: Optional[str] = Field(None, description="Additional instructions from advisor")


class BBADraftFindingsResponse(BaseModel):
    """Response schema for draft findings"""
    findings: List[BBAFinding] = Field(..., description="List of ranked findings")
    analysis_notes: Optional[str] = Field(None, description="Notes on analysis approach")
    files_analysed: Optional[List[str]] = Field(None, description="Files that were analysed")
    tokens_used: int = Field(0, description="Tokens used")
    model: str = Field("", description="Model used")


class BBAFindingsEdit(BaseModel):
    """Schema for editing draft findings"""
    findings: List[BBAFinding] = Field(..., description="Edited list of findings")


# Step 4: Expanded Findings schemas
class BBAExpandedFinding(BaseModel):
    """Schema for an expanded finding"""
    rank: int
    title: str
    priority_area: str
    paragraphs: List[str] = Field(..., description="1-3 paragraphs explaining the finding")
    key_points: Optional[List[str]] = Field(None, description="Bullet point key points")


class BBAExpandedFindingsResponse(BaseModel):
    """Response schema for expanded findings"""
    expanded_findings: List[BBAExpandedFinding]
    tokens_used: int = 0
    model: str = ""


# Step 5: Snapshot Table schemas
class BBASnapshotRow(BaseModel):
    """Schema for a snapshot table row"""
    rank: int
    priority_area: str
    key_finding: str
    recommendation: str


class BBASnapshotTableResponse(BaseModel):
    """Response schema for snapshot table"""
    title: str = "Key Findings & Recommendations Snapshot"
    rows: List[BBASnapshotRow]
    tokens_used: int = 0
    model: str = ""


# Step 6: 12-Month Plan schemas
class BBARecommendation(BaseModel):
    """Schema for a single recommendation"""
    number: int
    title: str
    timing: str = Field(..., description="e.g., Month 1-3")
    purpose: str
    key_objectives: List[str]
    actions: List[str]
    bba_support: str
    expected_outcomes: List[str]


class BBATimelineRow(BaseModel):
    """Schema for timeline summary row"""
    rec_number: int
    recommendation: str
    focus_area: str
    timing: str
    key_outcome: str


class BBATwelveMonthPlanResponse(BaseModel):
    """Response schema for 12-month plan"""
    plan_notes: str
    recommendations: List[BBARecommendation]
    timeline_summary: Optional[Dict[str, Any]] = None
    tokens_used: int = 0
    model: str = ""


# Phase 2 – Excel Task Planner (Engagement Planner)

class BBATaskPlannerSettings(BaseModel):
    """
    Phase 2 task planner context.
    Mirrors the advisor interaction:
    - lead/support advisors
    - total advisors
    - max advisor hours per month
    - engagement start month/year
    """

    lead_advisor: str = Field(..., description="Lead advisor display name")
    support_advisor: Optional[str] = Field(
        None, description="Support advisor display name (optional)"
    )
    advisor_count: int = Field(
        ...,
        gt=0,
        description="Total number of advisors working on the engagement",
    )
    max_hours_per_month: int = Field(
        ...,
        gt=0,
        description="Maximum combined advisor hours available per month",
    )
    # Use numeric months for backend logic; frontend can map from 'November 2025'
    start_month: int = Field(
        ...,
        ge=1,
        le=12,
        description="Engagement start month as number (1=January, 12=December)",
    )
    start_year: int = Field(
        ...,
        ge=2000,
        le=2100,
        description="Engagement start year (four digits)",
    )


class BBATaskRow(BaseModel):
    """
    Single row in the Excel task planner.
    Matches Excel columns:
    Rec #, Recommendation, Owner, Task, Advisor Hrs, Advisor, Status, Notes, Timing.
    """

    rec_number: int = Field(..., description="Recommendation number (1–10)")
    recommendation: str = Field(..., description="Recommendation title")
    owner: str = Field(
        ...,
        description="Owner of the task (e.g. 'Client', 'BBA', 'Advisor')",
    )
    task: str = Field(..., description="One task per row")
    advisor_hrs: float = Field(
        ...,
        alias="advisorHrs",
        description="Estimated BBA advisor hours for this task (0 for client-only tasks)",
    )
    advisor: Optional[str] = Field(
        None,
        description="Assigned advisor name (typically lead or support advisor)",
    )
    status: str = Field(
        "Not yet started",
        description="Task status; default is 'Not yet started'",
    )
    notes: Optional[str] = Field(
        "",
        description="Free-text notes. Kept blank by default for human input.",
    )
    timing: str = Field(
        ...,
        description="Human-readable real-month timing (e.g. 'Nov–Dec 2025')",
    )


class BBATaskPlannerSummary(BaseModel):
    """Summary for the Phase 2 task planner, including capacity validation."""

    total_bba_hours: float = Field(
        ...,
        description="Total BBA advisor hours allocated across all tasks",
    )
    max_hours_per_month: int = Field(
        ...,
        description=(
            "Configured maximum combined advisor hours per month across all advisors "
            "(capacity = advisor_count × max_hours_per_month)."
        ),
    )
    monthly_hours: Dict[str, float] = Field(
        ...,
        description=(
            "Map of YYYY-MM label to total BBA hours scheduled for that month. "
            "Used to validate per-month capacity."
        ),
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Any capacity warnings (e.g. months exceeding max_hours_per_month)",
    )


class BBATaskPlannerPreviewResponse(BaseModel):
    """
    Response for the Phase 2 task planner preview.
    Returned by the backend before Excel generation so the UI can show/edit rows.
    """

    settings: BBATaskPlannerSettings
    tasks: List[BBATaskRow]
    summary: BBATaskPlannerSummary


# Phase 3 – PowerPoint Presentation Generator

class BBAPresentationSlide(BaseModel):
    """Schema for a single presentation slide."""
    index: int = Field(..., description="Slide position (0-based)")
    type: str = Field(
        ...,
        description=(
            "Slide type: title, executive_summary, structure, "
            "recommendation, timeline, next_steps"
        ),
    )
    title: str = Field(..., description="Slide title / heading")
    subtitle: Optional[str] = Field(None, description="Subtitle (title slide only)")
    bullets: Optional[List[str]] = Field(None, description="Bullet points for content slides")
    finding: Optional[List[str]] = Field(None, description="Finding bullets (recommendation slide)")
    recommendation_bullets: Optional[List[str]] = Field(
        None, description="Recommendation bullets (recommendation slide)"
    )
    outcome: Optional[List[str]] = Field(None, description="Outcome bullets (recommendation slide)")
    rows: Optional[List[Dict[str, Any]]] = Field(None, description="Table rows (timeline slide)")
    approved: bool = Field(False, description="Whether the advisor has approved this slide")


class BBAPresentationSlideEdit(BaseModel):
    """Request schema for editing a single slide."""
    title: Optional[str] = None
    subtitle: Optional[str] = None
    bullets: Optional[List[str]] = None
    finding: Optional[List[str]] = None
    recommendation_bullets: Optional[List[str]] = None
    outcome: Optional[List[str]] = None
    rows: Optional[List[Dict[str, Any]]] = None
    approved: Optional[bool] = None


# Step 7: Edit schemas (still part of Phase 1 report workflow)
class BBAEditRequest(BaseModel):
    """Request schema for applying edits"""
    edit_type: str = Field(..., description="Type: rerank, timing, language, add, remove, merge")
    section: str = Field(..., description="Section to edit: findings, expanded, snapshot, plan")
    changes: Dict[str, Any] = Field(..., description="Specific changes to apply")
    instructions: Optional[str] = Field(None, description="Natural language edit instructions")


class BBAEditResponse(BaseModel):
    """Response schema for edit operation"""
    updated_sections: Dict[str, Any]
    changes_made: List[str]
    warnings: Optional[List[str]] = None
    tokens_used: int = 0
    model: str = ""


# Full response schema
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
    twelve_month_plan: Optional[Dict[str, Any]] = None
    plan_notes: Optional[str] = None
    executive_summary: Optional[str] = None
    final_report: Optional[Dict[str, Any]] = None
    report_version: int = 1
    ai_model_used: Optional[str] = None
    ai_tokens_used: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    questionnaire_completed_at: Optional[datetime] = None
    task_planner_settings: Optional[Dict[str, Any]] = None
    task_planner_tasks: Optional[List[Dict[str, Any]]] = None
    task_planner_summary: Optional[Dict[str, Any]] = None
    presentation_slides: Optional[Dict[str, Any]] = None

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

