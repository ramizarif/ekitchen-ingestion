"""
Tests for import progress reporting: the reporter itself, the ingest request's
import_id, and the stage wiring through the recipe processor (mocked HTTP and
mocked external calls only).
"""
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.import_progress import (
    NO_PROGRESS,
    MAX_INGREDIENTS,
    MAX_INGREDIENT_CHARS,
    MAX_TITLE_CHARS,
    ProgressReporter,
    clean_preview,
    contract_extraction_method,
)


class FakeResponse:
    def __init__(self, status_code=204):
        self.status_code = status_code


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def make_reporter(import_id="imp-1", status=204, min_interval=1.0):
    post = MagicMock(return_value=FakeResponse(status))
    clock = FakeClock()
    auth = MagicMock(return_value=("https://backend.test", "tok-123"))
    reporter = ProgressReporter(import_id, auth, post=post, clock=clock, min_interval=min_interval)
    return reporter, post, clock, auth


def sent_bodies(post):
    return [c.kwargs["json"] for c in post.call_args_list]


# --- no-op and wiring -------------------------------------------------------

def test_no_import_id_is_a_no_op():
    post = MagicMock()
    auth = MagicMock()
    reporter = ProgressReporter(None, auth, post=post)
    reporter.report("reading", title="x")
    NO_PROGRESS.report("extracting", ingredients=["a"])
    post.assert_not_called()
    auth.assert_not_called()


def test_posts_stage_and_preview_to_progress_endpoint():
    reporter, post, _, _ = make_reporter(import_id="imp/1")
    reporter.report("reading", title="Caption", creator="@chef", thumbnail_url="https://cdn.test/a.jpg")

    url = post.call_args.args[0]
    assert url == "https://backend.test/recipe-imports/imp%2F1/progress"
    assert post.call_args.kwargs["headers"] == {"Authorization": "Bearer tok-123"}
    assert post.call_args.kwargs["timeout"] == 3.0
    assert sent_bodies(post) == [{
        "stage": "reading",
        "preview": {"title": "Caption", "creator": "@chef", "thumbnail_url": "https://cdn.test/a.jpg"},
    }]


def test_stage_without_preview_sends_stage_only():
    reporter, post, _, _ = make_reporter()
    reporter.report("saving")
    assert sent_bodies(post) == [{"stage": "saving"}]


# --- monotonic stages and diffing ------------------------------------------

def test_stages_never_move_backwards():
    reporter, post, _, _ = make_reporter()
    reporter.report("extracting")
    reporter.report("reading", title="late")
    assert [b["stage"] for b in sent_bodies(post)] == ["extracting"]


def test_same_stage_sends_only_changed_keys():
    reporter, post, clock, _ = make_reporter()
    reporter.report("extracting", extraction_method="description", ingredient_count=3)
    clock.now += 5
    reporter.report("extracting", extraction_method="description", ingredient_count=3)  # nothing new
    clock.now += 5
    reporter.report("extracting", extraction_method="description", ingredient_count=4, step_count=2)

    bodies = sent_bodies(post)
    assert len(bodies) == 2
    assert bodies[1] == {"stage": "extracting", "preview": {"ingredient_count": 4, "step_count": 2}}


def test_new_stage_is_sent_even_inside_the_throttle_window():
    reporter, post, _, _ = make_reporter(min_interval=60)
    reporter.report("reading", title="a")
    reporter.report("extracting")
    assert [b["stage"] for b in sent_bodies(post)] == ["reading", "extracting"]


def test_same_stage_updates_are_throttled_and_not_lost():
    reporter, post, clock, _ = make_reporter(min_interval=1.0)
    reporter.report("matching", ingredient_count=5, ingredients_done=0, matched_count=0, new_count=0)
    clock.now += 0.2
    reporter.report("matching", ingredient_count=5, ingredients_done=1, matched_count=1, new_count=0)  # throttled
    clock.now += 0.2
    reporter.report("matching", ingredient_count=5, ingredients_done=2, matched_count=1, new_count=1)  # throttled
    assert post.call_count == 1

    clock.now += 1.0
    reporter.report("matching", ingredient_count=5, ingredients_done=3, matched_count=2, new_count=1)
    assert post.call_count == 2
    # The send carries everything that changed since the last one that was accepted.
    assert sent_bodies(post)[1]["preview"] == {"ingredients_done": 3, "matched_count": 2, "new_count": 1}
    assert merged_preview(post) == {"ingredient_count": 5, "ingredients_done": 3,
                                               "matched_count": 2, "new_count": 1}


