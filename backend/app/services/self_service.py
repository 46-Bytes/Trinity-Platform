"""
Self-service (SaaS) provisioning for business owners.

Feature 7. A business owner signs up on the website with no advisor involved,
picks a program, pays, and Trinity provisions their workspace: an advisor-less
engagement plus the M0 diagnostic, using exactly the same machinery advisors
use.

Two deliberate choices worth knowing about:

1. A self-service owner is a `UserRole.CLIENT` with `account_type='self_service'`.
   Their permissions on the engagement surface are identical to an advisory
   client's, so nothing in role_check.py, dashboard.py, the sidebar or the
   engagement views needed a new branch. `account_type` gates only the
   owner-specific extras: checkout, billing and team management.

2. Provisioning does not call `POST /api/engagements`. That endpoint requires an
   advisor and rejects clients, which is correct for the advisor flow. We build
   the engagement here instead, with `primary_advisor_id = None`.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from ..models.diagnostic import Diagnostic
from ..models.engagement import Engagement
from ..models.signup_intent import SignupIntent, SignupIntentStatus
from ..models.subscription import Subscription
from ..models.user import AccountType, User, UserRole
from .billing import get_plan, program_label
from .billing.catalogue import Plan

logger = logging.getLogger(__name__)


class SelfServiceError(Exception):
    """Raised when a self-service operation cannot be completed."""


# ----------------------------------------------------------------------------
# Signup intents
# ----------------------------------------------------------------------------

def create_signup_intent(
    db: Session,
    email: str,
    program: str,
    name: Optional[str] = None,
    business_name: Optional[str] = None,
) -> SignupIntent:
    """
    Park the owner's business details before handing them to Auth0.

    Auth0 Universal Login owns the credential step and will not carry our
    fields through, so they wait here and are matched back by email on
    /api/auth/callback.

    Raises:
        SelfServiceError: if the program is unknown or the email already has an account.
    """
    try:
        plan = get_plan(program)
    except ValueError as exc:
        raise SelfServiceError(str(exc)) from exc

    normalized_email = email.strip().lower()

    existing = db.query(User).filter(
        User.email == normalized_email,
        User.is_deleted == False,  # noqa: E712 - SQLAlchemy column comparison
    ).first()
    if existing:
        # The caller is responsible for not leaking this to an anonymous
        # visitor - see the enumeration-safe response in api/self_service.py.
        raise SelfServiceError("An account already exists for this email address.")

    # Supersede any earlier pending intent for the same address so a stale
    # program choice cannot be applied instead of the current one.
    db.query(SignupIntent).filter(
        SignupIntent.email == normalized_email,
        SignupIntent.status == SignupIntentStatus.PENDING.value,
    ).update({"status": SignupIntentStatus.EXPIRED.value}, synchronize_session=False)

    intent = SignupIntent(
        email=normalized_email,
        name=name,
        business_name=business_name,
        program=program,
        plan_name=plan.plan_name,
        status=SignupIntentStatus.PENDING.value,
        expires_at=SignupIntent.default_expiry(),
    )
    db.add(intent)
    db.commit()
    db.refresh(intent)

    logger.info("Created signup intent %s for %s (program=%s)", intent.id, normalized_email, program)
    return intent


def find_usable_intent(
    db: Session,
    email: str,
    intent_id: Optional[str] = None,
) -> Optional[SignupIntent]:
    """
    Find the pending intent for a signing-up user.

    Matched on email rather than trusting `intent_id` alone, so a leaked intent
    id cannot be redeemed against somebody else's Auth0 account.
    """
    if not email:
        return None

    query = db.query(SignupIntent).filter(
        SignupIntent.email == email.strip().lower(),
        SignupIntent.status == SignupIntentStatus.PENDING.value,
    )
    if intent_id:
        try:
            query = query.filter(SignupIntent.id == UUID(str(intent_id)))
        except (ValueError, AttributeError):
            logger.warning("Ignoring malformed intent id %r", intent_id)

    intent = query.order_by(SignupIntent.created_at.desc()).first()
    if intent and not intent.is_usable:
        intent.status = SignupIntentStatus.EXPIRED.value
        db.commit()
        return None
    return intent


def consume_intent(db: Session, intent: SignupIntent, user: User) -> None:
    """Apply a signup intent to a freshly created user and mark it spent."""
    user.role = UserRole.CLIENT
    user.account_type = AccountType.SELF_SERVICE.value
    if intent.business_name:
        user.business_name = intent.business_name
    if intent.name and not user.name:
        user.name = intent.name

    intent.status = SignupIntentStatus.CONSUMED.value
    intent.consumed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()

    logger.info(
        "Consumed signup intent %s: user %s is now a self-service owner (program=%s)",
        intent.id, user.email, intent.program,
    )


# ----------------------------------------------------------------------------
# Subscriptions
# ----------------------------------------------------------------------------

def get_owner_subscription(db: Session, owner_id: UUID) -> Optional[Subscription]:
    """The owner's most recent subscription, whatever its status."""
    return (
        db.query(Subscription)
        .filter(Subscription.user_id == owner_id)
        .order_by(Subscription.created_at.desc())
        .first()
    )


def get_active_subscription(db: Session, owner_id: UUID) -> Optional[Subscription]:
    """The owner's entitling subscription, or None if they are not paid up."""
    subscription = get_owner_subscription(db, owner_id)
    if subscription and subscription.is_entitled:
        return subscription
    return None


