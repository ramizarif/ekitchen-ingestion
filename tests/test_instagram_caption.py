"""
Unit tests for the Instagram caption-first path (no network, no API key).

Instagram serves yt-dlp an "empty media response" even for public reels, so we
fetch the caption from the public page's Open Graph metadata instead. These tests
lock the parsing that turns the og:description blob into a clean caption.
"""
import pytest

from parsers.video import VideoParser


def _page(og_title: str, og_description: str) -> str:
    """Minimal HTML carrying the two og tags _fetch_instagram_caption reads."""
    return (
        '<html><head>'
        f'<meta property="og:title" content="{og_title}" />'
        f'<meta property="og:description" content="{og_description}" />'
        '</head><body></body></html>'
    )


class _FakeResp:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code


@pytest.fixture
def parser():
    return VideoParser()


def test_strips_engagement_prefix_and_quotes(parser, monkeypatch):
    # Real-world shape: "<N> likes, <M> comments - <user> on <date>: "<caption>"."
    desc = ('465 likes, 11 comments - nunnamaryskitchen on June 28, 2026: '
            '&quot;Welcome to 7 days of Simple Cheap Eats. Day 1: Creamy Garlic '
            'Parmesan Pastina. 1 Tbsp Butter, 3 cloves garlic #pasta&quot;.')
    monkeypatch.setattr('parsers.video.requests.get',
                        lambda *a, **k: _FakeResp(_page('Mary on Instagram', desc)))

    title, caption = parser._fetch_instagram_caption('https://www.instagram.com/reel/ABC/')

    assert title == 'Mary on Instagram'
    # Engagement/author/date prefix and wrapping quotes are gone.
    assert caption.startswith('Welcome to 7 days of Simple Cheap Eats')
    assert 'likes,' not in caption
    assert caption.endswith('#pasta')


def test_non_200_returns_empty(parser, monkeypatch):
    monkeypatch.setattr('parsers.video.requests.get',
                        lambda *a, **k: _FakeResp('', status_code=429))
    assert parser._fetch_instagram_caption('https://www.instagram.com/reel/ABC/') == ('', '')


def test_network_error_returns_empty(parser, monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError('connection reset')
    monkeypatch.setattr('parsers.video.requests.get', _boom)
    assert parser._fetch_instagram_caption('https://www.instagram.com/reel/ABC/') == ('', '')


def test_missing_og_tags_returns_empty_caption(parser, monkeypatch):
    monkeypatch.setattr('parsers.video.requests.get',
                        lambda *a, **k: _FakeResp('<html><head></head></html>'))
    title, caption = parser._fetch_instagram_caption('https://www.instagram.com/reel/ABC/')
    assert title == ''
    assert caption == ''


def test_description_first_noop_on_empty(parser):
    # No title and no description → nothing to analyze, returns None (caller downloads).
    assert parser._try_description_first('', '', 'instagram', 0.0) is None
