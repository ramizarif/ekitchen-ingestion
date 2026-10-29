"""
Only the eKitchen backend may call the ingestion API.

The service has a public Railway domain, and its endpoints spend OpenAI credit
(vision, moderation, recipe import). The backend sends a shared token in
X-Internal-Token; when INTERNAL_API_TOKEN is set, a call to /api/v1 without it
gets a 401. When it isn't set, nothing is checked, so the backend can start
sending the token before ingestion starts requiring it.

Left open: health checks, and the read-only cost analytics behind /dashboard
(aggregate numbers, no OpenAI calls).
"""
import hmac

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import settings

HEADER = "X-Internal-Token"


def requires_token(method: str, path: str) -> bool:
    if not path.startswith("/api/v1/"):
        return False
    if method in ("GET", "HEAD") and path.startswith("/api/v1/analytics/"):
        return False
    return True


async def internal_auth_middleware(request: Request, call_next):
    token = settings.INTERNAL_API_TOKEN
    if token and requires_token(request.method, request.url.path):
        sent = request.headers.get(HEADER, "")
        if not hmac.compare_digest(sent.encode(), token.encode()):
            return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    return await call_next(request)
