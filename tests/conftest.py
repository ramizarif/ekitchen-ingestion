"""
Pytest configuration and fixtures.
"""
import sys
import os
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import json
from unittest.mock import patch

# Cache file to store last used URL for smoke tests
CACHE_FILE = Path(__file__).parent / ".smoke_test_url_cache.json"


@pytest.fixture(autouse=True)
def mock_ekitchen_auth():
    """Mock eKitchen auth validation for all tests."""
    with patch('app.main._auth_validated', True):
        yield


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--tiktok-url",
        action="store",
        default=None,
        help="TikTok URL to test with for smoke tests"
    )
    parser.addoption(
        "--interactive",
        action="store_true",
        default=False,
        help="Prompt for URL if not provided in smoke tests"
    )


def load_cached_url():
    """Load the last used URL from cache."""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
                return data.get('last_url')
        except Exception:
            return None
    return None


def save_cached_url(url: str):
    """Save URL to cache for next run."""
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump({'last_url': url}, f)
    except Exception:
        pass


def get_test_url(request):
    """Get test URL from CLI arg, interactive input, or cache."""
    # Try CLI argument first
    url = request.config.getoption("--tiktok-url")
    if url:
        save_cached_url(url)
        return url

    # Try interactive mode
    if request.config.getoption("--interactive"):
        cached = load_cached_url()
        if cached:
            print(f"\n💡 Last used URL: {cached}")
            response = input("Press Enter to use it, or paste a new URL: ").strip()
            url = response if response else cached
        else:
            url = input("\n🎬 Enter a TikTok URL to test: ").strip()

        if url:
            save_cached_url(url)
            return url

    # Fall back to cache
    url = load_cached_url()
    if url:
        return url

    return None


@pytest.fixture
def tiktok_url(request):
    """Fixture to provide TikTok URL for testing."""
    url = get_test_url(request)
    if not url:
        pytest.skip(
            "No TikTok URL provided. Run with:\n"
            "  pytest tests/test_smoke_video_ingestion.py -v --interactive\n"
            "or:\n"
            "  pytest tests/test_smoke_video_ingestion.py -v --tiktok-url='https://...'"
        )
    return url
