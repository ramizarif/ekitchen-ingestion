"""
Tests for the tiered website scraping strategy in DirectRecipeProcessor.

scrape_recipe_from_url tries, in order: (1) recipe-scrapers dedicated parser,
(2) schema.org/JSON-LD via wild_mode, (3) page text -> GPT-4o-mini. It returns the
first COMPLETE result (title + ingredients + steps), reuses a single HTML fetch for
tiers 2-3, and falls back to the best partial / None.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.recipe_processor import DirectRecipeProcessor


def _proc():
    p = DirectRecipeProcessor.__new__(DirectRecipeProcessor)
    p._log_and_print = lambda *a, **k: None
    return p


COMPLETE = {"title": "Soup", "ingredients": ["1 cup water"], "instructions": ["boil"]}
NO_STEPS = {"title": "Soup", "ingredients": ["1 cup water"], "instructions": []}


def test_complete_predicate():
    assert DirectRecipeProcessor._website_recipe_complete(COMPLETE) is True
    assert DirectRecipeProcessor._website_recipe_complete(NO_STEPS) is False
    assert DirectRecipeProcessor._website_recipe_complete({"title": "x", "ingredients": [], "instructions": ["s"]}) is False
    assert DirectRecipeProcessor._website_recipe_complete(None) is False


def test_tier1_short_circuits_without_fetching():
    p = _proc()
    p._scrape_via_recipe_scrapers = lambda url: dict(COMPLETE)
    # If tier 1 is complete we must NOT fetch HTML or hit later tiers.
    def _boom(*a, **k):
        raise AssertionError("should not be called when tier 1 is complete")
    p._fetch_page_html = _boom
    p._scrape_via_jsonld = _boom
    p._scrape_via_llm = _boom
    out = p.scrape_recipe_from_url("https://x.test/r")
    assert out["title"] == "Soup"


def test_falls_through_to_jsonld():
    p = _proc()
    p._scrape_via_recipe_scrapers = lambda url: None
    p._fetch_page_html = lambda url: "<html>...</html>"
    p._scrape_via_jsonld = lambda html, url: dict(COMPLETE)
    p._scrape_via_llm = lambda html, url: (_ for _ in ()).throw(AssertionError("LLM should not run if JSON-LD complete"))
    out = p.scrape_recipe_from_url("https://x.test/r")
    assert out == COMPLETE


def test_falls_through_to_llm():
    p = _proc()
    p._scrape_via_recipe_scrapers = lambda url: None
    p._fetch_page_html = lambda url: "<html>...</html>"
    p._scrape_via_jsonld = lambda html, url: None
    p._scrape_via_llm = lambda html, url: dict(COMPLETE)
    out = p.scrape_recipe_from_url("https://x.test/r")
    assert out == COMPLETE


def test_all_fail_returns_none():
    p = _proc()
    p._scrape_via_recipe_scrapers = lambda url: None
    p._fetch_page_html = lambda url: None  # fetch failed → tiers 2/3 skipped
    out = p.scrape_recipe_from_url("https://x.test/r")
    assert out is None


def test_returns_best_partial_when_nothing_complete():
    p = _proc()
    partial = {"title": "Soup", "ingredients": ["1 cup water"], "instructions": []}
    p._scrape_via_recipe_scrapers = lambda url: None
    p._fetch_page_html = lambda url: "<html>...</html>"
    p._scrape_via_jsonld = lambda html, url: partial   # has ingredients but no steps
    p._scrape_via_llm = lambda html, url: None
    out = p.scrape_recipe_from_url("https://x.test/r")
    assert out is partial  # best partial returned rather than None


def test_scraper_to_recipe_data_is_defensive():
    p = _proc()
    p._extract_time_minutes = lambda v: 0
    p._extract_servings = lambda v: 4

    class FlakyScraper:
        def title(self): return "Cake"
        def description(self): return "yum"
        def ingredients(self): return ["1 egg", "2 cups flour"]
        def instructions_list(self): return ["mix", "bake"]
        def prep_time(self): raise ValueError("no prep time")   # optional field raises
        def cook_time(self): raise ValueError("no cook time")
        def total_time(self): raise ValueError("no total time")
        def yields(self): raise ValueError("no yields")
        def image(self): return None
        def author(self): raise ValueError("no author")

    data = p._scraper_to_recipe_data(FlakyScraper(), "https://x.test/r")
    assert data["title"] == "Cake"
    assert data["ingredients"] == ["1 egg", "2 cups flour"]
    assert data["instructions"] == ["mix", "bake"]
    assert data["image_url"] == ""   # None coerced to ""
    assert data["author"] == ""      # raising method coerced to ""
    assert data["url"] == "https://x.test/r"