def test_force_bypasses_throttle():
    reporter, post, clock, _ = make_reporter(min_interval=60)
    reporter.report("matching", ingredients_done=1)
    clock.now += 0.1
    reporter.report("matching", ingredients_done=5, force=True)
    assert post.call_count == 2


def test_unknown_stage_is_ignored():
    reporter, post, _, _ = make_reporter()
    reporter.report("teleporting", title="x")
    post.assert_not_called()


# --- clamping -----------------------------------------------------------------

def test_title_is_clamped_to_contract_length():
    cleaned = clean_preview({"title": "t" * 500})
    assert len(cleaned["title"]) == MAX_TITLE_CHARS


def test_ingredients_are_clamped_to_count_and_length():
    raw = ["x" * 300] + [f"ingredient {i}" for i in range(60)]
    cleaned = clean_preview({"ingredients": raw})
    assert len(cleaned["ingredients"]) == MAX_INGREDIENTS
    assert len(cleaned["ingredients"][0]) == MAX_INGREDIENT_CHARS


def test_thumbnail_must_be_https():
    assert "thumbnail_url" not in clean_preview({"thumbnail_url": "http://cdn.test/a.jpg"})
    assert "thumbnail_url" not in clean_preview({"thumbnail_url": None})
    assert clean_preview({"thumbnail_url": "https://cdn.test/a.jpg"}) == {"thumbnail_url": "https://cdn.test/a.jpg"}


def test_unknown_keys_and_wrong_types_are_dropped():
    cleaned = clean_preview({
        "secret": "nope",
        "ingredient_count": "7",     # numeric string is fine
        "step_count": "many",        # not a number: dropped
        "servings": True,            # bool is not a count: dropped
        "title": 42,                 # not a string: dropped
    })
    assert cleaned == {"ingredient_count": 7}


def test_extraction_method_mapping():
    assert contract_extraction_method("description_only") == "description"
    assert contract_extraction_method("audio_only") == "audio"
    assert contract_extraction_method("hybrid") == "video"
    assert contract_extraction_method("vision_only") == "video"
    assert contract_extraction_method("something_else") is None


# --- best effort ---------------------------------------------------------------

def test_http_errors_and_exceptions_never_raise():
    reporter, post, clock, _ = make_reporter()
    post.side_effect = RuntimeError("connection reset")
    reporter.report("reading", title="x")  # must not raise

    post.side_effect = None
    post.return_value = FakeResponse(500)
    reporter.report("extracting")  # 500 is logged, not raised
    assert post.call_count == 2


def test_auth_failure_never_raises():
    post = MagicMock()
    auth = MagicMock(side_effect=RuntimeError("login down"))
    reporter = ProgressReporter("imp", auth, post=post)
    reporter.report("reading", title="x")
    post.assert_not_called()


def test_failed_send_is_retried_with_the_same_diff():
    reporter, post, clock, _ = make_reporter(min_interval=0)
    post.side_effect = [RuntimeError("timeout"), FakeResponse(204)]
    reporter.report("extracting", ingredient_count=3)
    reporter.report("extracting", ingredient_count=3)
    assert sent_bodies(post)[1] == {"stage": "extracting", "preview": {"ingredient_count": 3}}


def test_409_means_terminal_and_stops_reporting_quietly():
    reporter, post, _, _ = make_reporter(status=409)
    reporter.report("reading", title="x")
    reporter.report("extracting", ingredient_count=3)
    assert post.call_count == 1


# --- ingest request and wiring ----------------------------------------------

@pytest.fixture
def ingest_client():
    from app.routers import ingest
    app = FastAPI()
    app.include_router(ingest.router, prefix="/api/v1")
    return TestClient(app), ingest


def test_ingest_request_accepts_optional_import_id():
    from app.routers.ingest import IngestRequest
    assert IngestRequest(url="https://www.delish.com/x").import_id is None
    assert IngestRequest(url="https://www.delish.com/x", import_id="imp-9").import_id == "imp-9"


def test_ingest_without_import_id_reports_nothing(ingest_client):
    client, ingest = ingest_client
    with patch.object(ingest, "_ingest_website", return_value=MagicMock()) as website, \
         patch("services.import_progress.requests.post") as post:
        from fastapi.responses import JSONResponse
        website.return_value = JSONResponse({"success": True})
        client.post("/api/v1/ingest", json={"url": "https://www.delish.com/x", "generate_image": False})
    post.assert_not_called()
    assert website.call_args.args[3] is NO_PROGRESS


