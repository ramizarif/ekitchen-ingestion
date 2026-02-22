"""
Unit tests for cost tracking functionality (Issue #39).
"""
import pytest
from parsers.video import VideoParser


class TestCostTracking:
    """Test suite for cost tracking and calculation."""

    @pytest.fixture
    def video_parser(self):
        """Create VideoParser instance for testing."""
        return VideoParser(timeout=120)

    def test_calculate_extraction_cost_audio_only(self, video_parser):
        """Test cost calculation for audio-only extraction."""
        extraction_data = {
            'audio_duration_seconds': 60,  # 1 minute
            'transcript_tokens': 200,
            'output_tokens': 500,
            'frames_used': 0,
            'video_size_mb': 5.0
        }

        costs = video_parser._calculate_extraction_cost(extraction_data)

        # Whisper: 1 min * $0.006 = $0.006
        assert costs['whisper_transcription'] == pytest.approx(0.006, abs=0.0001)

        # GPT-4o text: (200/1M * $2.50) + (500/1M * $10) = $0.0005 + $0.005 = $0.0055
        assert costs['gpt4_text'] == pytest.approx(0.0055, abs=0.0001)

        # No vision cost
        assert costs['gpt4_vision'] == 0.0

        # Video download: 5MB * $0.0001 = $0.0005
        assert costs['video_download'] == pytest.approx(0.0005, abs=0.0001)

        # Total
        expected_total = 0.006 + 0.0055 + 0.0005
        assert costs['total'] == pytest.approx(expected_total, abs=0.0001)

    def test_calculate_extraction_cost_hybrid(self, video_parser):
        """Test cost calculation for hybrid extraction."""
        extraction_data = {
            'audio_duration_seconds': 45,  # 0.75 minutes
            'transcript_tokens': 150,
            'output_tokens': 500,
            'frames_used': 3,
            'video_size_mb': 8.0
        }

        costs = video_parser._calculate_extraction_cost(extraction_data)

        # Whisper: 0.75 min * $0.006 = $0.0045
        assert costs['whisper_transcription'] == pytest.approx(0.0045, abs=0.0001)

        # GPT-4o text: (150/1M * $2.50) + (500/1M * $10) = $0.000375 + $0.005 = $0.005375
        assert costs['gpt4_text'] == pytest.approx(0.005375, abs=0.0001)

        # GPT-4 Vision: 3 frames * $0.03 = $0.09
        assert costs['gpt4_vision'] == pytest.approx(0.09, abs=0.0001)

        # Video download: 8MB * $0.0001 = $0.0008
        assert costs['video_download'] == pytest.approx(0.0008, abs=0.0001)

        # Total
        expected_total = 0.0045 + 0.005375 + 0.09 + 0.0008
        assert costs['total'] == pytest.approx(expected_total, abs=0.001)

    def test_calculate_extraction_cost_vision_only(self, video_parser):
        """Test cost calculation for vision-only extraction."""
        extraction_data = {
            'audio_duration_seconds': 0,  # No audio used
            'transcript_tokens': 0,
            'output_tokens': 500,
            'frames_used': 5,
            'video_size_mb': 12.0
        }

        costs = video_parser._calculate_extraction_cost(extraction_data)

        # No whisper cost
        assert costs['whisper_transcription'] == 0.0

        # No GPT-4 text cost (no transcript)
        assert costs['gpt4_text'] == 0.0

        # GPT-4 Vision: 5 frames * $0.03 = $0.15
        assert costs['gpt4_vision'] == pytest.approx(0.15, abs=0.0001)

        # Video download: 12MB * $0.0001 = $0.0012
        assert costs['video_download'] == pytest.approx(0.0012, abs=0.0001)

        # Total
        expected_total = 0.15 + 0.0012
        assert costs['total'] == pytest.approx(expected_total, abs=0.001)

    def test_calculate_extraction_cost_no_data(self, video_parser):
        """Test cost calculation with empty extraction data."""
        extraction_data = {}

        costs = video_parser._calculate_extraction_cost(extraction_data)

        # All costs should be 0
        assert costs['whisper_transcription'] == 0.0
        assert costs['gpt4_text'] == 0.0
        assert costs['gpt4_vision'] == 0.0
        assert costs['video_download'] == 0.0
        assert costs['total'] == 0.0

    def test_cost_breakdown_structure(self, video_parser):
        """Test that cost breakdown has correct structure."""
        extraction_data = {
            'audio_duration_seconds': 30,
            'transcript_tokens': 100,
            'frames_used': 2
        }

        costs = video_parser._calculate_extraction_cost(extraction_data)

        # Verify structure
        assert 'whisper_transcription' in costs
        assert 'gpt4_text' in costs
        assert 'gpt4_vision' in costs
        assert 'video_download' in costs
        assert 'total' in costs

        # Verify all values are floats
        for key, value in costs.items():
            assert isinstance(value, float), f"{key} should be float, got {type(value)}"

    def test_parse_result_includes_cost_fields(self):
        """Test that ParseResult includes all cost tracking fields."""
        from parsers.base import ParseResult

        result = ParseResult(
            success=True,
            data={"name": "Test Recipe"},
            parser_name="video",
            extraction_method="hybrid",
            frames_used=3,
            audio_duration_seconds=45.5,
            video_size_mb=8.2,
            processing_time_ms=5000,
            transcript_tokens=200,
            output_tokens=500
        )

        # Verify cost tracking fields exist
        assert hasattr(result, 'cost_breakdown')
        assert hasattr(result, 'audio_duration_seconds')
        assert hasattr(result, 'video_size_mb')
        assert hasattr(result, 'processing_time_ms')
        assert hasattr(result, 'transcript_tokens')
        assert hasattr(result, 'output_tokens')

        # Verify cost_breakdown is initialized
        assert result.cost_breakdown is not None
        assert isinstance(result.cost_breakdown, dict)
        assert 'total' in result.cost_breakdown
