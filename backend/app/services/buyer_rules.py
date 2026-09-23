"""
Buyer access rules: the vocabulary and the decisions, as plain values.

No database and no ORM, so each rule is unit tested directly, the same way
sale_ready_rules is. Anything here that waits on a client answer says so.
"""
from typing import FrozenSet

# ----------------------------------------------------------------------
# Vocabulary
# ----------------------------------------------------------------------
BUYER_STATUS_ACTIVE = "active"
BUYER_STATUS_REVOKED = "revoked"
BUYER_STATUSES: FrozenSet[str] = frozenset({BUYER_STATUS_ACTIVE, BUYER_STATUS_REVOKED})

ACTION_LIST = "list"
ACTION_VIEW = "view"
ACTION_DOWNLOAD = "download"
ACCESS_ACTIONS: FrozenSet[str] = frozenset({ACTION_LIST, ACTION_VIEW, ACTION_DOWNLOAD})

# The release boundary. ASSUMPTION from the mockup, which keys its buyer panel
# by sub-item ("one folder per DD category and sub-item"). Per-file or
# per-category release would change the schema, so this is called out rather
# than buried: confirm before the Drive work starts.
RELEASE_BOUNDARY = "dd_sub_item"


def validate_status(value: str) -> str:
    if value not in BUYER_STATUSES:
        raise ValueError(f"status must be one of {', '.join(sorted(BUYER_STATUSES))}")
    return value


def validate_action(value: str) -> str:
    if value not in ACCESS_ACTIONS:
        raise ValueError(f"action must be one of {', '.join(sorted(ACCESS_ACTIONS))}")
    return value


def folder_key(category_code: str, sub_item_code: str) -> str:
    """The stable identity of a data room folder."""
    return f"{category_code}|{sub_item_code}"


def is_live(status: str, is_deleted: bool) -> bool:
    """Whether a binding currently grants access."""
    return status == BUYER_STATUS_ACTIVE and not is_deleted
