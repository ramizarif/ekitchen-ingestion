"""
Health check endpoints.
"""
from fastapi import APIRouter
from datetime import datetime

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0"
    }


@router.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with dependencies."""
    # TODO: Check OpenAI, Spoonacular, etc.
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
        "dependencies": {
            "openai": "not_implemented",
            "spoonacular": "not_implemented",
        }
    }
