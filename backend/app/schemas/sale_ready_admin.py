"""
Sale Ready Management (admin) request and response models.

Admins edit the master content that future engagements are built from: the
program guide, the task templates and the due diligence checklist. The 15
stages and the 16 DD categories are fixed - there is deliberately no schema
here for creating, deleting or reordering either.
"""
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.services import sale_ready_rules as rules


def _clean_lines(values: Optional[List[str]]) -> List[str]:
    """Trim each entry and drop the blanks an empty row in the editor leaves behind."""
    return [v.strip() for v in (values or []) if v and v.strip()]


# ----------------------------------------------------------------------
# Program guide
# ----------------------------------------------------------------------
class WorkflowStep(BaseModel):
    stage: str = Field(..., min_length=1, max_length=30)
    label: str = Field(..., min_length=1, max_length=500)


class ProgramRule(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1, max_length=4000)


class ProgramGuideUpdate(BaseModel):
    """Program-level guide content. Both lists replace what is stored."""
    workflow: Optional[List[WorkflowStep]] = None
    rules: Optional[List[ProgramRule]] = None


class StageGuide(BaseModel):
    purpose: str = ""
    steps: List[str] = Field(default_factory=list)
    watch: List[str] = Field(default_factory=list)
    templates: List[str] = Field(default_factory=list)
    run_with: Optional[str] = None


class StageGuideUpdate(BaseModel):
    """Per-stage guide content. Only the fields sent are changed."""
    purpose: Optional[str] = Field(None, max_length=4000)
    steps: Optional[List[str]] = None
    watch: Optional[List[str]] = None
    templates: Optional[List[str]] = None
    run_with: Optional[str] = Field(None, max_length=1000)

    @field_validator("steps", "watch", "templates")
    @classmethod
    def _strip(cls, v):
        return _clean_lines(v)


class AdminStage(BaseModel):
    """A stage as the admin screen lists it. Read-only apart from `guide`."""
    stage_code: str
    display_code: Optional[str] = None
    stage_type: str
    title: str
    description: Optional[str] = None
    default_order: int
    task_creation: str
    ui_variant: Optional[str] = None
    guide: StageGuide

    model_config = {"from_attributes": True}


class AdminGuideView(BaseModel):
    program: ProgramGuideUpdate
    stages: List[AdminStage]


# ----------------------------------------------------------------------
# Task templates
# ----------------------------------------------------------------------
class AdminTaskTemplate(BaseModel):
    id: UUID
    stage_code: str
    template_key: str
    section: str
    group_title: Optional[str] = None
    title: str
    description: Optional[str] = None
    priority: str
    default_order: int
    due_offset_days: Optional[int] = None
    is_active: bool
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TaskTemplateCreate(BaseModel):
    stage_code: str = Field(..., min_length=1, max_length=30)
    section: str = Field(..., description="must_do or optional")
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=4000)
    group_title: Optional[str] = Field(None, max_length=255)
    priority: str = "medium"
    due_offset_days: Optional[int] = Field(None, ge=0, le=3650)

    @field_validator("section")
    @classmethod
    def _section(cls, v):
        # client_specific tasks are added by the advisor on the engagement, never templated.
        if v not in (rules.SECTION_MUST_DO, rules.SECTION_OPTIONAL):
            raise ValueError("section must be must_do or optional")
        return v


class TaskTemplateUpdate(BaseModel):
    """`stage_code` and `template_key` are the keys engagements were copied against, so neither is editable."""
    section: Optional[str] = None
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=4000)
    group_title: Optional[str] = Field(None, max_length=255)
    priority: Optional[str] = None
    due_offset_days: Optional[int] = Field(None, ge=0, le=3650)
    is_active: Optional[bool] = None

    @field_validator("section")
    @classmethod
    def _section(cls, v):
        if v is not None and v not in (rules.SECTION_MUST_DO, rules.SECTION_OPTIONAL):
            raise ValueError("section must be must_do or optional")
        return v


# ----------------------------------------------------------------------
# Due diligence checklist
# ----------------------------------------------------------------------
class AdminDDTemplate(BaseModel):
    id: UUID
    item_key: str
    stage_code: str
    category_code: str
    category: str
    sub_item_code: str
    sub_item: Optional[str] = None
    document_required: Optional[str] = None
    action_step: Optional[str] = None
    default_order: int
    is_active: bool
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DDCategoryOption(BaseModel):
    """An existing category and its sub-items. The admin picks from these; the structure is fixed."""
    category_code: str
    category: str
    sub_items: List[Dict[str, str]] = Field(
        default_factory=list, description="[{sub_item_code, sub_item, stage_code}]"
    )


class DDTemplateCreate(BaseModel):
    """`category_code` and `sub_item_code` must name a pair that already exists."""
    category_code: str = Field(..., min_length=1, max_length=10)
    sub_item_code: str = Field(..., min_length=1, max_length=10)
    document_required: str = Field(..., min_length=1, max_length=4000)
    action_step: Optional[str] = Field(None, max_length=4000)


class DDTemplateUpdate(BaseModel):
    """The stage and the category structure are fixed, so neither is editable here."""
    document_required: Optional[str] = Field(None, min_length=1, max_length=4000)
    action_step: Optional[str] = Field(None, max_length=4000)
    sub_item: Optional[str] = Field(None, max_length=4000)
    is_active: Optional[bool] = None


# ----------------------------------------------------------------------
# Shared
# ----------------------------------------------------------------------
class ReorderRequest(BaseModel):
    """Ids in their new order. Every id must belong to the group being reordered."""
    ids: List[UUID] = Field(..., min_length=1)
