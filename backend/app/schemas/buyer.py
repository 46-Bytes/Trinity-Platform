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
    status: str = Field(..., description="'active' or 'revoked'")
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


class BuyerFolderView(BaseModel):
    category_code: str
    sub_item_code: str
    documents: List[BuyerDocument] = Field(default_factory=list)
