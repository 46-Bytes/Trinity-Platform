"""
Clients an advisor works with: active associations plus engagements where they
are primary or secondary. Adding a secondary advisor creates no association.
"""
from typing import Dict, List, Set
from uuid import UUID

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from ..models.adv_client import AdvisorClient
from ..models.engagement import Engagement
from ..models.user import User, UserRole


def get_advisor_clients(db: Session, advisor_id: UUID) -> List[Dict]:
    """
    Union of active associations and clients of non-deleted engagements where the
    advisor is primary or secondary. Read-only; it grants no engagement access.
    """
    associated_ids: Set[UUID] = {
        row[0]
        for row in db.query(AdvisorClient.client_id).filter(
            AdvisorClient.advisor_id == advisor_id,
            AdvisorClient.status == "active",
            AdvisorClient.is_deleted == False,  # noqa: E712
        ).all()
    }

    engagements = db.query(Engagement.client_id, Engagement.client_ids).filter(
        Engagement.is_deleted == False,  # noqa: E712
        or_(
            Engagement.primary_advisor_id == advisor_id,
            text("secondary_advisor_ids @> ARRAY[:advisor_id]::uuid[]").bindparams(
                advisor_id=advisor_id
            ),
        ),
    ).all()

    # client_ids is the multi-client list; client_id is the older single field.
    engagement_client_ids: Set[UUID] = set()
    for client_id, client_ids in engagements:
        if client_ids:
            engagement_client_ids.update(client_ids)
        if client_id:
            engagement_client_ids.add(client_id)

    all_ids = associated_ids | engagement_client_ids
    if not all_ids:
        return []

    clients = db.query(User).filter(
        User.id.in_(all_ids),
        User.role == UserRole.CLIENT,
        User.is_deleted == False,  # noqa: E712
    ).all()

    result = [
        {
            "client_id": client.id,
            "client_name": client.name,
            "client_email": client.email,
            "is_associated": client.id in associated_ids,
            "via_engagement": client.id in engagement_client_ids,
        }
        for client in clients
    ]
    result.sort(key=lambda c: (c["client_name"] or c["client_email"] or "").lower())
    return result
