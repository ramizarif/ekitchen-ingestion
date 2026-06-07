"""
FastAPI application for parsing recipes from various sources.
"""
import asyncio
import logging
import sys
import time
from contextlib import asynccontextmanager

import anyio
import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import parse, health, ingest, analytics, dashboard, receipt
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Error tracking. Initialized before the FastAPI app so the FastAPI/Starlette
# integrations (auto-enabled by sentry-sdk[fastapi]) wrap the app and capture
# unhandled exceptions + 5xx responses. Safe no-op when SENTRY_DSN is unset.
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        send_default_pii=False,
    )
    logger.info(f"✅ Sentry initialized (env={settings.ENVIRONMENT})")
else:
    logger.info("ℹ️  Sentry disabled (SENTRY_DSN not set)")

# Global flag for auth status
_auth_validated = False
_auth_error = None

# Lazy re-validation state: when startup auth failed, gated requests retry
# validation at most once per cooldown window instead of rejecting forever.
_last_auth_revalidation = 0.0
_AUTH_REVALIDATION_COOLDOWN_SECONDS = 30.0


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
            if result.get('access_token'):
                return True, "Authentication successful"
            else:
                return False, f"No access_token in response: {list(result.keys())}"
                
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

    # Validate eKitchen authentication. Retry a few times: deploys of this
    # service and the backend can overlap (incident 2026-06-07: a single 10s
    # login timeout during backend deploy churn rejected ALL imports for ~29h
    # because the failed result was cached until restart).
    logger.info("🔐 Validating eKitchen authentication...")
    success, message = False, "not attempted"
    for attempt in range(1, 4):
        success, message = validate_ekitchen_auth()
        if success:
            break
        logger.warning(f"⚠️  eKitchen auth attempt {attempt}/3 failed: {message}")
        if attempt < 3:
            await asyncio.sleep(5 * attempt)

    if success:
        _auth_validated = True
        logger.info(f"✅ eKitchen auth validated: {message}")
    else:
        _auth_validated = False
        _auth_error = message
        logger.error(f"❌ eKitchen auth FAILED: {message}")
        logger.error("⚠️  Ingest requests will re-attempt validation (30s cooldown) until auth recovers")
        # Page immediately: the service booted unable to authenticate to the
        # backend, so every import is rejected until auth recovers. The real
        # reason lives here, not in the opaque 503 returned to clients.
        sentry_sdk.capture_message(
            f"eKitchen ingestion auth FAILED at startup (imports blocked until recovery): {message}",
            level="fatal",
        )

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
    """Reject ingest requests while eKitchen auth is invalid — but self-heal.

    A failed startup validation must NOT brick the service until a manual
    restart: on each gated request (rate-limited to one attempt per 30s) we
    re-run the validation, so the service recovers as soon as the backend is
    reachable again.
    """
    global _auth_validated, _auth_error, _last_auth_revalidation

    # Always allow health checks
    if request.url.path in ["/", "/health", "/healthz"]:
        return await call_next(request)

    # Block protected routes if auth failed
    if not _auth_validated and request.url.path.startswith("/api/v1/ingest"):
        now = time.monotonic()
        if now - _last_auth_revalidation >= _AUTH_REVALIDATION_COOLDOWN_SECONDS:
            _last_auth_revalidation = now
            # validate_ekitchen_auth blocks (urllib, 10s timeout) — run it off
            # the event loop so other requests aren't stalled.
            success, message = await anyio.to_thread.run_sync(validate_ekitchen_auth)
            if success:
                _auth_validated = True
                _auth_error = None
                logger.info("✅ eKitchen auth recovered via lazy re-validation")
                sentry_sdk.capture_message(
                    "eKitchen ingestion auth RECOVERED via lazy re-validation",
                    level="info",
                )
            else:
                _auth_error = message
                logger.warning(f"⚠️  eKitchen auth re-validation failed: {message}")
                # Real reason behind the opaque 503 below. Sentry groups repeats
                # into one issue, so a sustained outage is one alert with a
                # rising event count, not a flood.
                sentry_sdk.capture_message(
                    f"eKitchen ingestion still rejecting imports — auth re-validation failed: {message}",
                    level="error",
                )
        if not _auth_validated:
            logger.warning(f"⛔ Rejecting request to {request.url.path} - auth not validated")
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service temporarily unavailable",
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
app.include_router(receipt.router, prefix="/api/v1", tags=["receipt"])
app.include_router(analytics.router, prefix="/api/v1", tags=["analytics"])
app.include_router(dashboard.router, tags=["dashboard"])


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "eKitchen Recipe Parser API",
        "version": "0.1.0",
        "docs_url": "/docs",
        "health_url": "/health",
    }
