"""
FastAPI application for parsing recipes from various sources.
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import parse, health, ingest
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

app = FastAPI(
    title="eKitchen Recipe Parser API",
    description="Parse recipes from websites, videos, and images",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(parse.router, prefix="/api/v1", tags=["parse"])
app.include_router(ingest.router, prefix="/api/v1", tags=["ingest"])


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "eKitchen Recipe Parser API",
        "version": "0.1.0",
        "docs_url": "/docs",
        "health_url": "/health",
    }
