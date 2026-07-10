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
    purpose: Optional[str] = None
    preparation_checklist: Optional[List[Dict[str, Any]]] = None
    recommended_tools: Optional[List[Dict[str, Any]]] = None
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
