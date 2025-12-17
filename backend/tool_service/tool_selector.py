"""
Tool selector service for creating tools based on tool type.
This service creates the appropriate tool instance for an engagement.
"""
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.engagement import Engagement
from app.services.diagnostic_service import get_diagnostic_service


async def create_tool_for_engagement(
    db: Session,
    engagement_id: UUID,
    tool_type: str,
    created_by_user_id: UUID
) -> Optional[object]:
    """
    Create a tool instance for an engagement based on the tool type.
    
    Args:
        db: Database session
        engagement_id: UUID of the engagement
        tool_type: Type of tool ('diagnostic', 'kpi_builder', etc.)
        created_by_user_id: UUID of the user creating the tool
        
    Returns:
        Created tool instance (Diagnostic, KPIBuilder, etc.) or None if tool type is not supported
        
    Raises:
        ValueError: If engagement not found or tool type is invalid
    """
    # Verify engagement exists
    engagement = db.query(Engagement).filter(
        Engagement.id == engagement_id
    ).first()
    
    if not engagement:
        raise ValueError(f"Engagement {engagement_id} not found")
    
    # Create tool based on type
    if tool_type == 'diagnostic':
        service = get_diagnostic_service(db)
        return await service.create_diagnostic(
            engagement_id=engagement_id,
            created_by_user_id=created_by_user_id
        )
    elif tool_type == 'kpi_builder':
        return _create_kpi_builder(db, engagement_id, created_by_user_id)
    else:
        # Unknown tool type - return None (or raise error if you want strict validation)
        return None


def _create_kpi_builder(
    db: Session,
    engagement_id: UUID,
    created_by_user_id: UUID
) -> dict:
    """
    Create a KPI Builder tool for an engagement.
    
    Note: KPI Builder model doesn't exist yet, so this returns a placeholder.
    When KPI Builder model is created, replace this with actual model creation.
    
    Args:
        db: Database session
        engagement_id: UUID of the engagement
        created_by_user_id: UUID of the user creating the KPI builder
        
    Returns:
        Placeholder dict (replace with actual KPI Builder model when created)
    """
    # TODO: Create KPI Builder model and implement this
    # For now, return a placeholder
    return {
        "tool_type": "kpi_builder",
        "engagement_id": str(engagement_id),
        "created_by_user_id": str(created_by_user_id),
        "status": "draft",
        "message": "KPI Builder tool created (placeholder - model not yet implemented)"
    }

