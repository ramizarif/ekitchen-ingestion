"""Only the backend, holding the shared token, may call the ingestion API."""
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.internal_auth import HEADER, requires_token
from app.main import app

client = TestClient(app)


@pytest.fixture
def token(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_TOKEN", "s3cret")
    return "s3cret"


@pytest.mark.parametrize("method,path,expected", [
    ("POST", "/api/v1/scan-receipt", True),
    ("POST", "/api/v1/resolve-ingredient", True),
    ("POST", "/api/v1/screen-image", True),
    ("POST", "/api/v1/parse", True),
    ("POST", "/api/v1/ingest", True),
    ("GET", "/api/v1/parsers", True),
    ("GET", "/api/v1/analytics/costs", False),
    ("POST", "/api/v1/analytics/costs", True),
    ("GET", "/health", False),
    ("GET", "/dashboard", False),
])
def test_which_routes_need_the_token(method, path, expected):
    assert requires_token(method, path) is expected


def test_a_call_without_the_token_is_refused(token):
    r = client.post("/api/v1/scan-receipt", json={"image_base64": "", "content_type": "image/jpeg"})
    assert r.status_code == 401


def test_a_wrong_token_is_refused(token):
    r = client.post("/api/v1/scan-receipt", headers={HEADER: "nope"}, json={})
    assert r.status_code == 401


def test_the_right_token_gets_through(token):
    # Past the gate, the request itself is invalid, which proves it got through.
    r = client.post("/api/v1/scan-receipt", headers={HEADER: token}, json={})
    assert r.status_code == 422


def test_nothing_is_checked_until_a_token_is_configured(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_TOKEN", "")
    assert client.post("/api/v1/scan-receipt", json={}).status_code == 422


def test_health_and_analytics_stay_open(token):
    assert client.get("/health").status_code != 401
    assert client.get("/api/v1/analytics/costs").status_code != 401
