"""
Dashboard API endpoints for super admin analytics.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.user import User, UserRole
from ..services.role_check import get_current_user_from_token
from ..schemas.dashboard import (
    DashboardStatsResponse,
    ActivityDataResponse,
)
from ..services.dashboard_service import get_superadmin_dashboard_stats as get_dashboard_stats_service
from ..services.activity_service import get_superadmin_activity_data

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Get dashboard statistics for super admin.
    
    Returns:
        - Total Users: Count of all users
        - Active Engagements: Count of engagements with status='active'
        - Total Firms: Count of all firms
        - AI Generations: Count of completed diagnostics
    
    Only accessible to SUPER_ADMIN role.
    """
    # Check if user is super admin
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can access dashboard statistics."
        )
    
    # Call service to get dashboard stats
    return get_dashboard_stats_service(db)


@router.get("/activity", response_model=ActivityDataResponse)
async def get_activity_data(
    days: int = Query(7, ge=1, le=90, description="Number of days to fetch activity for"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Get platform activity data over time for super admin.
    
    Returns daily counts of:
    - New users
    - New engagements
    - New firms
    - Completed AI generations (diagnostics)
    
    Only accessible to SUPER_ADMIN role.
    """
    # Check if user is super admin
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can access activity data."
        )
    
    # Call service to get activity data
    return get_superadmin_activity_data(db, days)

