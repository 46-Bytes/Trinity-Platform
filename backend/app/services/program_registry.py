"""
The advisory programs the Program Guide serves.

One place decides which `Engagement.tool` values are module-based programs, so
adding the next one is a single edit rather than a hunt through guards. Both the
Program Guide and the deliverables subsystem read from here.

Deliberately free of FastAPI and SQLAlchemy imports. `deliverable_permissions`
depends on FastAPI and services must not, which is why that module previously
duplicated its program constant instead of importing it; a plain constants
module is importable from either side without carrying a dependency across.

A program type listed here is one the *framework* supports. It says nothing
about whether content has been authored for it - an engagement whose program has
no seeded module cards is a valid, empty guide rather than an error.
"""
from typing import Dict, FrozenSet, Optional

PROGRAM_VALUE_BUILDER = "value_builder"
PROGRAM_SALE_READY = "sale_ready"

# Matches Engagement.tool. The scoring taxonomy for each lives in
# ScoringService.get_modules(), which is keyed by the same strings.
SUPPORTED_PROGRAM_TYPES: FrozenSet[str] = frozenset({
    PROGRAM_VALUE_BUILDER,
    PROGRAM_SALE_READY,
})

# Human-readable names, used in API error details.
PROGRAM_LABELS: Dict[str, str] = {
    PROGRAM_VALUE_BUILDER: "Value Builder",
    PROGRAM_SALE_READY: "Sale Ready",
}


def is_supported_program(program_type: Optional[str]) -> bool:
    """True when this Engagement.tool is a module-based advisory program."""
    return program_type in SUPPORTED_PROGRAM_TYPES


def program_label(program_type: Optional[str]) -> str:
    """Display name for a program type, falling back to the raw value."""
    return PROGRAM_LABELS.get(program_type or "", program_type or "unknown")


def supported_programs_phrase() -> str:
    """'Value Builder and Sale Ready' - for error messages that list them."""
    labels = sorted(PROGRAM_LABELS[p] for p in SUPPORTED_PROGRAM_TYPES)
    if len(labels) == 1:
        return labels[0]
    return f"{', '.join(labels[:-1])} and {labels[-1]}"
