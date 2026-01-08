from pydantic import BaseModel
from typing import List

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