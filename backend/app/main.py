"""
FastAPI application entry point with Auth0 integration.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from pathlib import Path
import logging
from .config import settings

from .api.diagnostics import router as diagnostics_router

from .api.files import router as files_router
from .api.upload_poc import router as upload_poc_router
from .api import auth_router, engagements_router, notes_router, tasks_router, settings_router, adv_client_router
from .api.chat import router as chat_router
from .api.users import router as users_router
from .api.firms import router as firms_router
from .api.subscriptions import router as subscriptions_router
from .api.dashboard import router as dashboard_router
from .api.strategy_workbook import router as strategy_workbook_router

# from .services.openai_service import OpenAIService  # Preserved for rollback
from .services.claude_service import ClaudeService
from . import models  # noqa: F401 — registers models with Base metadata for Alembic

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Disable verbose SQLAlchemy logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)

# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Backend API for Trinity Platform with Auth0 authentication",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Add Session Middleware (required for OAuth)
# IMPORTANT: SessionMiddleware must be added BEFORE CORS to ensure cookies work
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="trinity_session",
    max_age=3600 * 24 * 7,  # 7 days
    same_site="lax",  # "lax" works for backend-to-backend (login -> callback on same origin)
    https_only=settings.APP_ENV != "development",
)

# Configure CORS
# When allow_credentials=True, "*" cannot be used - must list specific origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)

app.include_router(diagnostics_router, prefix="/api")
app.include_router(files_router, prefix="/api")
app.include_router(upload_poc_router)  # POC router (already has /api prefix)
app.include_router(engagements_router)
app.include_router(notes_router)
app.include_router(tasks_router)
app.include_router(settings_router)
app.include_router(chat_router)
app.include_router(users_router)
app.include_router(adv_client_router)
app.include_router(firms_router)
app.include_router(subscriptions_router)
app.include_router(dashboard_router)
app.include_router(strategy_workbook_router, prefix="/api")

# Mount static files directory for serving uploaded files
# This allows /files/... URLs to be served directly
base_dir = Path(__file__).resolve().parents[1]  # Go up to backend/
files_dir = base_dir / "files"
files_dir.mkdir(exist_ok=True)  # Create directory if it doesn't exist

app.mount("/files", StaticFiles(directory=str(files_dir)), name="files")


@app.on_event("startup")
async def startup_event():
    """Initialize services at application startup"""
    logger = logging.getLogger(__name__)
    logger.info("🚀 Application startup - initializing services...")
    
    # Initialize Claude client once at startup
    ClaudeService.initialize_client()
    logger.info("Claude client initialized")

    # Preserved for rollback:
    # OpenAIService.initialize_client()
    # logger.info("OpenAI client initialized")
    
    logger.info("✅ Application startup complete")



@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Trinity Platform API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "environment": settings.APP_ENV
    }


@app.on_event("shutdown")
async def shutdown_event():
    """Handle application shutdown."""
    logger = logging.getLogger(__name__)
    logger.info("Application shutdown initiated")
    logger.info("Application shutdown complete")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG
    )



