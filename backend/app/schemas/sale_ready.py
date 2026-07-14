"""
Pydantic schemas for the Sale Ready Program feature.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import date
from uuid import UUID


# ---- Stage / roadmap views ----
class StageView(BaseModel):
    id: str
    program_type: str
    stage_code: str
    stage_type: str
    default_order: int
    title: str
    description: Optional[str] = None
    is_active: bool
    status: str
    start_date: Optional[str] = None
    due_date: Optional[str] = None
    lead_advisor_id: Optional[str] = None
    priority_order: Optional[int] = None


class StagesResponse(BaseModel):
    program_type: str
    stages: List[StageView]


class RoadmapResponse(BaseModel):
    program_type: str
    modules: List[StageView]


class StageStateUpdate(BaseModel):
    status: Optional[str] = Field(None, description="not_started | in_progress | complete")
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    lead_advisor_id: Optional[UUID] = None


class ModuleOrderUpdate(BaseModel):
    module_order: List[str] = Field(..., description="Ordered list of module stage_codes")


class TaskCompletionResponse(BaseModel):
    total: int
    completed: int


class GenerateResponse(BaseModel):
    generated: bool
    reason: Optional[str] = None
    stages: Optional[int] = None
    tasks: Optional[int] = None
    dd_items: Optional[int] = None


class MemberItem(BaseModel):
    """An assignable person on the engagement (advisor or client)."""
    id: str
    name: Optional[str] = None
    role: Optional[str] = None


# ---- DD items ----
class DDItemBase(BaseModel):
    module_code: str
    category: str
    sub_item: Optional[str] = None
    document_required: Optional[str] = None
    action_step: Optional[str] = None
    responsible_user_id: Optional[UUID] = None
    completed: bool = False
    date_completed: Optional[date] = None
    notes: Optional[str] = None
    media_id: Optional[UUID] = None
    file_link: Optional[str] = None
    display_order: int = 0


class DDItemCreate(DDItemBase):
    pass


class DDItemUpdate(BaseModel):
    module_code: Optional[str] = None
    category: Optional[str] = None
    sub_item: Optional[str] = None
    document_required: Optional[str] = None
    action_step: Optional[str] = None
    responsible_user_id: Optional[UUID] = None
    completed: Optional[bool] = None
    date_completed: Optional[date] = None
    notes: Optional[str] = None
    media_id: Optional[UUID] = None
    file_link: Optional[str] = None
    display_order: Optional[int] = None


class DDItemResponse(BaseModel):
    id: str
    engagement_id: str
    module_code: str
    category: str
    sub_item: Optional[str] = None
    document_required: Optional[str] = None
    action_step: Optional[str] = None
    responsible_user_id: Optional[str] = None
    completed: bool
    date_completed: Optional[str] = None
    notes: Optional[str] = None
    media_id: Optional[str] = None
    file_link: Optional[str] = None
    display_order: int


# ---- Document register ----
class DocumentEntryBase(BaseModel):
    stage_code: str
    document_name: str
    creation_date: Optional[date] = None
    document_id: Optional[str] = None
    renewal_date: Optional[date] = None
    renewal_cost: Optional[float] = None
    notes: Optional[str] = None
    media_id: Optional[UUID] = None
    file_link: Optional[str] = None


class DocumentEntryCreate(DocumentEntryBase):
    pass


class DocumentEntryUpdate(BaseModel):
    stage_code: Optional[str] = None
    document_name: Optional[str] = None
    creation_date: Optional[date] = None
    document_id: Optional[str] = None
    renewal_date: Optional[date] = None
    renewal_cost: Optional[float] = None
    notes: Optional[str] = None
    media_id: Optional[UUID] = None
    file_link: Optional[str] = None


class DocumentEntryResponse(BaseModel):
    id: str
    engagement_id: str
    stage_code: str
    document_name: str
    creation_date: Optional[str] = None
    document_id: Optional[str] = None
    renewal_date: Optional[str] = None
    renewal_cost: Optional[float] = None
    notes: Optional[str] = None
    media_id: Optional[str] = None
    file_link: Optional[str] = None
