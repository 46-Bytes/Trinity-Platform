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
    section_notes: Optional[Dict[str, str]] = None
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
    is_gateway: bool = False
    is_capstone: bool = False


class ProgramGuideView(BaseModel):
    """The composed Program Guide view for an engagement."""
    program_type: str
    order_source: str = Field(..., description="'bba' | 'custom' | 'default' | 'unsupported'")
    source_bba_id: Optional[str] = None
    unmapped_priority_areas: List[str] = Field(default_factory=list)
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
    is_gateway: bool = False
    is_capstone: bool = False
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
