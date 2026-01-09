"""
Application configuration management using Pydantic Settings.
"""
from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    APP_NAME: str = "Trinity Platform"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    
    # Auth0
    AUTH0_DOMAIN: str = os.getenv("AUTH0_DOMAIN")
    AUTH0_CLIENT_ID: str = os.getenv("AUTH0_CLIENT_ID")
    AUTH0_CLIENT_SECRET: str = os.getenv("AUTH0_CLIENT_SECRET")
    AUTH0_AUDIENCE: str = os.getenv("AUTH0_AUDIENCE")
    AUTH0_ALGORITHMS: str = "RS256"
    AUTH0_USERNAME_NAMESPACE: str = os.getenv("AUTH0_USERNAME_NAMESPACE", "https://your-app.com/username")
    
    # Auth0 Management API
    AUTH0_MANAGEMENT_API_AUDIENCE: str = os.getenv("AUTH0_MANAGEMENT_API_AUDIENCE")
    AUTH0_MANAGEMENT_CLIENT_ID: str = os.getenv("AUTH0_MANAGEMENT_CLIENT_ID")
    AUTH0_MANAGEMENT_CLIENT_SECRET: str = os.getenv("AUTH0_MANAGEMENT_CLIENT_SECRET")

    # Frontend
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:8080")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "1.0"))
    OPENAI_TIMEOUT: Optional[float] = None  # None = no timeout, or specify seconds (e.g., 60.0)
    # OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "16000"))
    
    # File Uploads
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")
    
    # Email (Gmail SMTP)
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "zohaibaamer2001@gmail.com")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "aoxo nuhu kllw noqj")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "zohaibaamer2001@gmail.com")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()



