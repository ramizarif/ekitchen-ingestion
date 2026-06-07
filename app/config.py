"""
Application configuration management.
"""
import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 4

    # CORS — default to internal backend URL only; override via env var for dev
    ALLOWED_ORIGINS: List[str] = ["http://ekitchen.railway.internal:8081"]

    # OpenAI
    OPENAI_API_KEY: str = ""

    # Spoonacular (optional)
    SPOONACULAR_API_KEY: str = ""

    # Parsing Timeouts
    WEBSITE_TIMEOUT: int = 30
    VIDEO_TIMEOUT: int = 120
    IMAGE_TIMEOUT: int = 60

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Sentry error tracking (no-op when SENTRY_DSN is unset)
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
