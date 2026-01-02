"""
API routes package.
"""
from .auth import router as auth_router
from .engagements import router as engagements_router
from .note import router as notes_router
from .tasks import router as tasks_router
from .settings import router as settings_router
from .adv_client import router as adv_client_router

__all__ = ["auth_router", "engagements_router", "notes_router", "tasks_router", "settings_router", "adv_client_router"]