def test_ingest_with_import_id_reports_reading_and_passes_reporter(ingest_client):
    client, ingest = ingest_client
    processor = MagicMock()
    processor.get_ekitchen_token.return_value = "tok-abc"
    processor.ingredient_processor.ekitchen_base_url = "https://backend.test"

    from services.recipe_processor import RecipeProcessingResult
    processor.process_recipe_autonomous.return_value = RecipeProcessingResult(
        success=True, recipe_id="r1", recipe_name="Pepper Steak", ingredients_processed=1)

    with patch.object(ingest, "get_processor", return_value=processor), \
         patch("services.import_progress.requests.post") as post:
        post.return_value = FakeResponse(204)
        response = client.post("/api/v1/ingest", json={
            "url": "https://www.delish.com/pepper-steak", "generate_image": False, "import_id": "imp-7"})

    assert response.status_code == 200, response.text
    first = post.call_args_list[0]
    assert first.args[0] == "https://backend.test/recipe-imports/imp-7/progress"
    assert first.kwargs["json"] == {
        "stage": "reading",
        "preview": {"platform": "website"},
    }
    assert first.kwargs["headers"] == {"Authorization": "Bearer tok-abc"}

    progress = processor.process_recipe_autonomous.call_args.kwargs["progress"]
    assert progress.import_id == "imp-7"


def test_ingest_still_succeeds_when_progress_backend_is_down(ingest_client):
    client, ingest = ingest_client
    processor = MagicMock()
    processor.get_ekitchen_token.return_value = "tok"
    processor.ingredient_processor.ekitchen_base_url = "https://backend.test"
    from services.recipe_processor import RecipeProcessingResult
    processor.process_recipe_autonomous.return_value = RecipeProcessingResult(
        success=True, recipe_id="r1", recipe_name="X", ingredients_processed=1)

    with patch.object(ingest, "get_processor", return_value=processor), \
         patch("services.import_progress.requests.post", side_effect=RuntimeError("backend down")):
        response = client.post("/api/v1/ingest", json={
            "url": "https://www.delish.com/x", "generate_image": False, "import_id": "imp-7"})
    assert response.status_code == 200, response.text


def test_error_messages_are_human_and_codes_are_unchanged():
    from app.routers.ingest import _friendly_error
    assert _friendly_error("NOT_A_RECIPE", "raw reason", "d") == "This video doesn't look like a recipe."
    assert _friendly_error("TIKWM_FAILED", "TikWM returned HTTP 403", "d").startswith(
        "TikTok wouldn't let us read this video.")
    assert _friendly_error("INGESTION_FAILED", "DUPLICATE_RECIPE", "d") == "You've already imported this recipe."
    assert _friendly_error("INGESTION_FAILED", "something internal", "fallback") == "fallback"
    assert "Something went wrong" in _friendly_error("UNEXPECTED_ERROR", "KeyError: 'x'", "d")


# --- processor stage wiring ---------------------------------------------------

def _bare_processor():
    """A DirectRecipeProcessor without __init__ (no API clients, no config)."""
    from services.recipe_processor import DirectRecipeProcessor
    proc = DirectRecipeProcessor.__new__(DirectRecipeProcessor)
    proc.ingredient_processor = MagicMock()
    proc.global_ingredients_cache = {}
    proc._log_and_print = lambda *a, **k: None
    proc.standardize_ingredient_with_ai = lambda text: {
        "standardized_name": text.split()[-1].lower(), "reference_as": text}

    created = {"n": 0}

    def get_or_create(name):
        # Alternate: even-numbered names already exist, odd ones are created.
        proc._last_ingredient_created = bool(len(name) % 2)
        return f"id-{name}"

    proc.get_or_create_global_ingredient_enhanced = get_or_create
    proc.ingredient_processor.calculate_recipe_nutrition_from_map.return_value = {}
    return proc


def stage_sequence(post):
    """Stages as the backend would see them, with consecutive repeats collapsed."""
    stages = [b["stage"] for b in sent_bodies(post)]
    return [s for i, s in enumerate(stages) if i == 0 or s != stages[i - 1]]


def previews_for(post, stage):
    return [b.get("preview", {}) for b in sent_bodies(post) if b["stage"] == stage]


def merged_preview(post):
    """What the backend holds once every send is merged in (it keeps one preview per import)."""
    merged = {}
    for body in sent_bodies(post):
        merged.update(body.get("preview", {}))
    return merged


def _recipe_data(**overrides):
    data = {
        "title": "Pepper Steak",
        "description": "",
        "ingredients": ["1 lb flank steak", "2 bell peppers", "soy sauce"],
        "instructions": ["Slice", "Cook"],
        "prep_time": 10, "cook_time": 10, "total_time": 20,
        "yields": 4, "image_url": "", "author": "@chef", "url": "https://www.delish.com/pepper-steak",
    }
    data.update(overrides)
    return data


