"""
Pydantic schemas for the PD & Role Scorecard models
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID


# ==================== Step 1: Inputs ====================

class PDScorecardInputsRequest(BaseModel):
    """Step 1: the shared inputs (files are uploaded separately)"""
    client_name: Optional[str] = Field(None, description="Business name shown in the PD header")
    fy_range: Optional[str] = Field(None, description="Financial year range for transition sections, e.g. 'FY25-27'")
    reference_pd_files: List[str] = Field(
        default_factory=list,
        description="Filenames to treat as tone-only reference PDs, never as a source of responsibilities",
    )
    pasted_notes: Optional[str] = Field(None, description="Pasted matrix content or extra notes")


# ==================== Step 2: Roles ====================

class PDScorecardExtractRequest(BaseModel):
    """Step 2: parse the uploaded matrix into roles"""
    custom_instructions: Optional[str] = Field(None, description="Optional extra instructions from the advisor")


class RoleInput(BaseModel):
    """A role the advisor has confirmed for the build"""
    id: Optional[UUID] = Field(None, description="Existing role ID; omit to create a new role")
    role_title: str = Field(..., min_length=1, max_length=255)
    person_name: Optional[str] = Field(None, max_length=255)
    included: bool = Field(True, description="Whether this role is part of the build")


class PDScorecardRolesUpdateRequest(BaseModel):
    """Step 2: save the confirmed role list, in display order"""
    roles: List[RoleInput] = Field(..., description="Full replacement set of roles, in display order")


# ==================== Step 3: Position Description ====================

class PDResponsibilityTheme(BaseModel):
    """One themed group of responsibilities in PD section 2"""
    theme: str = Field(..., description="e.g. 'Strategic Leadership'")
    responsibilities: List[str] = Field(default_factory=list)


class PDContent(BaseModel):
    """
    The seven Position Description sections. Transition focus is optional — it
    only appears where the role carries handover or 'lose' items.
    """
    position_purpose: Optional[str] = None
    key_responsibilities: List[PDResponsibilityTheme] = Field(default_factory=list)
    decision_making_authority: List[str] = Field(default_factory=list)
    key_relationships: List[str] = Field(default_factory=list)
    kpis: List[str] = Field(default_factory=list)
    behavioural_expectations: List[str] = Field(default_factory=list)
    transition_focus: List[str] = Field(default_factory=list)


class PDGenerateRequest(BaseModel):
    """Step 3: generate the PD draft for one role"""
    custom_instructions: Optional[str] = Field(None, description="Optional extra instructions from the advisor")


class PDUpdateRequest(BaseModel):
    """Step 3: save advisor edits to the PD draft"""
    pd_content: PDContent


# ==================== Step 4: Scorecard ====================

class ScorecardResponsibilityRow(BaseModel):
    """Section 1 row: nine columns, four of them rating inputs left blank"""
    focus_area: Optional[str] = None
    core_accountability: Optional[str] = None
    performance_indicators: Optional[str] = None


class ScorecardBehaviourRow(BaseModel):
    """Section 2 row"""
    behavioural_focus: Optional[str] = None
    expected_demonstration: Optional[str] = None


class ScorecardMilestoneRow(BaseModel):
    """Section 3 row"""
    milestone: Optional[str] = None
    target_date: Optional[str] = None


class ScorecardContent(BaseModel):
    """The four scorecard sections. Milestones are optional."""
    role_purpose: Optional[str] = None
    responsibilities: List[ScorecardResponsibilityRow] = Field(default_factory=list)
    behaviours: List[ScorecardBehaviourRow] = Field(default_factory=list)
    milestones: List[ScorecardMilestoneRow] = Field(default_factory=list)


class ScorecardGenerateRequest(BaseModel):
    """Step 4: generate the scorecard draft for one role"""
    custom_instructions: Optional[str] = Field(None, description="Optional extra instructions from the advisor")


class ScorecardUpdateRequest(BaseModel):
    """Step 4: save advisor edits to the scorecard draft"""
    scorecard_content: ScorecardContent


# ==================== Step progress ====================

class PDScorecardStepProgressRequest(BaseModel):
    """Persist which step the user is on"""
    current_step: int = Field(..., ge=1, le=4)
    max_step_reached: Optional[int] = Field(None, ge=1, le=4)
