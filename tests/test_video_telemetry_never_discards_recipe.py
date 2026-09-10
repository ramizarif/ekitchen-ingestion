"""
A successful extraction must survive its own bookkeeping.

parse() computes warnings, a cost estimate and a cost breakdown AFTER the recipe has been
extracted. Those calls used to sit bare inside parse()'s try, so any exception in them was
caught by the outer handler and returned as PARSE_ERROR with no recipe — an import thrown
away by its own accounting, and from the caller's side indistinguishable from a video that
genuinely could not be parsed.

The bug was reachable in the ordinary way: the block did os.listdir() on the temp directory
to measure the downloaded video, guarded only by os.path.exists.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest

from parsers.video import VideoParser, ZERO_COST_BREAKDOWN


@pytest.fixture
def parser():
    return VideoParser(timeout=1)


class TestTelemetryIsBestEffort:
    def test_missing_temp_dir_measures_zero_rather_than_raising(self, parser):
        assert parser._measure_video_size_mb('/tmp/definitely-not-a-real-dir-9f2b') == 0.0

    def test_none_temp_dir_measures_zero(self, parser):
        assert parser._measure_video_size_mb(None) == 0.0

    def test_measures_a_real_video_file(self, parser, tmp_path):
        video = tmp_path / "clip.mp4"
        video.write_bytes(b"x" * (2 * 1024 * 1024))
        assert parser._measure_video_size_mb(str(tmp_path)) == pytest.approx(2.0, rel=0.01)

    def test_a_file_that_vanishes_does_not_raise(self, parser, tmp_path, monkeypatch):
        (tmp_path / "clip.mp4").write_bytes(b"x")

        def gone(_path):
            raise OSError("file disappeared between listdir and getsize")

        monkeypatch.setattr(os.path, "getsize", gone)
        assert parser._measure_video_size_mb(str(tmp_path)) == 0.0

    def test_telemetry_survives_a_broken_cost_calculator(self, parser, monkeypatch):
        def boom(_data):
            raise ZeroDivisionError("bad arithmetic in cost accounting")

        monkeypatch.setattr(parser, "_calculate_extraction_cost", boom)

        tel = parser._telemetry(
            temp_dir=None,
            audio_result={'transcript': 'sear the steak'},
            download_info={'duration': 42.0},
            frames_used=3,
            start_time=0.0,
        )
        # The figure it could not compute degrades to zeros of the right SHAPE, so callers
        # reading cost_breakdown['total'] keep working.
        assert tel['cost_breakdown'] == ZERO_COST_BREAKDOWN
        # Everything it could still measure is present and real.
        assert tel['audio_duration_seconds'] == 42.0
        assert tel['transcript_tokens'] == len('sear the steak') // 4

    def test_telemetry_survives_junk_inputs_entirely(self, parser):
        class Hostile(dict):
            def get(self, *_a, **_k):
                raise RuntimeError("this object refuses to be read")

        tel = parser._telemetry(
            temp_dir=None,
            audio_result=Hostile(),
            download_info=Hostile(),
            frames_used=0,
            start_time=0.0,
        )
        assert tel['transcript_tokens'] == 0
        assert tel['audio_duration_seconds'] == 60.0
        # The breakdown is still computed, just from the fallbacks: one minute of Whisper at
        # $0.006 and no frames. A cost of exactly zero would mean accounting had collapsed too.
        assert tel['cost_breakdown']['total'] == pytest.approx(0.006)
        assert tel['cost_breakdown']['gpt4_vision'] == 0.0

    def test_safe_returns_the_value_when_nothing_goes_wrong(self, parser):
        assert parser._safe(lambda: 7, 0, 'seven') == 7

    def test_safe_returns_the_fallback_when_something_does(self, parser):
        def boom():
            raise ValueError("nope")

        assert parser._safe(boom, 'fallback', 'boom') == 'fallback'
