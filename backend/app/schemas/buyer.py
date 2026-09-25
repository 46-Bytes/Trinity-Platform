"""Buyer access request and response models."""
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ----------------------------------------------------------------------
# Advisor-facing
# ----------------------------------------------------------------------
class BuyerInvite(BaseModel):
    email: EmailStr
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    # Recorded only; the NDA is handled outside Trinity and does not gate access.
    nda_signed_date: Optional[date] = None


class BuyerUpdate(BaseModel):
    nda_signed_date: Optional[date] = None


class BuyerView(BaseModel):
    id: UUID
    engagement_id: UUID
    user_id: UUID
    email: Optional[str] = None
    name: Optional[str] = None
    status: str = Field(..., description="'active' or 'revoked'; the stored value")
    display_status: str = Field(
        "active",
        description="'active', 'invited' or 'revoked'. Derived for display: an active "
                    "buyer who has never opened the data room reads as 'invited'.",
    )
    last_access_at: Optional[datetime] = Field(
        None, description="Most recent access of any kind, from the access log")
    open_count: int = Field(
        0, description="Documents viewed or downloaded; folder listings do not count")
    nda_signed_date: Optional[date] = None
    invited_by_user_id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ReleasedFolder(BaseModel):
    category_code: str = Field(..., max_length=10)
    sub_item_code: str = Field(..., max_length=10)


class ReleasedFolderView(ReleasedFolder):
    released_at: Optional[datetime] = None
    released_by_user_id: Optional[UUID] = None


class ReleasedFolderUpdate(BaseModel):
    """The full released set. Folders left out are withdrawn."""
    folders: List[ReleasedFolder] = Field(default_factory=list)


class AccessLogEntry(BaseModel):
    id: UUID
    user_id: UUID
    media_id: Optional[UUID] = None
    action: str
    detail: Optional[str] = None
    created_at: Optional[datetime] = None


# ----------------------------------------------------------------------
# Buyer-facing
# ----------------------------------------------------------------------
class BuyerEngagementView(BaseModel):
    """
    The one engagement this buyer may see. Deliberately thin - a buyer gets the
    name of the business and nothing else about the sale.
    """
    engagement_id: UUID
    engagement_name: Optional[str] = None
    business_name: Optional[str] = None
    nda_signed_date: Optional[date] = None
    released_folder_count: int = 0


class BuyerDocument(BaseModel):
    id: UUID
    file_name: str
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    created_at: Optional[datetime] = None


class BuyerFolder(BaseModel):
    """
    A released folder as the buyer sees it.

    Deliberately narrower than ReleasedFolderView, which is the advisor's: no
    released_at and no released_by_user_id, because when a folder was released
    and by whom is the advisor's business, not the buyer's. The names come from
    the engagement's own due diligence items, so a buyer reads
    "3.1 Historical Financial Statements" rather than a bare code.
    """
    category_code: str
    category: Optional[str] = None
    sub_item_code: str
    sub_item: Optional[str] = None


class BuyerFolderView(BuyerFolder):
    documents: List[BuyerDocument] = Field(default_factory=list)
