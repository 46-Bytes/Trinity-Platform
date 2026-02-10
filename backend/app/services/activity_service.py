from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date

from ..models.user import User
from ..models.engagement import Engagement
from ..models.firm import Firm
from ..models.diagnostic import Diagnostic
from ..schemas.dashboard import ActivityDataResponse, ActivityDataPoint


def get_superadmin_activity_data(db: Session, days: int) -> ActivityDataResponse:
    """
    Get platform activity data over time for super admin.
    
    Args:
        db: Database session
        days: Number of days to fetch activity for (1-90)
    
    Returns:
        ActivityDataResponse with daily counts of:
        - New users
        - New engagements
        - New firms
        - Completed AI generations (diagnostics)
    """
    # Calculate date range
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days - 1)
    
    # Generate all dates in range (to ensure we have entries for all days)
    date_list = []
    current_date = start_date
    while current_date <= end_date:
        date_list.append(current_date)
        current_date += timedelta(days=1)
    
    # Query users by date
    users_by_date = db.query(
        cast(User.created_at, Date).label('date'),
        func.count(User.id).label('count')
    ).filter(
        cast(User.created_at, Date) >= start_date,
        cast(User.created_at, Date) <= end_date
    ).group_by(
        cast(User.created_at, Date)
    ).all()
    
    # Query engagements by date 
    engagements_by_date = db.query(
        cast(Engagement.created_at, Date).label('date'),
        func.count(Engagement.id).label('count')
    ).filter(
        cast(Engagement.created_at, Date) >= start_date,
        cast(Engagement.created_at, Date) <= end_date,
        Engagement.is_deleted.is_(False)
    ).group_by(
        cast(Engagement.created_at, Date)
    ).all()
    
    # Query firms by date
    firms_by_date = db.query(
        cast(Firm.created_at, Date).label('date'),
        func.count(Firm.id).label('count')
    ).filter(
        cast(Firm.created_at, Date) >= start_date,
        cast(Firm.created_at, Date) <= end_date
    ).group_by(
        cast(Firm.created_at, Date)
    ).all()
    
    # Query AI generations (completed diagnostics) by date
    ai_by_date = db.query(
        cast(Diagnostic.completed_at, Date).label('date'),
        func.count(Diagnostic.id).label('count')
    ).filter(
        Diagnostic.status == 'completed',
        Diagnostic.completed_at.isnot(None),
        cast(Diagnostic.completed_at, Date) >= start_date,
        cast(Diagnostic.completed_at, Date) <= end_date
    ).group_by(
        cast(Diagnostic.completed_at, Date)
    ).all()
    
    # Convert query results to dictionaries for easy lookup
    users_dict = {row.date.isoformat(): row.count for row in users_by_date}
    engagements_dict = {row.date.isoformat(): row.count for row in engagements_by_date}
    firms_dict = {row.date.isoformat(): row.count for row in firms_by_date}
    ai_dict = {row.date.isoformat(): row.count for row in ai_by_date}
    
    # Build response data
    data_points = []
    for date in date_list:
        date_str = date.isoformat()
        data_points.append(ActivityDataPoint(
            date=date_str,
            users=users_dict.get(date_str, 0),
            engagements=engagements_dict.get(date_str, 0),
            firms=firms_dict.get(date_str, 0),
            ai_generations=ai_dict.get(date_str, 0)
        ))
    
    return ActivityDataResponse(data=data_points)


