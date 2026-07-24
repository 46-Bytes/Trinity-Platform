"""
Stripe billing provider - the Feature 8 slot.

Deliberately unimplemented. The method bodies document the exact calls and the
mapping onto our columns, so Feature 8 is a fill-in rather than a redesign.
Nothing else in the codebase needs to change when it lands: the owner journey
talks only to the BillingProvider interface, and every column Stripe needs
(stripe_subscription_id, stripe_customer_id, current_period_start/end,
cancel_at_period_end, cancelled_at) already exists on Subscription.

To finish this:
  1. `pip install stripe` and add it to requirements.txt
  2. Set STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET in .env
  3. Create the products/prices in Stripe and put the price ids into
     catalogue.py (Plan.stripe_price_id)
  4. Set BILLING_PROVIDER=stripe
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from ...config import settings
from ...models.subscription import Subscription
from ...models.user import User
from .base import BillingError, BillingEvent, BillingProvider, CheckoutResult
from .catalogue import Plan

logger = logging.getLogger(__name__)


class StripeBillingProvider(BillingProvider):
    """Stripe Checkout + webhooks. Implemented by Feature 8."""

    name = "stripe"

    def __init__(self):
        if not settings.STRIPE_SECRET_KEY:
            raise BillingError(
                "BILLING_PROVIDER=stripe but STRIPE_SECRET_KEY is not set. "
                "Set it in .env, or use BILLING_PROVIDER=manual."
            )

    def create_checkout(
        self,
        db: Session,
        user: User,
        plan: Plan,
        subscription: Subscription,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutResult:
        # Feature 8:
        #   customer = stripe.Customer.create(email=user.email, name=user.name)
        #   session = stripe.checkout.Session.create(
        #       mode="subscription",
        #       customer=customer.id,
        #       line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
        #       success_url=success_url, cancel_url=cancel_url,
        #       client_reference_id=str(subscription.id),
        #   )
        #   subscription.stripe_customer_id = customer.id
        #   subscription.provider = self.name
        #   return CheckoutResult(redirect_url=session.url, reference=session.id)
        raise NotImplementedError(
            "Stripe checkout is Feature 8. Set BILLING_PROVIDER=manual until it is built."
        )

    def handle_webhook(self, payload: bytes, signature: Optional[str]) -> BillingEvent:
        # Feature 8:
        #   event = stripe.Webhook.construct_event(
        #       payload, signature, settings.STRIPE_WEBHOOK_SECRET)   # raises on bad signature
        # Map:
        #   checkout.session.completed          -> kind="activated"
        #                                          subscription_id = client_reference_id
        #   customer.subscription.updated       -> kind="activated" | "cancelled"
        #   customer.subscription.deleted       -> kind="cancelled"
        #   invoice.payment_failed              -> kind="payment_failed"
        #   everything else                     -> kind="ignored"
        raise NotImplementedError(
            "Stripe webhooks are Feature 8. Set BILLING_PROVIDER=manual until it is built."
        )

    def cancel(self, db: Session, subscription: Subscription, at_period_end: bool = True) -> None:
        # Feature 8:
        #   stripe.Subscription.modify(subscription.stripe_subscription_id,
        #                              cancel_at_period_end=at_period_end)
        # then let the webhook write the local state back.
        raise NotImplementedError(
            "Stripe cancellation is Feature 8. Set BILLING_PROVIDER=manual until it is built."
        )

    def get_portal_url(self, db: Session, subscription: Subscription, return_url: str) -> Optional[str]:
        # Feature 8:
        #   session = stripe.billing_portal.Session.create(
        #       customer=subscription.stripe_customer_id, return_url=return_url)
        #   return session.url
        raise NotImplementedError(
            "The Stripe customer portal is Feature 8. Set BILLING_PROVIDER=manual until it is built."
        )
