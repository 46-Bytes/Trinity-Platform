"""
Self-service (SaaS) API for business owners.

Feature 7: a business owner signs up directly, picks a program, pays, and gets
their diagnostic - no advisor in the loop.

Route map:
    GET  /api/self-service/programs        public   plan catalogue
    POST /api/self-service/signup-intent   public   park details, hand off to Auth0
    POST /api/self-service/checkout        owner    start payment
    POST /api/self-service/billing/webhook public   provider notification
    GET  /api/self-service/account         owner    subscription + workspace state
    POST /api/self-service/billing/portal  owner    manage billing
    POST /api/self-service/billing/cancel  owner    cancel
    GET  /api/self-service/team            owner    list team members
    POST /api/self-service/team/invite     owner    invite a team member
    PATCH/DELETE /team/{member_id}         owner    change access / revoke
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models.subscription import Subscription
from ..models.user import User
from ..schemas.self_service import (
    AccountResponse,
    CancelSubscriptionRequest,
    CheckoutCreate,
    CheckoutResponse,
    PlanResponse,
    ProgramsResponse,
    SignupIntentCreate,
    SignupIntentResponse,
    TeamListResponse,
    TeamMemberInvite,
    TeamMemberResponse,
    TeamMemberUpdate,
)
from ..services import self_service as self_service_service
from ..services import team_service
from ..services.billing import BillingError, get_billing_provider, get_plan, list_plans
from ..services.self_service import SelfServiceError
from ..services.team_service import TeamError
from ..utils.auth import get_current_user, require_self_service_owner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/self-service", tags=["self-service"])


def _frontend_url(path: str) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}{path}"


# ============================================================================
# Public: catalogue and signup
# ============================================================================

@router.get("/programs", response_model=ProgramsResponse)
async def get_programs():
    """The self-service plan catalogue. Public - this drives the signup page."""
    return ProgramsResponse(
        plans=[PlanResponse(**plan.to_dict()) for plan in list_plans()],
        signup_enabled=settings.SELF_SERVICE_SIGNUP_ENABLED,
    )


@router.post("/signup-intent", response_model=SignupIntentResponse)
async def create_signup_intent(payload: SignupIntentCreate, db: Session = Depends(get_db)):
    """
    Start a self-service signup.

    Parks the owner's business details and returns the Auth0 signup URL. The
    details are matched back by email on /api/auth/callback, which is what stops
    a public signup falling through to the ADVISOR default.

    Deliberately does not reveal whether an email is already registered - an
    existing account gets a login redirect and the `already_registered` flag,
    which is the same response an attacker would get for any address.
    """
    if not settings.SELF_SERVICE_SIGNUP_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-service signup is not currently open.",
        )

    try:
        intent = self_service_service.create_signup_intent(
            db=db,
            email=payload.email,
            program=payload.program,
            name=payload.name,
            business_name=payload.business_name,
        )
    except SelfServiceError as exc:
        message = str(exc)
        if "already exists" in message:
            # Enumeration-safe: send them to login rather than confirming the
            # address is registered with an error.
            return SignupIntentResponse(
                intent_id=None,
                redirect_url="/api/auth/login?force_login=true",
                already_registered=True,
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    return SignupIntentResponse(
        intent_id=intent.id,
        redirect_url=f"/api/auth/login?screen_hint=signup&intent={intent.id}",
        already_registered=False,
    )


# ============================================================================
# Billing
# ============================================================================

@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    payload: CheckoutCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_self_service_owner),
):
    """
    Start payment for a program.

    With BILLING_PROVIDER=manual the subscription activates immediately and the
    workspace is provisioned inline, so the owner lands on their diagnostic.
    With Stripe (Feature 8) the owner is redirected to Checkout and the webhook
    does the provisioning.
    """
    try:
        plan = get_plan(payload.program)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    existing = self_service_service.get_active_subscription(db, current_user.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"You already have an active {existing.program} subscription.",
        )

    provider = get_billing_provider()
    subscription = self_service_service.create_pending_subscription(
        db, current_user, plan, provider.name
    )

    try:
        result = provider.create_checkout(
            db=db,
            user=current_user,
            plan=plan,
            subscription=subscription,
            success_url=_frontend_url("/onboarding/complete"),
            cancel_url=_frontend_url("/onboarding/checkout?cancelled=1"),
        )
        db.commit()
    except (BillingError, NotImplementedError) as exc:
        db.rollback()
        logger.error("Checkout failed for %s: %s", current_user.email, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    engagement_id = None
    if result.activated_immediately:
        # No webhook is coming - provision now.
        try:
            engagement, _ = await self_service_service.activate_owner_account(
                db, current_user, subscription
            )
            team_service.sync_team_to_engagement(db, current_user.id, engagement)
            engagement_id = engagement.id
        except SelfServiceError as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    return CheckoutResponse(
        redirect_url=result.redirect_url,
        subscription_id=subscription.id,
        activated_immediately=result.activated_immediately,
        engagement_id=engagement_id,
    )


@router.post("/billing/webhook", status_code=status.HTTP_200_OK)
async def billing_webhook(
    request: Request,
    db: Session = Depends(get_db),
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature"),
):
    """
    Handle a billing provider notification.

    Public by necessity; authenticity comes from the provider's signature,
    verified inside the provider implementation.
    """
    payload = await request.body()
    provider = get_billing_provider()

    try:
        event = provider.handle_webhook(payload, stripe_signature)
    except (BillingError, NotImplementedError) as exc:
        logger.warning("Rejected billing webhook: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook.")

    if not event.is_actionable:
        return {"status": "ignored"}

    subscription = None
    if event.subscription_id:
        subscription = db.query(Subscription).filter(
            Subscription.id == event.subscription_id
        ).first()
    if not subscription and event.provider_subscription_id:
        subscription = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == event.provider_subscription_id
        ).first()

    if not subscription:
        logger.warning("Billing webhook referenced an unknown subscription: %s", event)
        return {"status": "unknown_subscription"}

    if event.kind == "activated":
        subscription.status = "active"
        if event.provider_subscription_id:
            subscription.stripe_subscription_id = event.provider_subscription_id
        if event.provider_customer_id:
            subscription.stripe_customer_id = event.provider_customer_id
        db.commit()

        owner = db.query(User).filter(User.id == subscription.user_id).first()
        if owner:
            try:
                engagement, _ = await self_service_service.activate_owner_account(
                    db, owner, subscription
                )
                team_service.sync_team_to_engagement(db, owner.id, engagement)
            except SelfServiceError as exc:
                # Return 500 so the provider retries rather than marking the
                # webhook delivered while the owner has no workspace.
                logger.error("Provisioning failed after payment for %s: %s", owner.email, exc)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Provisioning failed.",
                )

    elif event.kind == "cancelled":
        subscription.status = "cancelled"
        db.commit()

    elif event.kind == "payment_failed":
        subscription.status = "past_due"
        db.commit()

    return {"status": "processed"}


@router.post("/billing/portal")
async def billing_portal(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_self_service_owner),
):
    """URL where the owner manages their own billing, if the provider has one."""
    subscription = self_service_service.get_owner_subscription(db, current_user.id)
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No subscription found.")

    provider = get_billing_provider()
    try:
        url = provider.get_portal_url(db, subscription, _frontend_url("/dashboard/billing"))
    except (BillingError, NotImplementedError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    if not url:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Your billing provider does not offer a self-service portal.",
        )
    return {"redirect_url": url}


@router.post("/billing/cancel", response_model=AccountResponse)
async def cancel_subscription(
    payload: CancelSubscriptionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_self_service_owner),
):
    """Cancel the owner's subscription."""
    subscription = self_service_service.get_owner_subscription(db, current_user.id)
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No subscription found.")

    provider = get_billing_provider()
    try:
        provider.cancel(db, subscription, at_period_end=payload.at_period_end)
        db.commit()
    except (BillingError, NotImplementedError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return self_service_service.build_account_summary(db, current_user)


# ============================================================================
# Account
# ============================================================================

@router.get("/account", response_model=AccountResponse)
async def get_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_self_service_owner),
):
    """
    Subscription, program and workspace state for the signed-in owner.

    The frontend polls this after checkout to know when provisioning has
    finished and where to send the owner.
    """
    return self_service_service.build_account_summary(db, current_user)


