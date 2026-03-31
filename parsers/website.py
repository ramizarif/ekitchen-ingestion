"""
Website recipe parser using recipe-scrapers library.
Supports 200+ recipe websites.
"""
import html
import time
import re
from typing import Optional, Dict, Any
from urllib.parse import urlparse

from recipe_scrapers import scrape_me
from parsers.base import BaseParser, ParseResult
from app.security import is_safe_url


class WebsiteParser(BaseParser):
    """
    Parse recipes from websites using the recipe-scrapers library.

    Supports 200+ recipe sites including:
    - AllRecipes
    - FoodNetwork
    - BonAppetit
    - SeriousEats
    - And many more...
    """

    def __init__(self, timeout: int = 30):
        super().__init__(timeout)
        self.parser_name = "recipe-scrapers"

    async def validate_url(self, url: str) -> bool:
        """
        Check if the URL is a valid HTTP/HTTPS URL and safe from SSRF.
        recipe-scrapers will handle site-specific validation.
        """
        is_safe, reason = is_safe_url(url)
        if not is_safe:
            import logging
            logging.getLogger(__name__).warning(f"URL blocked by SSRF check: {url} - {reason}")
            return False
        return True

    async def parse(self, url: str, **kwargs) -> ParseResult:
        """
        Parse a recipe from a website URL.

        Args:
            url: The recipe URL to parse
            **kwargs: Additional options (currently unused)

        Returns:
            ParseResult with recipe data or error information
        """
        start_time = time.time()

        # Validate URL
        if not await self.validate_url(url):
            return ParseResult(
                success=False,
                error_code="INVALID_URL",
                error_message=f"Invalid URL format: {url}",
                parser_name=self.parser_name
            )

        try:
            # Use recipe-scrapers to fetch and parse the recipe
            scraper = scrape_me(url)

            # Extract all available data, sanitizing scraped text to remove HTML
            recipe_data = {
                "name": self._sanitize_text(self._safe_extract(scraper.title)),
                "description": self._sanitize_text(self._safe_extract(scraper.description)),
                "ingredients": self._sanitize_list(self._safe_extract(scraper.ingredients, default=[])),
                "steps": self._sanitize_list(self._safe_extract(scraper.instructions_list, default=[])),
                "servings": self._extract_servings(scraper),
                "prep_time_minutes": self._extract_time_minutes(scraper.prep_time),
                "cook_time_minutes": self._extract_time_minutes(scraper.cook_time),
                "total_time_minutes": self._extract_time_minutes(scraper.total_time),
                "image_url": self._safe_extract(scraper.image),
                "video_url": None,  # recipe-scrapers doesn't typically extract videos
                "source_metadata": {
                    "author": self._safe_extract(scraper.author),
                    "site_name": self._safe_extract(scraper.site_name),
                    "host": self._safe_extract(scraper.host),
                    "url": url
                }
            }

            # Calculate processing time
            processing_time_ms = int((time.time() - start_time) * 1000)

            # Generate warnings for missing data
            warnings = self._generate_warnings(recipe_data)

            # Calculate confidence score
            confidence_score = self._calculate_confidence(recipe_data)

            return ParseResult(
                success=True,
                data=recipe_data,
                parser_name=self.parser_name,
                confidence_score=confidence_score,
                warnings=warnings
            )

        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)

            # Determine error type
            error_code = self._categorize_error(e)

            return ParseResult(
                success=False,
                error_code=error_code,
                error_message=str(e),
                parser_name=self.parser_name
            )

    def _sanitize_text(self, text: Any) -> Any:
        """Strip HTML tags and decode entities from scraped text."""
        if not isinstance(text, str):
            return text
        clean = re.sub(r'<[^>]+>', '', text)
        clean = html.unescape(clean)
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean

    def _sanitize_list(self, items: Any) -> Any:
        """Sanitize a list of strings."""
        if not isinstance(items, list):
            return items
        return [self._sanitize_text(item) for item in items if item]

    def _safe_extract(self, func_or_value, default: Any = None) -> Any:
        """
        Safely extract data from scraper, handling both methods and values.
        """
        try:
            # If it's callable (a method), call it
            if callable(func_or_value):
                result = func_or_value()
            else:
                result = func_or_value

            # Return default if result is None or empty string
            if result is None or result == "":
                return default

            return result
        except Exception:
            return default

    def _extract_servings(self, scraper) -> Optional[int]:
        """Extract servings, handling various formats."""
        try:
            yields_str = scraper.yields()
            if not yields_str:
                return None

            # Try to extract number from yields string
            # e.g., "4 servings", "Serves 6", "Makes 12 cookies"
            numbers = re.findall(r'\d+', str(yields_str))
            if numbers:
                return int(numbers[0])

            return None
        except Exception:
            return None

    def _extract_time_minutes(self, time_value) -> Optional[int]:
        """
        Extract time in minutes from various formats.
        Handles: integers, "PT30M" (ISO 8601), "30 minutes", etc.
        """
        try:
            if time_value is None:
                return None

            # If already an integer
            if isinstance(time_value, int):
                return time_value

            time_str = str(time_value)

            # Handle ISO 8601 duration format (e.g., "PT30M", "PT1H30M")
            if time_str.startswith('PT'):
                total_minutes = 0

                # Extract hours
                hours_match = re.search(r'(\d+)H', time_str)
                if hours_match:
                    total_minutes += int(hours_match.group(1)) * 60

                # Extract minutes
                minutes_match = re.search(r'(\d+)M', time_str)
                if minutes_match:
                    total_minutes += int(minutes_match.group(1))

                return total_minutes if total_minutes > 0 else None

            # Extract first number from string (e.g., "30 minutes" -> 30)
            numbers = re.findall(r'\d+', time_str)
            if numbers:
                return int(numbers[0])

            return None
        except Exception:
            return None

    def _generate_warnings(self, recipe_data: Dict[str, Any]) -> list:
        """Generate warnings for missing or suspicious data."""
        warnings = []

        if not recipe_data.get("ingredients"):
            warnings.append("No ingredients found")

        if not recipe_data.get("steps"):
            warnings.append("No cooking steps found")

        if not recipe_data.get("prep_time_minutes") and not recipe_data.get("cook_time_minutes"):
            warnings.append("No timing information available")

        if not recipe_data.get("servings"):
            warnings.append("Servings information not available")

        if not recipe_data.get("image_url"):
            warnings.append("No image URL found")

        return warnings

    def _calculate_confidence(self, recipe_data: Dict[str, Any]) -> float:
        """
        Calculate confidence score based on data completeness.
        1.0 = Perfect, 0.0 = Poor
        """
        score = 0.0

        # Core data (70% of score)
        if recipe_data.get("name"):
            score += 0.15
        if recipe_data.get("ingredients") and len(recipe_data["ingredients"]) > 0:
            score += 0.30
        if recipe_data.get("steps") and len(recipe_data["steps"]) > 0:
            score += 0.25

        # Metadata (30% of score)
        if recipe_data.get("servings"):
            score += 0.10
        if recipe_data.get("total_time_minutes") or recipe_data.get("prep_time_minutes"):
            score += 0.10
        if recipe_data.get("image_url"):
            score += 0.05
        if recipe_data.get("description"):
            score += 0.05

        return round(score, 2)

    def _categorize_error(self, error: Exception) -> str:
        """Categorize the error for better error reporting."""
        error_str = str(error).lower()

        if "timeout" in error_str or "timed out" in error_str:
            return "TIMEOUT"
        elif "404" in error_str or "not found" in error_str:
            return "NOT_FOUND"
        elif "403" in error_str or "forbidden" in error_str:
            return "FORBIDDEN"
        elif "connection" in error_str or "network" in error_str:
            return "NETWORK_ERROR"
        elif "schema" in error_str or "no schema" in error_str:
            return "UNSUPPORTED_SITE"
        else:
            return "PARSING_FAILED"
