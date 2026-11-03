"""
TikTok import when TikWM is unavailable (it returned 403 to Railway in prod).

Order: TikWM -> TikTok oEmbed caption through description-first analysis -> yt-dlp
audio. All HTTP, yt-dlp and LLM calls are mocked.
"""
import asyncio
import os
import subprocess
import sys
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from parsers.video import VideoParser

TIKTOK_URL = "https://www.tiktok.com/@chef/video/7234567890123456789"
CAPTION = "Lemon pasta in 15 minutes #dinner"

FULL_RECIPE = {
    "is_recipe": True,
    "has_full_recipe": True,
    "confidence": 0.92,
    "recipe": {
        "name": "Lemon Pasta",
        "ingredients": [{"quantity": "200", "unit": "g", "name": "spaghetti"}],
        "steps": ["Boil the pasta."],
        "servings": 2,
        "total_time_minutes": 15,
    },
    "rejection_reason": None,
}
NOT_FULL = {"is_recipe": True, "has_full_recipe": False, "confidence": 0.5, "recipe": None, "rejection_reason": None}


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class Recorder:
    """Progress stand-in that records every report."""

    def __init__(self):
        self.calls = []

    def report(self, stage, *, force=False, **preview):
        self.calls.append((stage, preview))


def http_fake(tikwm=None, oembed=None):
    """tikwm / oembed: FakeResponse to return, or None for a 500."""
    def fake_get(url, *args, **kwargs):
        if "tikwm" in url:
            return tikwm or FakeResponse(403)
        if "oembed" in url:
            return oembed or FakeResponse(500)
        raise AssertionError(f"unexpected HTTP call: {url}")
    return fake_get


def oembed_ok():
    return FakeResponse(200, {
        "title": CAPTION,
        "author_unique_id": "chef",
        "author_name": "Chef",
        "thumbnail_url": "https://p16.tiktokcdn.com/cover.jpg",
    })


def run_parse(parser, progress=None):
    return asyncio.run(parser.parse(TIKTOK_URL, progress=progress or Recorder()))


def test_tikwm_403_then_oembed_caption_has_recipe_finishes_without_media():
    parser = VideoParser(timeout=5)
    progress = Recorder()
    with patch("parsers.video.requests.get", side_effect=http_fake(oembed=oembed_ok())), \
         patch.object(parser, "_analyze_description", return_value=FULL_RECIPE) as analyze, \
         patch.object(parser, "_download_audio") as download_audio, \
         patch.object(parser, "_download_from_url") as download_cdn:
        result = run_parse(parser, progress)

    assert result.success, result.error_message
    assert result.extraction_method == "description_only"
    assert result.data["ingredients"] == ["200 g spaghetti"]
    analyze.assert_called_once_with(CAPTION, CAPTION, "tiktok")
    download_audio.assert_not_called()
    download_cdn.assert_not_called()

    reading = [p for s, p in progress.calls if s == "reading"][0]
    assert reading["title"] == CAPTION
    assert reading["creator"] == "@chef"
    assert reading["thumbnail_url"] == "https://p16.tiktokcdn.com/cover.jpg"


def test_oembed_caption_without_recipe_falls_through_to_yt_dlp():
    parser = VideoParser(timeout=5)
    with patch("parsers.video.requests.get", side_effect=http_fake(oembed=oembed_ok())), \
         patch.object(parser, "_analyze_description", return_value=NOT_FULL) as analyze, \
         patch.object(parser, "_download_audio", return_value={"success": False, "error": "HTTP Error 403"}) as download_audio:
        result = run_parse(parser)

    assert not result.success
    assert result.error_code == "TIKWM_FAILED"
    download_audio.assert_called_once()
    assert download_audio.call_args.args[0] == TIKTOK_URL
    # The caption was analysed once; the yt-dlp metadata isn't analysed again.
    analyze.assert_called_once()


