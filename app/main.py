"""
FastAPI application for parsing recipes from various sources.
"""
import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import parse, health, ingest
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global flag for auth status
_auth_validated = False
_auth_error = None


def validate_ekitchen_auth() -> tuple[bool, str]:
    """Validate eKitchen authentication on startup."""
    import os
    import json
    import urllib.request
    import urllib.error
    
    base_url = os.environ.get('EKITCHEN_BASE_URL', '')
    admin_email = os.environ.get('EKITCHEN_ADMIN_EMAIL', '')
    admin_password = os.environ.get('EKITCHEN_ADMIN_PASSWORD', '')
    
    if not base_url:
        return False, "EKITCHEN_BASE_URL not set"
    if not admin_email:
        return False, "EKITCHEN_ADMIN_EMAIL not set"
    if not admin_password:
        return False, "EKITCHEN_ADMIN_PASSWORD not set"
    
    try:
        login_data = json.dumps({
            "email": admin_email,
            "password": admin_password
        }).encode('utf-8')
        
        req = urllib.request.Request(
            f"{base_url}/auth/login",
            data=login_data,
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            if result.get('token'):
                return True, "Authentication successful"
            else:
                return False, "No token in response"
                
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return False, f"Connection failed: {e.reason}"
    except Exception as e:
        return False, f"Auth error: {str(e)}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global _auth_validated, _auth_error
    
    logger.info("🚀 Starting eKitchen Ingestion API...")
    
    # Validate eKitchen authentication
    logger.info("🔐 Validating eKitchen authentication...")
    success, message = validate_ekitchen_auth()
    
    if success:
        _auth_validated = True
        logger.info(f"✅ eKitchen auth validated: {message}")
    else:
        _auth_validated = False
        _auth_error = message
        logger.error(f"❌ eKitchen auth FAILED: {message}")
        logger.error("⚠️  API will reject all ingest requests until auth is fixed!")
    
    yield  # Application runs here
    
    logger.info("👋 Shutting down eKitchen Ingestion API...")


app = FastAPI(
    title="eKitchen Recipe Parser API",
    description="Parse recipes from websites, videos, and images",
    version="0.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def auth_gate_middleware(request: Request, call_next):
    """Reject ingest requests if eKitchen auth failed on startup."""
    # Always allow health checks
    if request.url.path in ["/", "/health", "/healthz"]:
        return await call_next(request)
    
    # Block protected routes if auth failed
    if not _auth_validated and request.url.path.startswith("/api/v1/ingest"):
        logger.warning(f"⛔ Rejecting request to {request.url.path} - auth not validated")
        return JSONResponse(
            status_code=503,
            content={
                "error": "Service unavailable - eKitchen authentication failed on startup",
                "detail": _auth_error,
                "hint": "Check EKITCHEN_BASE_URL, EKITCHEN_ADMIN_EMAIL, EKITCHEN_ADMIN_PASSWORD environment variables"
            }
        )
    
    return await call_next(request)


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
