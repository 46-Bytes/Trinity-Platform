"""
Self-service plan catalogue.

Pricing, plan names and feature limits for the self-service tier are TBC in the
Feature 7 brief. This module is the single place they get set once confirmed -
nothing else in the codebase should hardcode a price, a plan name or a seat cap.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional


# Program identifiers. These are written to `Engagement.tool`, which already
# drives scoring maps, prompt selection, module codes and report titles
# (see app/utils/file_loader.py and app/services/scoring_service.py).
PROGRAM_VALUE_BUILDER = "value_builder"
PROGRAM_SALE_READY = "sale_ready"

VALID_PROGRAMS = (PROGRAM_VALUE_BUILDER, PROGRAM_SALE_READY)


@dataclass(frozen=True)
class Plan:
    """One purchasable self-service plan. One plan = one program = one engagement."""
    program: str
    plan_name: str
    label: str
    description: str
    monthly_price: float
    currency: str
    # Total seats including the owner. seat_count - 1 = invitable team members.
    seat_count: int
    features: List[str]
    # Provider-side price identifier, populated when Feature 8 wires up Stripe.
    stripe_price_id: Optional[str] = None

    @property
    def team_member_limit(self) -> int:
        """How many team members the owner may invite (owner occupies one seat)."""
        return max(self.seat_count - 1, 0)

    def to_dict(self) -> dict:
        return {
            "program": self.program,
            "plan_name": self.plan_name,
            "label": self.label,
            "description": self.description,
            "monthly_price": self.monthly_price,
            "currency": self.currency,
            "seat_count": self.seat_count,
            "team_member_limit": self.team_member_limit,
            "features": self.features,
        }


# TBC with the client: pricing, plan names, currency and seat caps.
# Seat count of 4 = the owner plus the proposed default of 3 team members.
CATALOGUE: Dict[str, Plan] = {
    PROGRAM_VALUE_BUILDER: Plan(
        program=PROGRAM_VALUE_BUILDER,
        plan_name="value_builder_self_service",
        label="Value Builder",
        description=(
            "Module-based program to systematically build the value of your business. "
            "Includes the Value Builder diagnostic, your AI-generated report and a "
            "recommended module path."
        ),
        monthly_price=0.0,  # TBC
        currency="AUD",
        seat_count=4,
        features=[
            "Value Builder diagnostic and AI report",
            "Recommended starting module and path",
            "Module guide with AI tools",
            "Task management and document storage",
            "Value dashboard",
        ],
    ),
    PROGRAM_SALE_READY: Plan(
        program=PROGRAM_SALE_READY,
        plan_name="sale_ready_self_service",
        label="Sale Ready",
        description=(
            "Get your business ready for sale. Includes the Sale Ready diagnostic, "
            "your AI-generated report and program management across the M1-M8 modules."
        ),
        monthly_price=0.0,  # TBC
        currency="AUD",
        seat_count=4,
        features=[
            "Sale Ready diagnostic and AI report",
            "Sale Ready program management",
            "AI tools for each module",
            "Task management and document storage",
            "Value dashboard",
        ],
    ),
}


def get_plan(program: str) -> Plan:
    """
    Look up the plan for a program.

    Raises:
        ValueError: if the program is not in the catalogue.
    """
    plan = CATALOGUE.get(program)
    if plan is None:
        raise ValueError(
            f"Unknown program '{program}'. Must be one of {sorted(CATALOGUE)}."
        )
    return plan


def list_plans() -> List[Plan]:
    """All purchasable plans, in display order."""
    return [CATALOGUE[program] for program in VALID_PROGRAMS]


def program_label(program: str) -> str:
    """Human-readable program name, e.g. for engagement titles. Falls back gracefully."""
    plan = CATALOGUE.get(program)
    if plan:
        return plan.label
    return program.replace("_", " ").title()
