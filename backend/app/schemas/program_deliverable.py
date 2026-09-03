"""
Pydantic schemas for the Value Builder deliverables API
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID


# ----------------------------------------------------------------------
# Responses
# ----------------------------------------------------------------------
class DeliverableItem(BaseModel):
    """One deliverable as rendered for an engagement."""
    deliverable_id: UUID = Field(..., description="Address for mutations: the library id for a preset, the instance id for an advisor-added deliverable")
    source: str = Field(..., description="'preset' | 'advisor'")
    title: str
    description: Optional[str] = None
    is_mandatory: bool
    is_in_scope: bool = Field(..., description="False means scoped out: retained but excluded from completion")
    is_complete: bool
    task_count: int = Field(
        0,
        description="Tasks generated from this deliverable. Display state only - a task's status never affects is_complete, and vice versa",
    )


class ModuleDeliverables(BaseModel):
    """A module's deliverables and its derived status."""
    module_code: str = Field(..., description="e.g. 'V1'..'V11'")
    status: str = Field(..., description="'not_started' | 'in_progress' | 'completed'")
    deliverables: List[DeliverableItem] = Field(
        default_factory=list,
        description="Ordered: presets by library display_order, then advisor-added by creation time",
    )


class DeliverableView(BaseModel):
    """The composed deliverables-and-status view for an engagement."""
    engagement_id: UUID
    program_type: str = Field(..., description="Matches Engagement.tool, e.g. 'value_builder'")
    modules: List[ModuleDeliverables] = Field(
        default_factory=list,
        description="Only modules that have at least one deliverable, ordered by module_code",
    )


class TaskGenerationResult(BaseModel):
    """
    The outcome of an advisor's "Create tasks" click, plus the refreshed view.

    `view` is the whole DeliverableView so the caller can replace state in one
    go, exactly as every mutation on this router already does. `created_count`
    is separate because zero is a legitimate, non-error outcome worth reporting
    back - every deliverable already had a task, or all were scoped out.
    """
    created_count: int = Field(..., description="Tasks actually created by this call")
    skipped_count: int = Field(..., description="Deliverables passed over: already tasked, scoped out, or complete")
    view: DeliverableView


# ----------------------------------------------------------------------
# Requests
# ----------------------------------------------------------------------
class DeliverableCompleteUpdate(BaseModel):
    is_complete: bool = Field(..., description="True marks the deliverable complete, False clears it")


class DeliverableScopeUpdate(BaseModel):
    is_in_scope: bool = Field(..., description="False scopes the deliverable out; True brings it back in")


class AdvisorDeliverableCreate(BaseModel):
    """A deliverable that exists on this engagement only."""
    module_code: str = Field(..., max_length=20, description="Module this deliverable belongs to")
    title: str = Field(..., max_length=255)
    is_mandatory: bool = Field(..., description="Required because there is no library row to inherit it from")
    description: Optional[str] = None


class AdvisorDeliverableUpdate(BaseModel):
    """
    Partial edit of an advisor-added deliverable.

    Only fields actually present in the request body are forwarded, so omitting
    one leaves it unchanged. Sending an explicit null for title or is_mandatory
    is rejected rather than nulling a required field.
    """
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    is_mandatory: Optional[bool] = None
