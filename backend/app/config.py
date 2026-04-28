"""
Application configuration management using Pydantic Settings.
"""
from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Trinity Platform"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000

    # Database
    DATABASE_URL: str

    # Auth0
    AUTH0_DOMAIN: str
    AUTH0_CLIENT_ID: str
    AUTH0_CLIENT_SECRET: str
    AUTH0_AUDIENCE: str
    AUTH0_ALGORITHMS: str = "RS256"
    AUTH0_USERNAME_NAMESPACE: str = "https://your-app.com/username"

    # Auth0 Management API
    AUTH0_MANAGEMENT_API_AUDIENCE: str
    AUTH0_MANAGEMENT_CLIENT_ID: str
    AUTH0_MANAGEMENT_CLIENT_SECRET: str

    # Frontend
    FRONTEND_URL: str = "http://localhost:8080"

    # Security
    SECRET_KEY: str

    # OpenAI (preserved for rollback — optional when using Claude)
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_TEMPERATURE: float = 1.0
    OPENAI_TIMEOUT: Optional[float] = None  # None = no timeout, or specify seconds (e.g., 60.0)

    # Anthropic / Claude
    ANTHROPIC_API_KEY: str
    ANTHROPIC_MODEL: str = "claude-haiku-4-5-20251001"
    ANTHROPIC_MODEL_STRATEGY_WORKBOOK_STEP2: Optional[str] = None
    ANTHROPIC_MAX_TOKENS_STRATEGY_WORKBOOK_STEP2: Optional[int] = None
    ANTHROPIC_TEMPERATURE: float = 0.5
    ANTHROPIC_TIMEOUT: Optional[float] = 1800.0
    ANTHROPIC_MAX_TOKENS: int = 128000  # Max output tokens
    LLM_PROVIDER: str = "claude"  # "claude" or "openai"

    # Celery / Redis
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # File Uploads
    UPLOAD_DIR: str = "uploads"

    # Email (Gmail SMTP)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""

    # Google Drive
    GOOGLE_DRIVE_ENABLED: bool = False
    GOOGLE_DRIVE_CREDENTIALS_FILE: Optional[str] = None
    GOOGLE_DRIVE_FOLDER_ID: Optional[str] = None

    @field_validator("OPENAI_TEMPERATURE")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        if not 0.0 <= v <= 2.0:
            raise ValueError("OPENAI_TEMPERATURE must be between 0.0 and 2.0")
        return v

    @field_validator("ANTHROPIC_TEMPERATURE")
    @classmethod
    def validate_anthropic_temperature(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("ANTHROPIC_TEMPERATURE must be between 0.0 and 1.0")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
