"""
Billing provider port.

Feature 7 (self-service signup) needs a payment gate, but Feature 8 (the actual
Stripe integration) is a separate piece of work. This interface is the seam
between them: the owner journey talks only to `BillingProvider`, so Feature 8
can drop in `StripeBillingProvider` without touching signup, provisioning or
the frontend.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from ...models.subscription import Subscription
from ...models.user import User
from .catalogue import Plan


@dataclass
class CheckoutResult:
    """Where to send the owner to pay, and how we recognise them coming back."""
    # URL the browser should be sent to. For the manual provider this is an
    # internal confirmation URL; for Stripe it is the Checkout Session URL.
    redirect_url: str
    # Provider-side reference (Stripe Checkout Session id, or the subscription
    # id for the manual provider).
    reference: str
    # True when the provider activated the subscription synchronously and no
    # webhook will follow (the manual provider).
    activated_immediately: bool = False


@dataclass
class BillingEvent:
    """A normalised billing notification, whatever the provider called it."""
    # One of: activated, cancelled, payment_failed, ignored
    kind: str
    subscription_id: Optional[str] = None
    provider_subscription_id: Optional[str] = None
    provider_customer_id: Optional[str] = None
    current_period_start: Optional[str] = None
    current_period_end: Optional[str] = None
    raw: dict = field(default_factory=dict)

    @property
    def is_actionable(self) -> bool:
        return self.kind != "ignored"


class BillingError(Exception):
    """Raised when a billing provider rejects a request or a webhook is invalid."""


class BillingProvider(ABC):
    """Payment gateway abstraction for the self-service tier."""

    #: Stored on Subscription.provider so a row can be traced back to its gateway.
    name: str = "base"

    @abstractmethod
    def create_checkout(
        self,
        db: Session,
        user: User,
        plan: Plan,
        subscription: Subscription,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutResult:
        """
        Begin payment for `plan`.

        `subscription` is an already-persisted row in `pending` status; the
        provider should attach its own identifiers to it and leave activation
        to `handle_webhook` (unless it activates immediately, in which case it
        must say so via CheckoutResult.activated_immediately).
        """

    @abstractmethod
    def handle_webhook(self, payload: bytes, signature: Optional[str]) -> BillingEvent:
        """
        Verify and normalise an inbound provider notification.

        Raises:
            BillingError: if the signature is missing or invalid.
        """

    @abstractmethod
    def cancel(self, db: Session, subscription: Subscription, at_period_end: bool = True) -> None:
        """Cancel a subscription, immediately or at the end of the paid period."""

    @abstractmethod
    def get_portal_url(self, db: Session, subscription: Subscription, return_url: str) -> Optional[str]:
        """
        URL where the subscriber manages their own billing.

        Returns None when the provider has no such portal.
        """
