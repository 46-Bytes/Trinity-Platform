"""
Pydantic schemas for the Roles & Responsibilities Matrix model
"""
from pydantic import BaseModel, Field
from typing import Optional, List


class StaffMember(BaseModel):
    """A key staff member supplied by the advisor"""
    name: str = Field(..., description="Staff member name, e.g. 'Scott'")
    role_title: Optional[str] = Field(None, description="Current role or title, e.g. 'Director'")


class MatrixRow(BaseModel):
    """
    A single row of the matrix. Field order mirrors the Job Roles columns:
    Name | Role Descriptions | Time | Priorities | Retain | Gain | Lose | Action | Resp | When
    Missing information stays blank — it is never estimated.
    """
    name: Optional[str] = Field(None, description="Only set on the first row of each person's block")
    role_description: Optional[str] = None
    time: Optional[str] = None
    priorities: Optional[str] = None
    retain: Optional[str] = Field(None, description="'Y' or blank")
    gain: Optional[str] = Field(None, description="'Y' or blank")
    lose: Optional[str] = Field(None, description="'Y' or blank")
    action: Optional[str] = None
    resp: Optional[str] = None
    when: Optional[str] = None


class RolesMatrixInputsRequest(BaseModel):
    """Step 1: the advisor's four required inputs (files are uploaded separately)"""
    staff: List[StaffMember] = Field(default_factory=list, description="Key staff names and current roles/titles")
    included_roles: List[str] = Field(default_factory=list, description="Roles confirmed for inclusion in the matrix")
    pasted_notes: Optional[str] = Field(None, description="Pasted responsibilities lists, org charts or notes")


class RolesMatrixExtractRequest(BaseModel):
    """Step 2: trigger responsibility extraction"""
    custom_instructions: Optional[str] = Field(None, description="Optional extra instructions from the advisor")


class RolesMatrixGenerateRequest(BaseModel):
    """Step 3: build the matrix from the extracted responsibilities"""
    custom_instructions: Optional[str] = Field(None, description="Optional extra instructions from the advisor")


class RolesMatrixUpdateRequest(BaseModel):
    """Step 4: save advisor edits to the matrix"""
    matrix_rows: List[MatrixRow] = Field(..., description="Full replacement set of matrix rows, in display order")


class RolesMatrixStepProgressRequest(BaseModel):
    """Persist which step the advisor is on"""
    current_step: int = Field(..., ge=1, le=4)
    max_step_reached: Optional[int] = Field(None, ge=1, le=4)
