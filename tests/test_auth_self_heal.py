"""
Tests for eKitchen auth self-heal.

Regression guard for the production outage where the long-lived (singleton) processor
lost its eKitchen token and then failed EVERY ingredient/recipe write with
"Not authenticated with eKitchen" until the service was manually restarted — because
the write paths bailed on a missing/expired token instead of re-authenticating.

These tests instantiate the processors via __new__ (skipping the heavy __init__ that
does real config loading + network auth) and drive the auth paths with mocks.
"""
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import urllib.error
import requests

from services.ingredient_processor import DirectIngredientProcessor
from services.recipe_processor import DirectRecipeProcessor


def _make_ingredient_processor(access_token=None):
    proc = DirectIngredientProcessor.__new__(DirectIngredientProcessor)
    proc.access_token = access_token
    proc.refresh_token = None
    proc.ekitchen_base_url = "http://ekitchen.test"
    proc._log_and_print = lambda *a, **k: None  # silence logging
    return proc


def _http_error(code):
    return urllib.error.HTTPError("http://ekitchen.test", code, "err", {}, None)


def _urlopen_ctx(payload):
    """Build an object usable as `with urllib.request.urlopen(...) as response:`."""
    resp = MagicMock()
    resp.read.return_value = __import__("json").dumps(payload).encode("utf-8")
    cm = MagicMock()
    cm.__enter__.return_value = resp
    cm.__exit__.return_value = False
    return cm


# ─────────────────────────────────────────────────────────────────────────────
# DirectIngredientProcessor.rename_ingredient — representative urllib write path
# ─────────────────────────────────────────────────────────────────────────────

def test_rename_reauths_when_token_missing():
    """Entry guard: a None token triggers re-auth instead of bailing."""
    proc = _make_ingredient_processor(access_token=None)

    def fake_reauth():
        proc.access_token = "fresh-token"
        return True

    proc._reauthenticate = MagicMock(side_effect=fake_reauth)

    with patch("urllib.request.urlopen", return_value=_urlopen_ctx({"message": "ok"})) as mock_open:
        assert proc.rename_ingredient("ing-1", "new name") is True

    proc._reauthenticate.assert_called_once()
    mock_open.assert_called_once()


def test_rename_retries_once_on_401_then_succeeds():
    """A 401 mid-write re-authenticates and retries exactly once."""
    proc = _make_ingredient_processor(access_token="stale-token")

    def fake_reauth():
        proc.access_token = "fresh-token"
        return True

    proc._reauthenticate = MagicMock(side_effect=fake_reauth)

    calls = {"n": 0}

    def urlopen_side_effect(req, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _http_error(401)
        return _urlopen_ctx({"message": "ok"})

    with patch("urllib.request.urlopen", side_effect=urlopen_side_effect):
        assert proc.rename_ingredient("ing-1", "new name") is True

    proc._reauthenticate.assert_called_once()
    assert calls["n"] == 2  # first 401, retried once and succeeded


def test_rename_gives_up_when_reauth_fails():
    """If re-auth can't restore a session, the write fails cleanly (no infinite loop)."""
    proc = _make_ingredient_processor(access_token=None)
    proc._reauthenticate = MagicMock(return_value=False)

    with patch("urllib.request.urlopen") as mock_open:
        assert proc.rename_ingredient("ing-1", "new name") is False

    mock_open.assert_not_called()  # never even attempted the write


# ─────────────────────────────────────────────────────────────────────────────
# DirectRecipeProcessor._ensure_ekitchen_auth — re-sync the dual-token copy
# ─────────────────────────────────────────────────────────────────────────────

def _make_recipe_processor(local_token="old-token"):
    rp = DirectRecipeProcessor.__new__(DirectRecipeProcessor)
    rp.ekitchen_token = local_token
    rp.ekitchen_refresh_token = "old-refresh"
    rp._log_and_print = lambda *a, **k: None
    ip = MagicMock()
    ip.ekitchen_base_url = "http://ekitchen.test"
    rp.ingredient_processor = ip
    return rp, ip


def test_ensure_auth_resyncs_token_from_ingredient_processor():
    """The recipe processor's stale token copy is refreshed from the authoritative session."""
    rp, ip = _make_recipe_processor(local_token="old-token")
    ip.access_token = "authoritative-token"
    ip.refresh_token = "authoritative-refresh"

    assert rp._ensure_ekitchen_auth() is True
    assert rp.ekitchen_token == "authoritative-token"
    assert rp.ekitchen_refresh_token == "authoritative-refresh"
    ip._reauthenticate.assert_not_called()  # token already present, no re-login needed


def test_ensure_auth_reauthenticates_when_no_token():
    rp, ip = _make_recipe_processor(local_token=None)
    ip.access_token = None

    def fake_reauth():
        ip.access_token = "recovered-token"
        ip.refresh_token = "recovered-refresh"
        return True

    ip._reauthenticate.side_effect = fake_reauth

    assert rp._ensure_ekitchen_auth() is True
    assert rp.ekitchen_token == "recovered-token"


def test_ensure_auth_returns_false_when_reauth_fails():
    rp, ip = _make_recipe_processor(local_token=None)
    ip.access_token = None
    ip._reauthenticate.return_value = False

    assert rp._ensure_ekitchen_auth() is False


# ─────────────────────────────────────────────────────────────────────────────
# DirectRecipeProcessor.create_ekitchen_recipe — requests write path 401 retry
# ─────────────────────────────────────────────────────────────────────────────

def _recipe_inputs():
    recipe_data = {
        "title": "Test Recipe", "description": "d", "prep_time": 5, "cook_time": 10,
        "total_time": 15, "yields": 2, "url": "http://src.test/r",
    }
    ai_decisions = {
        "cozy_instructions": ["step one"], "cozy_description": "cozy", "cuisine": "american",
        "difficulty": "easy", "dietary_classification": None, "tags": ["dinner"],
    }
    nutrition = {"calories": 1, "protein": 1, "fat": 1, "carbohydrates": 1, "fiber": 1, "sugar": 1}
    return recipe_data, ai_decisions, [], nutrition


def test_create_recipe_retries_once_on_401_then_succeeds():
    rp, ip = _make_recipe_processor(local_token="stale-token")
    ip.access_token = "fresh-token"
    ip.refresh_token = "fresh-refresh"
    # _ensure_ekitchen_auth is exercised for real (delegates to the ip mock).

    calls = {"n": 0}

    def post_side_effect(url, headers=None, json=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            err_resp = MagicMock(status_code=401)
            raise requests.exceptions.HTTPError(response=err_resp)
        ok = MagicMock()
        ok.raise_for_status.return_value = None
        ok.json.return_value = {"id": "recipe-123"}
        return ok

    recipe_data, ai_decisions, ingredients, nutrition = _recipe_inputs()
    with patch("requests.post", side_effect=post_side_effect):
        result = rp.create_ekitchen_recipe(recipe_data, ai_decisions, ingredients, nutrition)

    assert result == "recipe-123"
    assert calls["n"] == 2


def test_create_recipe_succeeds_first_try():
    rp, ip = _make_recipe_processor(local_token="good-token")
    ip.access_token = "good-token"
    ip.refresh_token = "good-refresh"

    ok = MagicMock()
    ok.raise_for_status.return_value = None
    ok.json.return_value = {"id": "recipe-9"}

    recipe_data, ai_decisions, ingredients, nutrition = _recipe_inputs()
    with patch("requests.post", return_value=ok) as mock_post:
        result = rp.create_ekitchen_recipe(recipe_data, ai_decisions, ingredients, nutrition)

    assert result == "recipe-9"
    mock_post.assert_called_once()
