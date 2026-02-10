from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, text, distinct
from uuid import UUID

from ..models.user import User
from ..models.engagement import Engagement
from ..models.firm import Firm
from ..models.diagnostic import Diagnostic
from ..models.task import Task
from ..models.media import Media, diagnostic_media
from ..models.adv_client import AdvisorClient
from ..schemas.dashboard import (
    DashboardStatsResponse, 
    RecentAIGeneration,
    ClientDashboardStatsResponse,
    ClientTaskItem,
    ClientDocumentItem,
    FirmAdvisorDashboardStatsResponse
)


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
    
    # Active Engagements - Current month (exclude soft-deleted)
    active_engagements_current = db.query(func.count(Engagement.id)).filter(
        and_(
            Engagement.status == 'active',
            Engagement.is_deleted.is_(False),
            Engagement.created_at >= current_month_start
        )
    ).scalar() or 0
    
    # Active Engagements - Last month (exclude soft-deleted)
    active_engagements_last = db.query(func.count(Engagement.id)).filter(
        and_(
            Engagement.status == 'active',
            Engagement.is_deleted.is_(False),
            Engagement.created_at >= last_month_start,
            Engagement.created_at <= last_month_end
        )
    ).scalar() or 0
    
    # Active Engagements - All time (current active count, exclude soft-deleted)
    active_engagements_all = db.query(func.count(Engagement.id)).filter(
        Engagement.status == 'active',
        Engagement.is_deleted.is_(False)
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


def get_client_dashboard_stats(db: Session, client_user_id: UUID) -> ClientDashboardStatsResponse:
    """
    Get dashboard statistics for a client user.
    
    Returns:
        ClientDashboardStatsResponse with:
        - Total tasks (assigned to or created by client, in their engagements)
        - Total documents (uploaded by client)
        - Total diagnostics (from client's engagements)
        - Latest tasks list
        - Recent documents list (first 3)
    """
    # Get all engagements where client is the client_id
    client_engagements = db.query(Engagement).filter(
        Engagement.client_id == client_user_id
    ).all()
    engagement_ids = [e.id for e in client_engagements]
    
    # If no engagements, return empty stats
    if not engagement_ids:
        return ClientDashboardStatsResponse(total_tasks=0,total_documents=0,total_diagnostics=0,latest_tasks=[],recent_documents=[])
    
    tasks_query = db.query(Task).filter(
        Task.engagement_id.in_(engagement_ids),
        or_(
            Task.assigned_to_user_id == client_user_id,
            Task.created_by_user_id == client_user_id
        )
    )
    
    total_tasks = tasks_query.count()
    
    # Get latest tasks (ordered by created_at desc, limit 20)
    latest_tasks_query = tasks_query.order_by(Task.created_at.desc()).limit(20).all()
    
    # Format latest tasks
    latest_tasks_list = []
    for task in latest_tasks_query:
        # Get engagement name
        engagement_name = None
        if task.engagement_id:
            engagement = db.query(Engagement).filter(Engagement.id == task.engagement_id).first()
            if engagement:
                engagement_name = engagement.engagement_name
        
        latest_tasks_list.append(ClientTaskItem(id=str(task.id), title=task.title, status=task.status, priority=task.priority,engagement_name=engagement_name,created_at=task.created_at.isoformat() if task.created_at else ""))
    
    # Get documents uploaded by client (exclude soft-deleted)
    documents_query = db.query(Media).filter(
        Media.user_id == client_user_id,
        Media.deleted_at.is_(None)
    )
    
    total_documents = documents_query.count()
    
    # Get recent documents (ordered by created_at desc, limit 3)
    recent_documents_query = documents_query.order_by(Media.created_at.desc()).limit(3).all()
    
    # Format recent documents
    recent_documents_list = []
    for document in recent_documents_query:
        recent_documents_list.append(ClientDocumentItem(
            id=str(document.id),
            file_name=document.file_name,
            file_size=document.file_size,
            created_at=document.created_at.isoformat() if document.created_at else ""
        ))
    
    # Get diagnostics from client's engagements
    total_diagnostics = db.query(Diagnostic).filter(
        Diagnostic.engagement_id.in_(engagement_ids)
    ).count()
    
    return ClientDashboardStatsResponse(
        total_tasks=total_tasks,
        total_documents=total_documents,
        total_diagnostics=total_diagnostics,
        latest_tasks=latest_tasks_list,
        recent_documents=recent_documents_list
    )


def get_firm_advisor_dashboard_stats(db: Session, firm_advisor_user_id: UUID) -> FirmAdvisorDashboardStatsResponse:
    """
    Get dashboard statistics for a firm advisor user.
    
    Returns:
        FirmAdvisorDashboardStatsResponse with:
        - Active Clients: Count of clients associated with the firm advisor (through advisor_client table)
        - Total Engagements: Engagements where firm_advisor is primary or secondary advisor
        - Total Documents: Documents from firm_advisor's engagements
        - Total Tasks: Tasks assigned to or created by firm_advisor
        - Total Diagnostics: Diagnostics from firm_advisor's engagements
    """
    # Get active clients associated with this firm advisor through advisor_client table
    associations = db.query(AdvisorClient).filter(
        AdvisorClient.advisor_id == firm_advisor_user_id,
        AdvisorClient.status == 'active'
    ).all()
    
    active_clients = len(associations)
    
    # Get engagements where firm_advisor is primary or secondary advisor
    # Also filter by firm_id to ensure we only get engagements from the same firm
    firm_advisor = db.query(User).filter(User.id == firm_advisor_user_id).first()
    firm_id = firm_advisor.firm_id if firm_advisor else None
    
    # Get engagements where advisor is primary advisor
    primary_engagements = db.query(Engagement).filter(
        Engagement.primary_advisor_id == firm_advisor_user_id
    )
    
    # Get engagements where advisor is in secondary_advisor_ids array
    # Using PostgreSQL array contains operator
    secondary_engagements = db.query(Engagement).filter(
        text("secondary_advisor_ids @> ARRAY[:advisor_id]::uuid[]").params(advisor_id=firm_advisor_user_id)
    )
    
    # Combine both queries
    all_engagement_ids = set()
    for eng in primary_engagements.all():
        all_engagement_ids.add(eng.id)
    for eng in secondary_engagements.all():
        all_engagement_ids.add(eng.id)
    
    engagement_ids = list(all_engagement_ids)
    total_engagements = len(engagement_ids)
    
    # Get total documents from engagements (media linked to diagnostics in these engagements)
    total_documents = 0
    if engagement_ids:
        # Get diagnostics from these engagements
        diagnostic_ids = db.query(Diagnostic.id).filter(
            Diagnostic.engagement_id.in_(engagement_ids)
        ).all()
        diagnostic_id_list = [d[0] for d in diagnostic_ids]
        
        if diagnostic_id_list:
            # Count media linked to these diagnostics
            total_documents = db.query(func.count(distinct(Media.id))).join(
                diagnostic_media, Media.id == diagnostic_media.c.media_id
            ).filter(
                diagnostic_media.c.diagnostic_id.in_(diagnostic_id_list),
                Media.deleted_at.is_(None)
            ).scalar() or 0
    
    # Get total tasks assigned to or created by firm_advisor in their engagements
    total_tasks = 0
    if engagement_ids:
        total_tasks = db.query(func.count(Task.id)).filter(
            Task.engagement_id.in_(engagement_ids),
            or_(
                Task.assigned_to_user_id == firm_advisor_user_id,
                Task.created_by_user_id == firm_advisor_user_id
            )
        ).scalar() or 0
    
    # Get total diagnostics from firm_advisor's engagements
    total_diagnostics = 0
    if engagement_ids:
        total_diagnostics = db.query(func.count(Diagnostic.id)).filter(
            Diagnostic.engagement_id.in_(engagement_ids)
        ).scalar() or 0
    
    return FirmAdvisorDashboardStatsResponse(
        active_clients=active_clients,
        total_engagements=total_engagements,
        total_documents=total_documents,
        total_tasks=total_tasks,
        total_diagnostics=total_diagnostics
    )