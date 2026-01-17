"""
Abstract base class for all parsers.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ParseResult:
    """Standard result format for all parsers."""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    parser_name: str = "unknown"
    confidence_score: Optional[float] = None
    warnings: list = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class BaseParser(ABC):
    """Abstract base class for recipe parsers."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.parser_name = self.__class__.__name__

    @abstractmethod
    async def parse(self, url: str, **kwargs) -> ParseResult:
        """
        Parse a recipe from the given URL.

        Args:
            url: The URL to parse
            **kwargs: Additional parser-specific options

        Returns:
            ParseResult with recipe data or error information
        """
        pass

    @abstractmethod
    async def validate_url(self, url: str) -> bool:
        """
        Quick validation if this parser can handle the URL.

        Args:
            url: The URL to validate

        Returns:
            True if this parser can handle the URL
        """
        pass
