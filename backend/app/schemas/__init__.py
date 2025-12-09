"""
Pydantic schemas package.
"""
from .user import UserBase, UserCreate, UserResponse

from .engagement import (
    EngagementBase,
    EngagementCreate,
    EngagementUpdate,
    EngagementResponse,
    EngagementListItem,
    EngagementDetail,
)

from .diagnostic import (
    DiagnosticBase,
    DiagnosticCreate,
    DiagnosticResponseUpdate,
    DiagnosticSubmit,
    DiagnosticResponse,
    DiagnosticDetail,
    DiagnosticResults,
    DiagnosticListItem,
)

from .task import (
    TaskBase,
    TaskCreate,
    TaskCreateFromDiagnostic,
    TaskUpdate,
    TaskResponse,
    TaskListItem,
    BulkTaskCreate,
)

from .note import (
    NoteBase,
    NoteCreate,
    NoteUpdate,
    NoteResponse,
    NoteListItem,
    NoteAttachment,
)

__all__ = [
    # User schemas
    "UserBase",
    "UserCreate",
    "UserResponse",
    # Engagement schemas
    "EngagementBase",
    "EngagementCreate",
    "EngagementUpdate",
    "EngagementResponse",
    "EngagementListItem",
    "EngagementDetail",
    # Diagnostic schemas
    "DiagnosticBase",
    "DiagnosticCreate",
    "DiagnosticResponseUpdate",
    "DiagnosticSubmit",
    "DiagnosticResponse",
    "DiagnosticDetail",
    "DiagnosticResults",
    "DiagnosticListItem",
    # Task schemas
    "TaskBase",
    "TaskCreate",
    "TaskCreateFromDiagnostic",
    "TaskUpdate",
    "TaskResponse",
    "TaskListItem",
    "BulkTaskCreate",
    # Note schemas
    "NoteBase",
    "NoteCreate",
    "NoteUpdate",
    "NoteResponse",
    "NoteListItem",
    "NoteAttachment",
]



