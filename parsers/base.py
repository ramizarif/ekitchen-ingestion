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

    # Video parser specific fields (for multi-mode extraction tracking)
    extraction_method: Optional[str] = None  # "audio_only", "hybrid", "vision_only"
    frames_used: Optional[int] = None
    estimated_cost: Optional[float] = None
    fallback_reason: Optional[str] = None

    # Cost tracking fields (Issue #39)
    cost_breakdown: Optional[Dict[str, float]] = None  # Detailed cost breakdown
    audio_duration_seconds: Optional[float] = None
    video_size_mb: Optional[float] = None
    processing_time_ms: Optional[int] = None
    transcript_tokens: Optional[int] = None
    output_tokens: Optional[int] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.cost_breakdown is None:
            self.cost_breakdown = {
                "whisper_transcription": 0.0,
                "gpt4_text": 0.0,
                "gpt4_vision": 0.0,
                "video_download": 0.0,
                "total": 0.0
            }


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
