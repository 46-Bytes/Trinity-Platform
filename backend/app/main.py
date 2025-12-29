"""
FastAPI application entry point with Auth0 integration.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from pathlib import Path
import logging
import asyncio
from .config import settings
from .utils.background_task_manager import background_task_manager

from .api.diagnostics import router as diagnostics_router

from .api.files import router as files_router
from .api import auth_router, engagements_router, notes_router, tasks_router, settings_router

from .database import engine, Base

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Disable verbose SQLAlchemy logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)

# Create database tables
Base.metadata.create_all(bind=engine)

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
    https_only=False,  # Set to True in production with HTTPS
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8080",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)

app.include_router(diagnostics_router, prefix="/api")
app.include_router(files_router, prefix="/api")
app.include_router(engagements_router)
app.include_router(notes_router)
app.include_router(tasks_router)
app.include_router(settings_router)

# Mount static files directory for serving uploaded files
# This allows /files/... URLs to be served directly
base_dir = Path(__file__).resolve().parents[1]  # Go up to backend/
files_dir = base_dir / "files"
files_dir.mkdir(exist_ok=True)  # Create directory if it doesn't exist

app.mount("/files", StaticFiles(directory=str(files_dir)), name="files")



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
    """Handle application shutdown - gracefully terminate background tasks."""
    logger = logging.getLogger(__name__)
    logger.info("🛑 Application shutdown initiated")
    
    # Initiate shutdown in task manager
    background_task_manager.initiate_shutdown()
    
    # Wait for tasks to complete (with timeout)
    await background_task_manager.wait_for_shutdown(timeout=30.0)
    
    logger.info("✅ Application shutdown complete")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG
    )