def create_pending_subscription(db: Session, owner: User, plan: Plan, provider_name: str) -> Subscription:
    """
    Create the `pending` subscription row that checkout will activate.

    Reuses an existing pending row for the same program so a bounced checkout
    does not litter the table.
    """
    existing = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == owner.id,
            Subscription.program == plan.program,
            Subscription.status == "pending",
        )
        .first()
    )
    if existing:
        return existing

    subscription = Subscription(
        user_id=owner.id,
        program=plan.program,
        plan_name=plan.plan_name,
        seat_count=plan.seat_count,
        monthly_price=plan.monthly_price,
        status="pending",
        provider=provider_name,
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


# ----------------------------------------------------------------------------
# Provisioning
# ----------------------------------------------------------------------------

def get_owner_engagement(db: Session, owner_id: UUID, program: Optional[str] = None) -> Optional[Engagement]:
    """The owner's self-service engagement for a program (or their most recent one)."""
    query = db.query(Engagement).filter(
        Engagement.client_id == owner_id,
        Engagement.is_deleted == False,  # noqa: E712
    )
    if program:
        query = query.filter(Engagement.tool == program)
    return query.order_by(Engagement.created_at.desc()).first()


async def activate_owner_account(
    db: Session,
    owner: User,
    subscription: Subscription,
) -> Tuple[Engagement, Optional[Diagnostic]]:
    """
    Provision an owner's workspace once their subscription is entitled.

    Creates the advisor-less engagement and its M0 diagnostic. Idempotent: a
    replayed webhook returns the existing workspace rather than a duplicate.

    Returns:
        (engagement, diagnostic) - diagnostic is None only if one somehow
        already existed for a pre-existing engagement.

    Raises:
        SelfServiceError: if provisioning fails. Unlike the advisor path
            (api/engagements.py, which logs and continues), this is fatal - an
            owner who has paid and has no diagnostic has received nothing.
    """
    program = subscription.program
    if not program:
        raise SelfServiceError("Subscription has no program; cannot provision a workspace.")

    existing = get_owner_engagement(db, owner.id, program)
    if existing:
        logger.info("Owner %s already has a %s engagement (%s); skipping provisioning",
                    owner.email, program, existing.id)
        diagnostic = db.query(Diagnostic).filter(Diagnostic.engagement_id == existing.id).first()
        return existing, diagnostic

    label = program_label(program)
    business_name = owner.business_name or owner.name or owner.email

    engagement = Engagement(
        engagement_name=f"{business_name} - {label}",
        business_name=owner.business_name,
        description=f"Self-service {label} program.",
        tool=program,
        status="active",
        client_id=owner.id,
        client_ids=[owner.id],
        # No advisor: this is the whole point of the self-service tier. Feature 9
        # populates this when an owner is upsold to a full BBA engagement.
        primary_advisor_id=None,
        firm_id=None,
        secondary_advisor_ids=[],
    )
    db.add(engagement)
    db.commit()
    db.refresh(engagement)

    # Reuse the advisor path's tool factory so the owner gets exactly the same
    # diagnostic, keyed to the program via Engagement.tool.
    import sys
    from pathlib import Path

    backend_path = Path(__file__).parent.parent.parent
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))

    from tool_service.tool_selector import create_tool_for_engagement

    try:
        diagnostic = await create_tool_for_engagement(
            db=db,
            engagement_id=engagement.id,
            tool_type=program,
            created_by_user_id=owner.id,
        )
        db.commit()
    except Exception as exc:
        # Roll the engagement back so a retry provisions cleanly instead of
        # leaving the owner with an empty workspace.
        logger.exception("Failed to create the diagnostic for owner %s", owner.email)
        db.delete(engagement)
        db.commit()
        raise SelfServiceError(
            "Could not set up your program. Your payment was not affected - please contact support."
        ) from exc

    logger.info(
        "Provisioned self-service workspace for %s: engagement=%s program=%s",
        owner.email, engagement.id, program,
    )
    return engagement, diagnostic


def build_account_summary(db: Session, owner: User) -> dict:
    """
    Everything the owner's frontend needs to decide what to show: are they paid
    up, which program did they buy, where is their workspace, how many seats
    are left.
    """
    from .team_service import count_active_members  # local import avoids a cycle

    subscription = get_owner_subscription(db, owner.id)
    engagement = None
    diagnostic = None

    if subscription and subscription.program:
        engagement = get_owner_engagement(db, owner.id, subscription.program)
    if engagement:
        diagnostic = (
            db.query(Diagnostic)
            .filter(Diagnostic.engagement_id == engagement.id)
            .order_by(Diagnostic.created_at.desc())
            .first()
        )

    seat_count = subscription.seat_count if subscription else 0
    members_used = count_active_members(db, owner.id)

    return {
        "is_self_service": owner.is_self_service,
        "subscription": subscription.to_dict() if subscription else None,
        "program": subscription.program if subscription else None,
        "program_label": program_label(subscription.program) if subscription and subscription.program else None,
        "engagement_id": str(engagement.id) if engagement else None,
        "diagnostic_id": str(diagnostic.id) if diagnostic else None,
        "diagnostic_status": diagnostic.status if diagnostic else None,
        "seats": {
            "total": seat_count,
            # The owner occupies one seat.
            "team_member_limit": max(seat_count - 1, 0),
            "team_members_used": members_used,
        },
    }
