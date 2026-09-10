"""
Import failures are read by the person who pasted the link, so they have to read like English.

The rule this enforces: a failure must tell someone what happened to THEIR video. "Could not
extract recipe from video" fails that — it describes our code's outcome, not their video, and
someone who reads it concludes the importer is broken rather than that this particular clip has
no recipe in it. That belief costs the whole feature, not one link.

These messages are also the UI. The mobile client renders processing_error verbatim in four
places (ImportStatusScreen, ImportCompleteToast, ImportManager, PlanFlowModal), so a string
written here appears on a phone with no editing in between.

The copy check walks the AST rather than a hand-kept list, so a message added later is held to
the same rule without anyone remembering to add it.
"""

import ast
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest

from parsers.video import VideoParser

VIDEO_PY = os.path.join(os.path.dirname(__file__), '..', 'parsers', 'video.py')

# Words that mean something to us and nothing to a cook.
JARGON = [
    'tikwm', 'yt-dlp', 'ytdlp', 'ffprobe', 'ffmpeg', 'whisper', 'gpt-4', 'gpt4',
    'traceback', 'exception', 'stacktrace', 'null', 'none', 'json', 'api',
    'parser', 'pipeline', 'fallback', 'vision', 'transcript', 'metadata',
    'http', 'status code', 'timeout', 'errno',
]


def literal_error_messages():
    """Every error_message= in video.py that is a plain string literal."""
    with open(VIDEO_PY) as f:
        tree = ast.parse(f.read())

    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg != 'error_message':
                continue
            # ast.literal_eval handles both a bare string and implicit concatenation.
            try:
                value = ast.literal_eval(kw.value)
            except (ValueError, SyntaxError):
                continue  # an f-string or a .get() — covered by the dynamic tests below
            if isinstance(value, str):
                found.append((node.lineno, value))
    return found


class TestFailureCopyIsForPeople:
    def test_there_are_messages_to_check(self):
        msgs = literal_error_messages()
        assert len(msgs) >= 8, f"expected the parser's failure messages, found {len(msgs)}"

    @pytest.mark.parametrize("lineno,message", literal_error_messages())
    def test_message_is_free_of_jargon(self, lineno, message):
        lowered = message.lower()
        hits = [word for word in JARGON if word in lowered]
        assert not hits, (
            f"video.py:{lineno} shows a person internal vocabulary {hits}: {message!r}. "
            f"Technical detail belongs in the log line, not in front of the user."
        )

    @pytest.mark.parametrize("lineno,message", literal_error_messages())
    def test_message_is_a_real_sentence(self, lineno, message):
        assert len(message) >= 40, f"video.py:{lineno} is too terse to explain anything: {message!r}"
        assert message[0].isupper(), f"video.py:{lineno} should start as a sentence: {message!r}"
        assert message.rstrip().endswith(('.', '!')), f"video.py:{lineno} needs an end stop: {message!r}"

    @pytest.mark.parametrize("lineno,message", literal_error_messages())
    def test_message_does_not_echo_a_url_or_a_code(self, lineno, message):
        assert 'http://' not in message and 'https://' not in message, (
            f"video.py:{lineno} echoes a URL back at the user: {message!r}"
        )
        assert not (message.startswith('[') and ']' in message[:32]), (
            f"video.py:{lineno} leads with a bracketed error code: {message!r}"
        )


class TestNoUsableSignal:
    """
    The fail-fast gate. By the time it is asked, a caption holding a complete recipe has
    already returned a success from parse(), so the only question left is whether the
    narration gave us anything usable.
    """

    @pytest.fixture
    def parser(self):
        return VideoParser(timeout=1)

    def test_a_usable_transcript_is_signal(self, parser):
        audio = {'success': True, 'transcript': 'Add two cups of flour, then fold in butter.',
                 'recipe_data': {'name': 'Shortbread'}}
        assert parser._no_usable_signal(audio) is False

    def test_too_little_audio_is_not_signal(self, parser):
        assert parser._no_usable_signal(
            {'success': False, 'confidence': 0.0, 'reason': 'insufficient_audio', 'transcript': ''}
        ) is True

    def test_speech_that_is_not_a_recipe_is_not_signal(self, parser):
        # The real case that exposed this. Whisper succeeds, the text is genuine, and it is
        # song lyrics. Reading the transcript would call this narration; reading `success`
        # does not, which is the whole reason the gate keys on `success`.
        assert parser._no_usable_signal({
            'success': False,
            'confidence': 0.2,
            'reason': 'not_a_recipe',
            'transcript': 'We never forget. Long has gone by. We never forget.',
        }) is True

    def test_a_missing_success_key_is_treated_as_no_signal(self, parser):
        # Fail closed. A malformed result must not be mistaken for narration and let a
        # guessed recipe through.
        assert parser._no_usable_signal({}) is True


class TestIsCookable:
    """
    The output gate. Quantities are what separates a recipe that was READ from one that was
    inferred from pictures, and unlike every input-side signal it does not move between runs.
    """

    @pytest.fixture
    def parser(self):
        return VideoParser(timeout=1)

    def test_a_real_recipe_is_cookable(self, parser):
        assert parser._is_cookable({'ingredients': [
            '2 large chicken breasts', '1 tbsp paprika', '3/4 cup freshly grated Parmesan',
        ]}) is True

    def test_a_guessed_recipe_is_not(self, parser):
        # Verbatim from the live run that prompted this gate: seven ingredients, no amounts.
        assert parser._is_cookable({'ingredients': [
            'Extra virgin olive oil (amount not specified)',
            'Black pepper (amount not specified)',
            'Garlic (amount not specified)',
            'Paprika (amount not specified)',
            'Breadcrumbs (amount not specified)',
            'Ground beef patties (amount not specified)',
            'Burger buns (amount not specified)',
        ]}) is False

    def test_no_ingredients_at_all_is_not_cookable(self, parser):
        assert parser._is_cookable({'ingredients': []}) is False
        assert parser._is_cookable({}) is False

    def test_a_few_missing_amounts_is_still_cookable(self, parser):
        # Real recipes say "salt to taste". The gate is for recipes where NOTHING was read,
        # not for ones with a couple of loose lines.
        assert parser._is_cookable({'ingredients': [
            '500g beef mince', '2 cloves garlic', 'Salt to taste',
            'Black pepper (amount not specified)',
        ]}) is True

    def test_one_quantified_ingredient_is_enough_to_pass(self, parser):
        # Deliberately permissive at the boundary: the gate exists to catch total absence of
        # quantities, and a thin-but-real recipe should not be thrown away by it.
        assert parser._is_cookable({'ingredients': [
            '1 cup rice', 'Water (amount not specified)',
        ]}) is True
