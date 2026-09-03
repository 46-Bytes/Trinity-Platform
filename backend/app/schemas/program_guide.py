"""
Program Guide Pydantic schemas
"""
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import UUID


class ProgramModuleContentItem(BaseModel):
    """A single module's authored content (no engagement-specific state)."""
    id: UUID
    program_type: str
    module_code: str
    display_order: int
    title: str
    focus: Optional[str] = None
    purpose: Optional[str] = None
    core_outcomes: Optional[List[str]] = None
    preparation_checklist: Optional[List[Dict[str, Any]]] = None
    preparation_summary: Optional[Dict[str, Any]] = None
    sessions: Optional[List[Dict[str, Any]]] = None
    between_sessions: Optional[Dict[str, Any]] = None
    post_session_actions: Optional[Dict[str, Any]] = None
    guardrails: Optional[Dict[str, Any]] = None
    quality_standards: Optional[List[str]] = None
    notes: Optional[List[Dict[str, Any]]] = None
    tables: Optional[List[Dict[str, Any]]] = None
    recommended_tools: Optional[List[Dict[str, Any]]] = None
    required_inputs: Optional[List[Dict[str, Any]]] = None
    # Display-only labels, derived by the seed script from the preset titles.
    # The deliverables the status engine reads are served by /api/deliverables;
    # this stays a flat string list until the composed view replaces it.
    deliverables: Optional[List[str]] = None
    is_active: bool = True

    class Config:
        from_attributes = True


class ProgramGuideModuleItem(ProgramModuleContentItem):
    """A module card as rendered for a specific engagement."""
    effective_rank: Optional[int] = None


class ProgramGuideView(BaseModel):
    """The composed Program Guide view for an engagement."""
    program_type: str
    order_source: str = Field(..., description="'diagnostic' | 'custom' | 'default' | 'unsupported'")
    source_diagnostic_id: Optional[str] = Field(
        None, description="The completed diagnostic whose module scores set the order"
    )
    custom_order_set_at: Optional[datetime] = None
    custom_order_set_by_user_id: Optional[str] = None
    modules: List[ProgramGuideModuleItem]


class DashboardModuleItem(BaseModel):
    """
    One module as a business owner may see it: identity, position and progress.

    Deliberately NOT a subclass of ProgramModuleContentItem. That class carries
    purpose, preparation_checklist, recommended_tools and deliverables, all of
    which are "No" for an owner in Part A's roles matrix - inheriting it is
    exactly how card content would leak back into this view. Every field here is
    listed on purpose; keep it that way.
    """
    module_code: str
    title: str
    effective_rank: Optional[int] = None
    status: str = Field(..., description="'not_started' | 'in_progress' | 'completed'")


class ProgramGuideDashboardView(BaseModel):
    """
    The program dashboard: progress and the module list, nothing else.

    This is the one Program Guide read an owner is allowed. Module card
    contents and diagnostic findings are served elsewhere, behind an
    advisor-only guard.
    """
    program_type: str
    modules: List[DashboardModuleItem]
    total_modules: int
    completed_modules: int
    in_progress_modules: int
    not_started_modules: int


class ProgramGuideOrderUpdate(BaseModel):
    module_order: List[str] = Field(..., description="Ordered module codes, full or partial")


class ModuleMovement(BaseModel):
    module_code: str
    module_name: str
    previous_score: Optional[float] = None
    current_score: Optional[float] = None
    delta: Optional[float] = None
    previous_rag: Optional[str] = None
    current_rag: Optional[str] = None


class ValueMovementResponse(BaseModel):
    has_comparison: bool
    previous_diagnostic_id: Optional[str] = None
    current_diagnostic_id: Optional[str] = None
    overall_score_previous: Optional[float] = None
    overall_score_current: Optional[float] = None
    overall_score_delta: Optional[float] = None
    module_movements: List[ModuleMovement] = Field(default_factory=list)


class ModuleInsight(BaseModel):
    """
    Per-engagement diagnostic state for one module.

    Deliberately separate from ProgramGuideModuleItem, which is authored library
    content plus a position. Everything here is specific to one client and comes
    from the engagement's diagnostic, so joining it into the card schema would
    put per-engagement scores inside the object the owner-facing dashboard
    narrows from. Keeping them apart is what keeps that narrowing safe.
    """
    module_code: str
    module_name: str
    score: Optional[float] = Field(None, description="Module average, 0-5, from the latest completed diagnostic")
    rag: Optional[str] = Field(None, description="'Red' | 'Amber' | 'Green'")
    severity: Optional[str] = Field(None, description="'Critical' | 'High' | 'Moderate' | 'Low' | 'Strong'")
    answered_questions: Optional[int] = Field(
        None,
        description="How many diagnostic questions actually scored to this module. A module scored on three answers is not comparable to one scored on eighteen",
    )
    effective_rank: Optional[int] = Field(None, description="1-based position in this engagement's module order")


class ProgramGuideInsightsView(BaseModel):
    """
    The diagnostic layer of the Program Guide, for every module at once.

    Advisor-only: Part A puts per-module scores in the owner's "No" column,
    which is why this is its own route rather than fields on the guide.

    `has_scores` is false for an engagement whose diagnostic has not been
    completed, which is an ordinary state rather than a failure. `modules`
    always carries all eleven entries either way, so the caller never has to
    guess whether a module was omitted or simply has nothing yet.
    """
    program_type: str
    has_scores: bool
    diagnostic_id: Optional[str] = None
    diagnostic_completed_at: Optional[datetime] = None
    overall_score: Optional[float] = None
    modules: List[ModuleInsight] = Field(default_factory=list)
