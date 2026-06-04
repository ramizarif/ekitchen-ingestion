"""
Tests for Facebook video support + yt-dlp impersonation gating.

- Facebook URLs must route to the video pipeline and be detected as platform
  'facebook' (regression guard for launch).
- yt-dlp --impersonate must only be passed when the installed binary actually
  supports it; the standalone release binary lacks curl_cffi and hard-fails on
  --impersonate, which broke Instagram/Facebook/YouTube downloads in prod.
"""
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from parsers.video import VideoParser
from app.routers.ingest import detect_url_type


FACEBOOK_URLS = [
    "https://www.facebook.com/recipeslearn/videos/reels-recie-food/1106610630839743/",
    "https://www.facebook.com/watch/?v=123456789",
    "https://www.facebook.com/reel/1234567890",
    "https://www.facebook.com/share/v/abcDEF123/",
    "https://fb.watch/abc-123/",
]


def _parser():
    # Skip heavy __init__ (no network / OpenAI needed for these checks).
    return VideoParser.__new__(VideoParser)


def test_router_routes_facebook_to_video():
    for url in FACEBOOK_URLS:
        url_type, platform = detect_url_type(url)
        assert url_type == "video", f"{url} should route to video, got {url_type}"
        assert platform == "facebook", f"{url} should be facebook, got {platform}"


def test_detect_platform_facebook():
    vp = _parser()
    for url in FACEBOOK_URLS:
        assert vp._detect_platform(url) == "facebook", f"{url} not detected as facebook"


def test_existing_platforms_still_detected():
    vp = _parser()
    assert vp._detect_platform("https://www.tiktok.com/@9resha/video/7643779462269652246") == "tiktok"
    assert vp._detect_platform("https://www.instagram.com/reel/DVBzRI2AN_t/") == "instagram"
    assert vp._detect_platform("https://youtu.be/abc123") == "youtube"
    assert vp._detect_platform("https://www.allrecipes.com/recipe/123/") is None


def test_facebook_has_platform_config():
    assert "facebook" in VideoParser.PLATFORM_CONFIG
    cfg = VideoParser.PLATFORM_CONFIG["facebook"]
    assert "audio_confidence_threshold" in cfg and "default_frames" in cfg


def test_ytdlp_args_skip_impersonate_when_unsupported():
    vp = _parser()
    VideoParser._impersonate_supported = None  # reset cache
    # Probe reports no impersonation targets → flag must be omitted.
    fake = MagicMock(stdout="(no impersonate targets available)")
    with patch("parsers.video.subprocess.run", return_value=fake):
        args = vp._ytdlp_base_args()
    assert "--impersonate" not in args
    VideoParser._impersonate_supported = None  # cleanup


def test_ytdlp_args_include_impersonate_when_supported():
    vp = _parser()
    VideoParser._impersonate_supported = None
    fake = MagicMock(stdout="Available targets:\nchrome\nchrome-110\nsafari")
    with patch("parsers.video.subprocess.run", return_value=fake):
        args = vp._ytdlp_base_args()
    assert "--impersonate" in args and "chrome" in args
    VideoParser._impersonate_supported = None


def test_ytdlp_args_skip_impersonate_when_probe_errors():
    vp = _parser()
    VideoParser._impersonate_supported = None
    with patch("parsers.video.subprocess.run", side_effect=FileNotFoundError("yt-dlp missing")):
        args = vp._ytdlp_base_args()
    assert "--impersonate" not in args
    VideoParser._impersonate_supported = None
