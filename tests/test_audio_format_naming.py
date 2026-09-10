"""
Whisper reads a file's format from the NAME it is given, not from the bytes.

TikTok is why this matters. TikWM's CDN serves M4A; the downloader writes it to a hardcoded
"audio.mp3"; Whisper then rejected every single one with

    Invalid file format. Supported formats: ['flac','m4a','mp3','mp4','mpeg','mpga','oga','ogg','wav','webm']

even though m4a is right there on the list. The transcript came back empty, the confidence
scorer read that as "insufficient audio", and every TikTok import fell through to vision-only —
losing the narration, where the quantities and technique actually live, and paying roughly a
hundred times more for a worse recipe.

Nothing failed loudly. The import "succeeded" every time.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest

from parsers.video import VideoParser


# Real leading bytes for each container.
M4A = b'\x00\x00\x00\x1cftypM4A \x00\x00\x02\x00'
MP3_ID3 = b'ID3\x04\x00\x00\x00\x00\x00\x00'
MP3_SYNC = b'\xff\xfb\x90\x00\x00\x00\x00\x00'
OGG = b'OggS\x00\x02\x00\x00\x00\x00'
FLAC = b'fLaC\x00\x00\x00"'
WAV = b'RIFF$\x08\x00\x00WAVE'
WEBM = b'\x1a\x45\xdf\xa3\x01\x00\x00\x00'


@pytest.fixture
def parser():
    return VideoParser(timeout=1)


class TestSniffAudioFormat:
    @pytest.mark.parametrize("data,expected", [
        (M4A, 'm4a'),
        (MP3_ID3, 'mp3'),
        (MP3_SYNC, 'mp3'),
        (OGG, 'ogg'),
        (FLAC, 'flac'),
        (WAV, 'wav'),
        (WEBM, 'webm'),
    ])
    def test_identifies_container_from_bytes(self, parser, data, expected):
        assert parser._sniff_audio_format(data) == expected

    def test_unknown_bytes_return_none(self, parser):
        # None means "keep the existing name" — a genuinely odd file should fail loudly at the
        # API rather than be confidently mislabelled by us.
        assert parser._sniff_audio_format(b'this is not audio') is None

    def test_empty_file_returns_none(self, parser):
        assert parser._sniff_audio_format(b'') is None


class TestTranscribeNamesFileByItsRealFormat:
    def _capture_filename(self, parser, tmp_path, data, name_on_disk):
        """Run _transcribe_audio against a fake client and report the filename Whisper saw."""
        path = tmp_path / name_on_disk
        path.write_bytes(data)

        seen = {}

        class FakeTranscriptions:
            def create(self, **kwargs):
                seen['file'] = kwargs['file']
                return "Add two cups of flour and mix until smooth, then bake for twenty minutes."

        class FakeClient:
            audio = type('A', (), {'transcriptions': FakeTranscriptions()})()

        parser._openai_client = FakeClient()
        transcript = parser._transcribe_audio(str(path))
        return seen['file'][0], transcript

    def test_m4a_named_mp3_is_presented_as_m4a(self, parser, tmp_path):
        """The exact TikTok case: M4A bytes written to audio.mp3."""
        name, transcript = self._capture_filename(parser, tmp_path, M4A, "audio.mp3")
        assert name == "audio.m4a", "Whisper must be told this is m4a, or it 400s"
        assert transcript.startswith("Add two cups")

    def test_a_correctly_named_file_is_left_alone(self, parser, tmp_path):
        name, _ = self._capture_filename(parser, tmp_path, MP3_ID3, "audio.mp3")
        assert name == "audio.mp3"

    def test_unrecognised_bytes_keep_the_name_on_disk(self, parser, tmp_path):
        name, _ = self._capture_filename(parser, tmp_path, b'mystery meat', "audio.mp3")
        assert name == "audio.mp3"

    @pytest.mark.parametrize("data,ext", [(OGG, 'ogg'), (WAV, 'wav'), (WEBM, 'webm'), (FLAC, 'flac')])
    def test_other_containers_are_renamed_too(self, parser, tmp_path, data, ext):
        name, _ = self._capture_filename(parser, tmp_path, data, "audio.mp3")
        assert name == f"audio.{ext}"

    def test_transcription_failure_still_returns_none(self, parser, tmp_path):
        path = tmp_path / "audio.mp3"
        path.write_bytes(M4A)

        class Boom:
            def create(self, **_kwargs):
                raise RuntimeError("whisper is down")

        class FakeClient:
            audio = type('A', (), {'transcriptions': Boom()})()

        parser._openai_client = FakeClient()
        assert parser._transcribe_audio(str(path)) is None
