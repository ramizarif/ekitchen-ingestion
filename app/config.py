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

    # CORS
    ALLOWED_ORIGINS: List[str] = ["*"]

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

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