# ============================================================================
# Team members
# ============================================================================

@router.get("/team", response_model=TeamListResponse)
async def list_team(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_self_service_owner),
):
    """The owner's team and their seat usage."""
    summary = self_service_service.build_account_summary(db, current_user)
    return TeamListResponse(
        members=[TeamMemberResponse(**m) for m in team_service.list_members(db, current_user.id)],
        seats=summary["seats"],
    )


@router.post("/team/invite", response_model=TeamMemberResponse, status_code=status.HTTP_201_CREATED)
async def invite_team_member(
    payload: TeamMemberInvite,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_self_service_owner),
):
    """
    Invite a team member.

    Creates their Auth0 account, emails a password setup link, and adds them to
    the owner's engagements.
    """
    try:
        team_service.invite_team_member(
            db=db,
            owner=current_user,
            email=payload.email,
            name=payload.name,
            access_level=payload.access_level,
        )
    except TeamError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    members = team_service.list_members(db, current_user.id)
    return TeamMemberResponse(**members[0])


@router.patch("/team/{member_id}", response_model=TeamMemberResponse)
async def update_team_member(
    member_id: UUID,
    payload: TeamMemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_self_service_owner),
):
    """Change a team member's access level."""
    try:
        team_service.update_access_level(db, current_user, member_id, payload.access_level)
    except TeamError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    for member in team_service.list_members(db, current_user.id):
        if member["id"] == str(member_id):
            return TeamMemberResponse(**member)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team member not found.")


@router.delete("/team/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_team_member(
    member_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_self_service_owner),
):
    """Remove a team member and free their seat."""
    try:
        team_service.revoke_member(db, current_user, member_id)
    except TeamError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return None
