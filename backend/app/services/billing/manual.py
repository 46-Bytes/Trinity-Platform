"""
Manual billing provider.

Activates a subscription immediately without taking payment. This is what makes
the whole Feature 7 owner journey - signup, program selection, activation,
diagnostic, report - runnable and testable before Feature 8 wires up Stripe.

Not for production use with real customers: it grants entitlement for free.
`SELF_SERVICE_SIGNUP_ENABLED` and the deploy config are what keep it out of
customers' hands.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from ...models.subscription import Subscription
from ...models.user import User
from .base import BillingEvent, BillingProvider, CheckoutResult
from .catalogue import Plan

logger = logging.getLogger(__name__)

# Length of a billing period for a manually activated subscription.
MANUAL_PERIOD = timedelta(days=30)


class ManualBillingProvider(BillingProvider):
    """Activates subscriptions on the spot, no payment gateway involved."""

    name = "manual"

    def create_checkout(
        self,
        db: Session,
        user: User,
        plan: Plan,
        subscription: Subscription,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutResult:
        """Mark the subscription active and send the owner straight to the success URL."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        subscription.status = "active"
        subscription.provider = self.name
        subscription.current_period_start = now
        subscription.current_period_end = now + MANUAL_PERIOD
        subscription.cancel_at_period_end = False
        db.flush()

        logger.info(
            "Manual billing: activated subscription %s (plan=%s) for user %s without payment",
            subscription.id, plan.plan_name, user.email,
        )

        return CheckoutResult(
            redirect_url=success_url,
            reference=str(subscription.id),
            activated_immediately=True,
        )

    def handle_webhook(self, payload: bytes, signature: Optional[str]) -> BillingEvent:
        """The manual provider never emits webhooks; anything arriving here is ignored."""
        logger.warning("Manual billing: received an unexpected webhook, ignoring")
        return BillingEvent(kind="ignored")

    def cancel(self, db: Session, subscription: Subscription, at_period_end: bool = True) -> None:
        """Cancel locally; there is no gateway to notify."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if at_period_end:
            subscription.cancel_at_period_end = True
        else:
            subscription.status = "cancelled"
            subscription.cancelled_at = now
        db.flush()

    def get_portal_url(self, db: Session, subscription: Subscription, return_url: str) -> Optional[str]:
        """No self-serve portal without a payment gateway."""
        return None
