"""
Health check endpoints.
"""
from fastapi import APIRouter
from datetime import datetime

router = APIRouter()


def get_auth_status():
    """Get the current auth status from main module."""
    from app.main import _auth_validated, _auth_error
    return _auth_validated, _auth_error


@router.get("/health")
async def health_check():
    """Basic health check."""
    auth_ok, auth_error = get_auth_status()
    return {
        "status": "healthy" if auth_ok else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
        "ekitchen_auth": "ok" if auth_ok else f"failed: {auth_error}"
    }


@router.get("/healthz")
async def health_check_k8s():
    """Kubernetes-style liveness probe (always returns 200)."""
    return {"status": "alive"}


@router.get("/ready")
async def readiness_check():
    """Kubernetes-style readiness probe (requires auth to be valid)."""
    auth_ok, auth_error = get_auth_status()
    if not auth_ok:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "reason": f"eKitchen auth failed: {auth_error}"
            }
        )
    return {"status": "ready"}


@router.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with dependencies."""
    auth_ok, auth_error = get_auth_status()
    return {
        "status": "healthy" if auth_ok else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
        "dependencies": {
            "ekitchen": "ok" if auth_ok else f"auth_failed: {auth_error}",
            "openai": "not_implemented",
            "spoonacular": "not_implemented",
        }
    }
