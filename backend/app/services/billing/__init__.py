"""
Billing package for the self-service (SaaS) tier.

`get_billing_provider()` is the only entry point application code should use -
which concrete gateway is behind it is a deployment decision
(`BILLING_PROVIDER` in .env), not something the owner journey knows about.
"""
from functools import lru_cache

from ...config import settings
from .base import BillingError, BillingEvent, BillingProvider, CheckoutResult
from .catalogue import (
    CATALOGUE,
    PROGRAM_SALE_READY,
    PROGRAM_VALUE_BUILDER,
    VALID_PROGRAMS,
    Plan,
    get_plan,
    list_plans,
    program_label,
)
from .manual import ManualBillingProvider


@lru_cache(maxsize=1)
def get_billing_provider() -> BillingProvider:
    """
    The billing provider configured for this deployment.

    Cached because constructing the Stripe provider validates credentials.
    """
    if settings.BILLING_PROVIDER == "stripe":
        # Imported lazily so a manual-billing deployment never needs the
        # stripe package installed.
        from .stripe_provider import StripeBillingProvider
        return StripeBillingProvider()
    return ManualBillingProvider()


__all__ = [
    "BillingError",
    "BillingEvent",
    "BillingProvider",
    "CheckoutResult",
    "CATALOGUE",
    "PROGRAM_SALE_READY",
    "PROGRAM_VALUE_BUILDER",
    "VALID_PROGRAMS",
    "Plan",
    "get_billing_provider",
    "get_plan",
    "list_plans",
    "program_label",
]
