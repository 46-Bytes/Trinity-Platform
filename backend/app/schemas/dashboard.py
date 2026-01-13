from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID

class RecentAIGeneration(BaseModel):
    """Single recent AI generation item."""
    user_name: str
    engagement_name: str
    completed_at: str
    time_ago: str


class DashboardStatsResponse(BaseModel):
    """Response model for dashboard statistics."""
    total_users: int
    total_users_change: str
    total_users_change_type: str
    active_engagements: int
    active_engagements_change: str
    active_engagements_change_type: str
    total_firms: int
    total_firms_change: str
    total_firms_change_type: str
    ai_generations: int
    ai_generations_change: str
    ai_generations_change_type: str
    recent_ai_generations: List[RecentAIGeneration]


class ClientTaskItem(BaseModel):
    """Task information for client dashboard."""
    id: str
    title: str
    status: str
    priority: str
    engagement_name: Optional[str] = None
    created_at: str


class ClientDocumentItem(BaseModel):
    """Document information for client dashboard."""
    id: str
    file_name: str
    file_size: Optional[int] = None
    created_at: str


class ClientDashboardStatsResponse(BaseModel):
    """Response model for client dashboard statistics."""
    total_tasks: int
    total_documents: int
    total_diagnostics: int
    latest_tasks: List[ClientTaskItem]
    recent_documents: List[ClientDocumentItem]


class ActivityDataPoint(BaseModel):
    """Single data point for activity chart."""
    date: str
    users: int
    engagements: int
    firms: int
    ai_generations: int


class ActivityDataResponse(BaseModel):
    """Response model for activity data over time."""
    data: List[ActivityDataPoint]