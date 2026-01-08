from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from ..models.user import User
from ..models.engagement import Engagement
from ..models.firm import Firm
from ..models.diagnostic import Diagnostic
from ..schemas.dashboard import DashboardStatsResponse, RecentAIGeneration


def calculate_percentage_change(current: int, previous: int) -> tuple[str, str]:
    """
    Calculate percentage change between current and previous values.
    
    Returns:
        tuple: (formatted_change_string, change_type)
    """
    if previous == 0:
        if current > 0:
            return f"+{current}", "positive"
        return "0%", "neutral"
    
    change = ((current - previous) / previous) * 100
    change_type = "positive" if change > 0 else "negative" if change < 0 else "neutral"
    
    # Format with + or - sign and % symbol
    sign = "+" if change > 0 else ""
    return f"{sign}{change:.0f}%", change_type


def format_time_ago(completed_at: datetime) -> str:
    """
    Format datetime as relative time string.
    
    Returns:
        Human-readable relative time (e.g., "5m ago", "1h ago", "2d ago")
    """
    now = datetime.utcnow()
    diff = now - completed_at
    
    # Less than 1 minute
    if diff.total_seconds() < 60:
        return "Just now"
    
    # Less than 1 hour
    minutes = int(diff.total_seconds() / 60)
    if minutes < 60:
        return f"{minutes}m ago"
    
    # Less than 24 hours
    hours = int(diff.total_seconds() / 3600)
    if hours < 24:
        return f"{hours}h ago"
    
    # Less than 7 days
    days = int(diff.total_seconds() / 86400)
    if days < 7:
        return f"{days}d ago"
    
    # Otherwise, use date format
    return completed_at.strftime("%b %d, %Y")


def get_superadmin_dashboard_stats(db: Session) -> DashboardStatsResponse:
    """
    Get dashboard statistics for super admin.
    
    Returns:
        DashboardStatsResponse with all statistics and recent AI generations
    """
    # Get current date and calculate month boundaries
    now = datetime.utcnow()
    current_month_start = datetime(now.year, now.month, 1)
    last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
    last_month_end = current_month_start - timedelta(seconds=1)
    
    # Total Users - Current month
    total_users_current = db.query(func.count(User.id)).filter(
        User.created_at >= current_month_start
    ).scalar() or 0
    
    # Total Users - Last month
    total_users_last = db.query(func.count(User.id)).filter(
        and_(
            User.created_at >= last_month_start,
            User.created_at <= last_month_end
        )
    ).scalar() or 0
    
    # Total Users - All time
    total_users_all = db.query(func.count(User.id)).scalar() or 0
    
    # Active Engagements - Current month
    active_engagements_current = db.query(func.count(Engagement.id)).filter(
        and_(
            Engagement.status == 'active',
            Engagement.created_at >= current_month_start
        )
    ).scalar() or 0
    
    # Active Engagements - Last month
    active_engagements_last = db.query(func.count(Engagement.id)).filter(
        and_(
            Engagement.status == 'active',
            Engagement.created_at >= last_month_start,
            Engagement.created_at <= last_month_end
        )
    ).scalar() or 0
    
    # Active Engagements - All time (current active count)
    active_engagements_all = db.query(func.count(Engagement.id)).filter(
        Engagement.status == 'active'
    ).scalar() or 0
    
    # Total Firms - Current month
    total_firms_current = db.query(func.count(Firm.id)).filter(
        Firm.created_at >= current_month_start
    ).scalar() or 0
    
    # Total Firms - Last month
    total_firms_last = db.query(func.count(Firm.id)).filter(
        and_(
            Firm.created_at >= last_month_start,
            Firm.created_at <= last_month_end
        )
    ).scalar() or 0
    
    # Total Firms - All time
    total_firms_all = db.query(func.count(Firm.id)).scalar() or 0
    
    # AI Generations (Completed Diagnostics) - Current month
    ai_generations_current = db.query(func.count(Diagnostic.id)).filter(
        and_(
            Diagnostic.status == 'completed',
            Diagnostic.created_at >= current_month_start
        )
    ).scalar() or 0
    
    # AI Generations - Last month
    ai_generations_last = db.query(func.count(Diagnostic.id)).filter(
        and_(
            Diagnostic.status == 'completed',
            Diagnostic.created_at >= last_month_start,
            Diagnostic.created_at <= last_month_end
        )
    ).scalar() or 0
    
    # AI Generations - All time (total completed)
    ai_generations_all = db.query(func.count(Diagnostic.id)).filter(
        Diagnostic.status == 'completed'
    ).scalar() or 0
    
    # Query recent completed diagnostics
    recent_diagnostics = db.query(Diagnostic).filter(
        Diagnostic.status == 'completed',
        Diagnostic.completed_at.isnot(None)
    ).order_by(
        Diagnostic.completed_at.desc()
    ).limit(5).all()
    
    # Format recent AI generations
    recent_ai_generations_list = []
    for diagnostic in recent_diagnostics:
        # Get user name - prefer completed_by_user_id, fallback to created_by_user_id
        user_name = "Unknown User"
        user_id = diagnostic.completed_by_user_id or diagnostic.created_by_user_id
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user_name = user.name or user.email or user.nickname or "Unknown User"
        
        # Get engagement name
        engagement_name = "Unknown Engagement"
        if diagnostic.engagement_id:
            engagement = db.query(Engagement).filter(Engagement.id == diagnostic.engagement_id).first()
            if engagement:
                engagement_name = engagement.engagement_name or "Unknown Engagement"
        
        # Format time
        time_ago = format_time_ago(diagnostic.completed_at)
        
        recent_ai_generations_list.append(RecentAIGeneration(
            user_name=user_name,
            engagement_name=engagement_name,
            completed_at=diagnostic.completed_at.isoformat(),
            time_ago=time_ago
        ))
    
    # Calculate percentage changes
    users_change, users_change_type = calculate_percentage_change(
        total_users_current, total_users_last
    )
    engagements_change, engagements_change_type = calculate_percentage_change(
        active_engagements_current, active_engagements_last
    )
    firms_change, firms_change_type = calculate_percentage_change(
        total_firms_current, total_firms_last
    )
    ai_change, ai_change_type = calculate_percentage_change(
        ai_generations_current, ai_generations_last
    )
    
    # Format change strings with "this month" suffix
    users_change_str = f"{users_change} this month"
    engagements_change_str = f"{engagements_change} this month"
    firms_change_str = f"{firms_change} this month"
    ai_change_str = f"{ai_change} this month"
    
    return DashboardStatsResponse(
        total_users=total_users_all,
        total_users_change=users_change_str,
        total_users_change_type=users_change_type,
        active_engagements=active_engagements_all,
        active_engagements_change=engagements_change_str,
        active_engagements_change_type=engagements_change_type,
        total_firms=total_firms_all,
        total_firms_change=firms_change_str,
        total_firms_change_type=firms_change_type,
        ai_generations=ai_generations_all,
        ai_generations_change=ai_change_str,
        ai_generations_change_type=ai_change_type,
        recent_ai_generations=recent_ai_generations_list,
    )