def test_everything_fails_returns_tiktok_message_to_the_user():
    from app.routers.ingest import _friendly_error

    parser = VideoParser(timeout=5)
    with patch("parsers.video.requests.get", side_effect=http_fake()), \
         patch.object(parser, "_download_audio", return_value={"success": False, "error": "ERROR: 403 Forbidden"}):
        result = run_parse(parser)

    assert not result.success
    assert result.error_code == "TIKWM_FAILED"
    assert "yt-dlp" in result.error_message  # the raw detail stays for the logs
    user_message = _friendly_error(result.error_code, result.error_message, "generic")
    assert user_message == (
        "TikTok wouldn't let us read this video. Try again in a few minutes, "
        "or share it from the TikTok app."
    )


def test_yt_dlp_audio_path_continues_into_the_normal_pipeline():
    parser = VideoParser(timeout=5)
    info = {"success": True, "title": CAPTION, "description": CAPTION, "creator": "@chef",
            "thumbnail_url": "https://p16.tiktokcdn.com/cover.jpg", "file_size": 0}
    recipe = {"name": "Lemon Pasta", "ingredients": ["200 g spaghetti"], "steps": ["Boil the pasta."],
              "servings": 2, "total_time_minutes": 15, "source_metadata": {}}

    with patch("parsers.video.requests.get", side_effect=http_fake(oembed=oembed_ok())), \
         patch.object(parser, "_analyze_description", return_value=NOT_FULL) as analyze, \
         patch.object(parser, "_download_audio", return_value=info), \
         patch.object(parser, "_try_audio_extraction", new=AsyncMock(
             return_value={"success": False, "reason": "no speech", "confidence": 0.0})), \
         patch.object(parser, "_download_video_for_platform", return_value="/nowhere/video.mp4"), \
         patch.object(parser, "_extract_key_frames", return_value=["f1", "f2"]), \
         patch.object(parser, "_vision_extract_recipe", return_value=recipe):
        result = run_parse(parser)

    assert result.success, result.error_message
    assert result.extraction_method == "vision_only"
    assert result.data["source_metadata"]["author"] == "@chef"
    analyze.assert_called_once()


def test_tikwm_success_keeps_cover_and_author_for_the_preview():
    parser = VideoParser(timeout=5)
    tikwm_payload = {"code": 0, "data": {
        "title": CAPTION, "play": "https://v.tiktokcdn.com/v.mp4", "music": "https://m.tiktokcdn.com/a.mp3",
        "cover": "https://p16.tiktokcdn.com/tikwm-cover.jpg", "author": {"unique_id": "chef"},
        "duration": 30, "id": 7234567890123456789}}
    progress = Recorder()
    with patch("parsers.video.requests.get", side_effect=http_fake(tikwm=FakeResponse(200, tikwm_payload))), \
         patch.object(parser, "_download_from_url", return_value={"success": True}), \
         patch.object(parser, "_analyze_description", return_value=FULL_RECIPE):
        result = run_parse(parser, progress)

    assert result.success, result.error_message
    reading = [p for s, p in progress.calls if s == "reading"][0]
    assert reading["creator"] == "@chef"
    assert reading["thumbnail_url"] == "https://p16.tiktokcdn.com/tikwm-cover.jpg"


def test_yt_dlp_metadata_keeps_thumbnail_creator_and_duration(tmp_path):
    parser = VideoParser(timeout=5)
    output_path = str(tmp_path / "audio.mp3")
    info_json = (
        '{"title": "Pepper steak", "description": "Full recipe", '
        '"thumbnail": "https://scontent.cdninstagram.com/t.jpg", '
        '"uploader": "Chef Name", "uploader_id": "chefhandle", "duration": 42}'
    )

    def fake_run(cmd, *args, **kwargs):
        if "--dump-json" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout=info_json, stderr="")
        open(output_path, "wb").write(b"audio")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    with patch("parsers.video.subprocess.run", side_effect=fake_run):
        info = parser._download_audio("https://www.instagram.com/reel/abc/", output_path)

    assert info["success"]
    assert info["thumbnail_url"] == "https://scontent.cdninstagram.com/t.jpg"
    assert info["creator"] == "@chefhandle"
    assert info["duration"] == 42
