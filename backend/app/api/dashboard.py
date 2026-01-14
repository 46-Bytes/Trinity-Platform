"""
Dashboard API endpoints for super admin and client analytics.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Union

from ..database import get_db
from ..models.user import User, UserRole
from ..services.role_check import get_current_user_from_token
from ..schemas.dashboard import (
    DashboardStatsResponse,
    ClientDashboardStatsResponse,
    FirmAdvisorDashboardStatsResponse,
    ActivityDataResponse,
)
from ..services.dashboard_service import (
    get_superadmin_dashboard_stats as get_dashboard_stats_service,
    get_client_dashboard_stats,
    get_firm_advisor_dashboard_stats
)
from ..services.activity_service import get_superadmin_activity_data

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=Union[DashboardStatsResponse, ClientDashboardStatsResponse, FirmAdvisorDashboardStatsResponse])
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Get dashboard statistics based on user role.
    
    For SUPER_ADMIN:
        Returns:
        - Total Users: Count of all users
        - Active Engagements: Count of engagements with status='active'
        - Total Firms: Count of all firms
        - AI Generations: Count of completed diagnostics
    
    For CLIENT:
        Returns:
        - Total Tasks: Tasks assigned to or created by client
        - Total Documents: Documents uploaded by client
        - Total Diagnostics: Diagnostics from client's engagements
        - Latest Tasks: List of latest tasks
        - Recent Documents: List of recent documents (first 3)
    
    For FIRM_ADVISOR:
        Returns:
        - Active Clients: Count of clients associated with the firm advisor
        - Total Engagements: Engagements where firm_advisor is primary or secondary advisor
        - Total Documents: Documents from firm_advisor's engagements
        - Total Tasks: Tasks assigned to or created by firm_advisor
        - Total Diagnostics: Diagnostics from firm_advisor's engagements
    
    Only accessible to SUPER_ADMIN, CLIENT, or FIRM_ADVISOR roles.
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        return get_dashboard_stats_service(db)
    
    if current_user.role == UserRole.CLIENT:
        return get_client_dashboard_stats(db, current_user.id)
    
    if current_user.role == UserRole.FIRM_ADVISOR:
        return get_firm_advisor_dashboard_stats(db, current_user.id)
    
    # If none of the allowed roles, return 403
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Only super admins, clients, and firm advisors can access dashboard statistics.")


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

