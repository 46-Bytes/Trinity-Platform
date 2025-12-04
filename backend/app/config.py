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
    
    # Frontend
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:8080")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()



