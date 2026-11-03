"""
A user import whose recipe name is already taken by a different recipe is saved
under a name that says where it came from, instead of failing.

Recipe names are unique catalog-wide. Before this, importing @royaleeats's
"Pepper Steak" after Delish's failed with a 409 and the user saw "This import
didn't finish"; a website recipe with a taken name was told "You've already
imported this recipe".
"""
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests

from services.recipe_processor import DirectRecipeProcessor


def _processor():
    rp = DirectRecipeProcessor.__new__(DirectRecipeProcessor)
    rp.ekitchen_token = "tok"
    rp.ekitchen_refresh_token = "refresh"
    rp._log_and_print = lambda *a, **k: None
    ip = MagicMock()
    ip.ekitchen_base_url = "http://ekitchen.test"
    ip.access_token = "tok"
    ip.refresh_token = "refresh"
    rp.ingredient_processor = ip
    return rp


def _inputs(author="royaleeats", url="https://www.tiktok.com/@royaleeats/video/1"):
    recipe_data = {
        "title": "Pepper Steak", "description": "d", "prep_time": 5, "cook_time": 10,
        "total_time": 15, "yields": 2, "url": url, "author": author,
    }
    ai = {
        "cozy_instructions": ["step"], "cozy_description": "c", "cuisine": "Chinese",
        "difficulty": "Easy", "dietary_classification": None, "tags": ["dinner"],
    }
    nutrition = {k: 1 for k in ("calories", "protein", "fat", "carbohydrates", "fiber", "sugar")}
    return recipe_data, ai, [], nutrition


def _post_rejecting(taken):
    sent = []

    def post(url, headers=None, json=None, timeout=None):
        sent.append(json["name"])
        if json["name"] in taken:
            raise requests.exceptions.HTTPError(response=MagicMock(status_code=409, text="exists"))
        ok = MagicMock()
        ok.raise_for_status.return_value = None
        ok.json.return_value = {"id": "r1"}
        return ok

    return post, sent


def _catalog(*recipes):
    """Stub for GET /global-recipes/search: returns recipes whose name contains q."""
    def get(url, params=None, headers=None, timeout=None):
        q = (params or {}).get("q", "").lower()
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = [r for r in recipes if q in r["name"].lower()]
        return resp
    return get


DELISH = {"id": "delish", "name": "Pepper Steak",
          "inspired_by_url": "https://www.delish.com/pepper-steak", "imported_from_url": None}


def test_user_import_takes_a_sourced_name_when_the_name_is_taken():
    post, sent = _post_rejecting({"Pepper Steak"})
    with patch("requests.post", side_effect=post), patch("requests.get", side_effect=_catalog(DELISH)):
        rid = _processor().create_ekitchen_recipe(*_inputs(), user_id="u1")
    assert rid == "r1"
    assert sent == ["Pepper Steak", "Pepper Steak (royaleeats)"]


def _named(name, url):
    return {"id": name, "name": name, "inspired_by_url": url, "imported_from_url": None}


def test_falls_back_to_a_number_and_then_gives_up():
    others = [DELISH, _named("Pepper Steak (royaleeats)", "https://a.test/1"), _named("Pepper Steak 2", "https://b.test/2")]
    post, sent = _post_rejecting({r["name"] for r in others})
    with patch("requests.post", side_effect=post), patch("requests.get", side_effect=_catalog(*others)):
        assert _processor().create_ekitchen_recipe(*_inputs(), user_id="u1") == "r1"
    assert sent[-1] == "Pepper Steak 3"

    others.append(_named("Pepper Steak 3", "https://c.test/3"))
    post, sent = _post_rejecting({r["name"] for r in others})
    with patch("requests.post", side_effect=post), patch("requests.get", side_effect=_catalog(*others)):
        assert _processor().create_ekitchen_recipe(*_inputs(), user_id="u1") is None
    assert len(sent) == 4


def test_same_recipe_already_in_the_catalog_is_reused_not_copied():
    # Also what a retry sees after an earlier attempt saved the recipe.
    data, ai, ings, nutrition = _inputs(author="", url="https://www.delish.com/pepper-steak/")
    post, sent = _post_rejecting({"Pepper Steak"})
    with patch("requests.post", side_effect=post), patch("requests.get", side_effect=_catalog(DELISH)):
        assert _processor().create_ekitchen_recipe(data, ai, ings, nutrition, user_id="u1") == "delish"
    assert sent == ["Pepper Steak"]
    assert data["reused_recipe_id"] == "delish"


def test_a_409_that_is_not_about_the_name_is_not_renamed_around():
    post, sent = _post_rejecting({"Pepper Steak"})
    with patch("requests.post", side_effect=post), patch("requests.get", side_effect=_catalog()):
        assert _processor().create_ekitchen_recipe(*_inputs(), user_id="u1") is None
    assert sent == ["Pepper Steak"]


def test_website_recipe_uses_the_site():
    names = DirectRecipeProcessor._alternate_names(
        "Pepper Steak", {"author": "", "url": "https://www.delish.com/x"})
    assert names[0] == "Pepper Steak (delish.com)"


def test_catalog_ingestion_still_fails_on_a_taken_name():
    post, sent = _post_rejecting({"Pepper Steak"})
    with patch("requests.post", side_effect=post):
        assert _processor().create_ekitchen_recipe(*_inputs()) is None
    assert sent == ["Pepper Steak"]


# ─── Video results carry the link and creator on every extraction path ───

def test_video_result_gets_link_and_creator_when_extraction_left_them_out():
    import asyncio
    from parsers.base import ParseResult
    from parsers.video import VideoParser

    url = "https://www.tiktok.com/@royaleeats/video/1"
    parser = VideoParser.__new__(VideoParser)

    async def fake_parse(u, **kwargs):
        kwargs['progress'].report('reading', title='t', creator='@royaleeats')
        return ParseResult(success=True, data={"name": "Pepper Steak"}, parser_name="video",
                           extraction_method="description_only")

    parser._parse = fake_parse
    seen = []
    progress = MagicMock()
    progress.report.side_effect = lambda stage, **f: seen.append(stage)
    result = asyncio.run(parser.parse(url, progress=progress))

    assert result.data["source_url"] == url
    assert result.data["source_metadata"]["author"] == "@royaleeats"
    assert seen == ["reading"]  # reports still reach the real reporter
