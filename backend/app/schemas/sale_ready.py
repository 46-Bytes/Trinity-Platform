"""
Sale Ready Pydantic schemas: the roadmap, stage detail, tasks and DD checklist.

Status and counts are always server-derived from app/services/sale_ready_rules.py;
the client never computes a stage's status itself.
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ----------------------------------------------------------------------
# Shared
# ----------------------------------------------------------------------
class SaleReadyPerson(BaseModel):
    """An engagement member who can lead a stage or be responsible for an item."""
    id: UUID
    name: str
    role: str


class RoadmapStage(BaseModel):
    stage_code: str
    display_code: Optional[str] = None
    title: str
    stage_type: str = Field(..., description="'pre_module' | 'module' | 'post_module'")
    ui_variant: Optional[str] = None
    status: str = Field(..., description="'not_started' | 'in_progress' | 'completed'")
    effective_rank: Optional[int] = None
    is_pinned_last: bool = False
    tasks_created: bool
    must_do_total: int
    must_do_resolved: int
    dd_total: int
    dd_yes: int
    start_date: Optional[date] = None
    due_date: Optional[date] = None


class RoadmapProgress(BaseModel):
    phases_completed: int
    phases_total: int
    modules_completed: int
    modules_total: int
    must_do_resolved: int
    must_do_total: int
    dd_yes: int
    dd_total: int
    percent: int


class GapSummary(BaseModel):
    total: int
    fix: int
    disclose: int
    refer: int
    unhandled: int


class RoadmapCloseout(BaseModel):
    is_closed: bool
    closed_at: Optional[datetime] = None
    referred_to_benchmark: bool


class RoadmapIssues(BaseModel):
    addressed: int
    total: int


class SaleReadyRoadmap(BaseModel):
    engagement_id: UUID
    order_source: str = Field(..., description="'diagnostic' | 'custom' | 'default'")
    phases: List[RoadmapStage]
    modules: List[RoadmapStage] = Field(..., description="Effective order, pinned module last")
    post_phases: List[RoadmapStage]
    progress: RoadmapProgress
    gaps: GapSummary
    lead_advisor_name: Optional[str] = None
    closeout: RoadmapCloseout
    sale_planner_issues: RoadmapIssues


# ----------------------------------------------------------------------
# DD items
# ----------------------------------------------------------------------
class DDItem(BaseModel):
    id: UUID
    item_key: str
    stage_code: str
    stage_title: str
    category_code: str
    category: str
    sub_item_code: str
    sub_item: Optional[str] = None
    document_required: Optional[str] = None
    action_step: Optional[str] = None
    display_order: int
    status: Optional[str] = Field(None, description="None, 'yes', 'in_progress', 'no' or 'not_applicable'")
    gap_handling: Optional[str] = Field(None, description="Stored choice; only counts while status is 'no'")
    flag_for_m8: bool
    responsible_user_id: Optional[UUID] = None
    notes: Optional[str] = None
    date_completed: Optional[date] = None
    status_changed_at: Optional[datetime] = None


class DDStats(BaseModel):
    total: int
    yes: int
    in_progress: int
    no: int
    not_applicable: int
    no_status: int
    flagged: int
    referred: int


class DDStageOption(BaseModel):
    stage_code: str
    title: str


class DDChecklist(BaseModel):
    items: List[DDItem]
    stats: DDStats
    stages: List[DDStageOption]
    people: List[SaleReadyPerson]


class DDItemUpdate(BaseModel):
    """Every field is optional; only the fields sent are changed."""
    status: Optional[str] = None
    gap_handling: Optional[str] = None
    notes: Optional[str] = None
    responsible_user_id: Optional[UUID] = None
    flag_for_m8: Optional[bool] = None


# ----------------------------------------------------------------------
# Stage detail
# ----------------------------------------------------------------------
class StageTask(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    section: str = Field(..., description="'must_do' | 'optional' | 'client_specific'")
    group_title: Optional[str] = None
    status: str
    sale_ready_state: Optional[str] = Field(
        None, description="Sale Ready only: 'not_applicable' or 'blocked'; null otherwise"
    )
    assigned_to_user_id: Optional[UUID] = None
    due_date: Optional[date] = None
    notes: Optional[str] = None
    from_template: bool


class TemplatePreviewTask(BaseModel):
    title: str
    section: str
    group_title: Optional[str] = None


class StageQA(BaseModel):
    passed: bool
    open_must_do: int
    dd_without_status: int
    reasons: List[str]


class StageDetail(BaseModel):
    stage: RoadmapStage
    task_creation: str
    lead_advisor_id: Optional[UUID] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completed_by_name: Optional[str] = None
    updated_at: Optional[datetime] = None
    qa: StageQA
    tasks: List[StageTask]
    template_preview: List[TemplatePreviewTask]
    dd_items: List[DDItem]
    flagged_for_review: List[DDItem] = Field(
        default_factory=list, description="M8 only: DD items flagged for review, across every stage"
    )
    ui_config: Optional[Dict[str, Any]] = None
    guide: Dict[str, Any] = Field(
        default_factory=dict,
        description="This engagement's frozen stage guide: purpose, steps, watch, templates, run_with",
    )
    people: List[SaleReadyPerson]


class StageUpdate(BaseModel):
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    lead_advisor_id: Optional[UUID] = None


class StageTaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class StageTaskUpdate(BaseModel):
    status: Optional[str] = None
    sale_ready_state: Optional[str] = Field(None, description="'not_applicable', 'blocked', or null to clear")
    assigned_to_user_id: Optional[UUID] = None
    due_date: Optional[date] = None
    notes: Optional[str] = None


class ModuleOrderUpdate(BaseModel):
    module_order: List[str] = Field(..., min_length=1)


# ----------------------------------------------------------------------
# Sale Planner and Close-out
# ----------------------------------------------------------------------
class SalePlannerView(BaseModel):
    config: Dict[str, Any] = Field(..., description="Option lists and questions from the stage's ui_config")
    sale_type: Optional[str] = None
    sale_structures: List[str]
    value_propositions: Dict[str, str]
    marketing_answers: Dict[str, str]
    issues: Dict[str, Dict[str, Any]] = Field(..., description='{issue_key: {"addressed": bool, "note": text}}')
    issues_addressed: int
    issues_total: int
    updated_at: Optional[datetime] = None
    updated_by_name: Optional[str] = None


class SalePlannerUpdate(BaseModel):
    """sale_type and sale_structures replace; the three maps merge by key, and null removes a key."""
    sale_type: Optional[str] = None
    sale_structures: Optional[List[str]] = None
    value_propositions: Optional[Dict[str, Optional[str]]] = None
    marketing_answers: Optional[Dict[str, Optional[str]]] = None
    issues: Optional[Dict[str, Optional[Dict[str, Any]]]] = None


class CloseoutView(BaseModel):
    fresh_appraisal_required: bool
    referred_to_benchmark: bool
    ongoing_assistance: Optional[str] = None
    is_closed: bool
    closed_at: Optional[datetime] = None
    closed_by_name: Optional[str] = None
    engagement_status: str
    engagement_completed_at: Optional[datetime] = None
    can_close: bool = Field(
        False, description="Whether the current user may close or reopen the program"
    )


class CloseoutUpdate(BaseModel):
    fresh_appraisal_required: Optional[bool] = None
    referred_to_benchmark: Optional[bool] = None
    ongoing_assistance: Optional[str] = None


class CloseProgramRequest(CloseoutUpdate):
    """The decisions are saved with the close, in the same transaction."""
    confirm_without_referral: bool = False


class SaleReadyGuideView(BaseModel):
    """An engagement's frozen program guide, as the Program guide tab renders it."""
    program: Dict[str, Any] = Field(
        default_factory=dict, description="{'workflow': [{stage,label}], 'rules': [{title,body}]}"
    )
    stages: Dict[str, Any] = Field(
        default_factory=dict, description="Stage code -> {purpose, steps, watch, templates, run_with}"
    )