def _ai_decisions():
    return {"cuisine": "Chinese", "difficulty": "easy", "meal_type": "dinner",
            "cozy_instructions": ["Slice", "Cook"], "cozy_description": "d", "tags": []}


def test_website_pipeline_reports_every_stage_in_order():
    proc = _bare_processor()
    reporter, post, _, _ = make_reporter(min_interval=0)
    with patch.object(proc, "scrape_recipe_from_url", return_value=_recipe_data()), \
         patch.object(proc, "_recipe_already_exists", return_value=False), \
         patch.object(proc, "generate_ai_decisions", return_value=_ai_decisions()), \
         patch.object(proc, "_acquire_hero_image", return_value=(None, None)), \
         patch.object(proc, "create_ekitchen_recipe", return_value="recipe-1"), \
         patch.object(proc, "_remember_created_recipe"):
        result = proc.process_recipe_autonomous(
            "https://www.delish.com/pepper-steak", save_images_dir="imgs-dir", progress=reporter)

    assert result.success, result.error_message
    assert stage_sequence(post) == ["extracting", "matching", "writing", "photo", "saving"]

    extracting = previews_for(post, "extracting")[0]
    assert extracting["extraction_method"] == "page"
    assert extracting["title"] == "Pepper Steak"
    assert extracting["creator"] == "@chef"
    assert extracting["site_name"] == "delish.com"
    assert extracting["ingredients"] == ["1 lb flank steak", "2 bell peppers", "soy sauce"]
    assert extracting["ingredient_count"] == 3
    assert extracting["step_count"] == 2
    assert extracting["servings"] == 4
    assert extracting["total_minutes"] == 20

    matching = merged_preview(post)
    assert matching["ingredients_done"] == 3
    assert matching["ingredient_count"] == 3
    assert matching["matched_count"] + matching["new_count"] == 3

    assert previews_for(post, "writing")[-1] == {"cuisine": "Chinese", "difficulty": "easy", "meal_type": "dinner"}
    assert previews_for(post, "photo")[-1] == {"photo_source": "none"}


def test_matching_reports_are_throttled_when_the_reporter_is_throttled():
    proc = _bare_processor()
    reporter, post, _, _ = make_reporter(min_interval=60)  # frozen clock: only the forced final send gets through
    proc.process_ingredients_enhanced(["1 lb flank steak", "2 bell peppers", "soy sauce"], progress=reporter)
    assert len(previews_for(post, "matching")) == 2  # the first (start) and the forced final one
    assert merged_preview(post)["ingredients_done"] == 3


def test_video_pipeline_reports_matching_writing_photo_and_saving():
    proc = _bare_processor()
    reporter, post, _, _ = make_reporter(min_interval=0)
    parsed = {
        "name": "Pepper Steak", "description": "", "ingredients": ["1 lb flank steak", "2 bell peppers"],
        "steps": ["Slice", "Cook"], "servings": 4, "total_time_minutes": 20,
        "prep_time_minutes": None, "cook_time_minutes": None, "video_url": "https://www.tiktok.com/@a/video/1",
        "source_metadata": {"author": "@chef"},
    }
    with patch.object(proc, "generate_ai_decisions", return_value=_ai_decisions()), \
         patch.object(proc, "_acquire_hero_image", return_value=("/nowhere/x.jpg", "pexels")), \
         patch.object(proc, "create_ekitchen_recipe", return_value="recipe-2"), \
         patch.object(proc, "upload_recipe_image", return_value=True), \
         patch.object(proc, "_resolve_ambiguous_matches_for_recipe"):
        result = proc.process_parsed_recipe(parsed, save_images_dir="imgs-dir", progress=reporter)

    assert result.success, result.error_message
    # The video path's extracting report comes from the ingest layer, so the processor starts at matching.
    assert stage_sequence(post) == ["matching", "writing", "photo", "saving"]
    assert previews_for(post, "photo")[-1] == {"photo_source": "stock"}


def test_video_pipeline_fails_cleanly_when_ai_decisions_are_none():
    proc = _bare_processor()
    parsed = {"name": "Pepper Steak", "ingredients": ["1 lb flank steak"], "steps": ["Cook"]}
    with patch.object(proc, "generate_ai_decisions", return_value=None), \
         patch.object(proc, "create_ekitchen_recipe") as create:
        result = proc.process_parsed_recipe(parsed, save_images_dir=None)

    assert result.success is False
    assert result.error_message == "AI decision generation failed after retries"
    create.assert_not_called()
