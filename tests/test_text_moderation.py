"""
Unit tests for reported-text moderation (advisory verdict shown to the moderator).

The OpenAI calls are mocked — these cover the contract the Go backend depends on:
the verdict is always one of three values, a broken response degrades to "uncertain"
rather than a silent "safe", and a classifier outage does not fail the call.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from services.text_moderator import TextModerator


def _chat_response(payload):
    """Shape a fake chat.completions response carrying `payload` as JSON."""
    message = MagicMock()
    message.content = json.dumps(payload) if isinstance(payload, dict) else payload
    choice = MagicMock()
    choice.message = message
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _moderation_response(scores):
    result = MagicMock()
    result.category_scores = scores
    resp = MagicMock()
    resp.results = [result]
    return resp


@pytest.fixture
def moderator():
    """A TextModerator with a stubbed OpenAI client."""
    with patch("services.text_moderator.settings") as settings, patch(
        "services.text_moderator.openai.OpenAI"
    ) as client_cls:
        settings.OPENAI_API_KEY = "test-key"
        instance = TextModerator()
        instance.client = client_cls.return_value
        instance.client.moderations.create.return_value = _moderation_response({})
        yield instance


class TestScreenText:
    """The verdict contract the Go side relies on."""

    def test_unsafe_verdict_passes_through(self, moderator):
        moderator.client.chat.completions.create.return_value = _chat_response(
            {"verdict": "unsafe", "categories": ["harassment"], "reason": "Insults the cook directly."}
        )

        result = moderator.screen_text("you are worthless", "comment on a cooking post")

        assert result["verdict"] == "unsafe"
        assert result["categories"] == ["harassment"]
        assert result["reason"] == "Insults the cook directly."

    def test_safe_verdict_passes_through(self, moderator):
        moderator.client.chat.completions.create.return_value = _chat_response(
            {"verdict": "safe", "categories": [], "reason": "Ordinary criticism of a recipe."}
        )

        result = moderator.screen_text("this recipe is trash lol", "comment on a cooking post")

        assert result["verdict"] == "safe"
        assert result["categories"] == []

    @pytest.mark.parametrize("verdict", ["banana", "", None, "SAFE-ish"])
    def test_unrecognized_verdict_becomes_uncertain(self, moderator, verdict):
        """Never a silent 'safe' — an unreadable answer means a human decides."""
        moderator.client.chat.completions.create.return_value = _chat_response(
            {"verdict": verdict, "categories": [], "reason": ""}
        )

        assert moderator.screen_text("something", "")["verdict"] == "uncertain"

    def test_verdict_case_and_whitespace_normalized(self, moderator):
        moderator.client.chat.completions.create.return_value = _chat_response(
            {"verdict": "  UNSAFE  ", "categories": [], "reason": ""}
        )

        assert moderator.screen_text("something", "")["verdict"] == "unsafe"

    def test_malformed_categories_become_empty_list(self, moderator):
        moderator.client.chat.completions.create.return_value = _chat_response(
            {"verdict": "safe", "categories": "harassment", "reason": ""}
        )

        assert moderator.screen_text("something", "")["categories"] == []

    def test_empty_text_raises_value_error(self, moderator):
        """A permanent error: the router turns this into a 400, not a retry."""
        with pytest.raises(ValueError):
            moderator.screen_text("   ", "comment on a cooking post")

    def test_long_text_is_truncated_before_the_call(self, moderator):
        moderator.client.chat.completions.create.return_value = _chat_response(
            {"verdict": "safe", "categories": [], "reason": ""}
        )

        moderator.screen_text("a" * 20000, "user recipe")

        sent = moderator.client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        assert len(sent) < 20000


class TestClassifierSignal:
    """The free moderation endpoint is evidence for the model, never a hard gate."""

    def test_scores_are_passed_to_the_model(self, moderator):
        moderator.client.moderations.create.return_value = _moderation_response(
            {"harassment": 0.97, "hate": 0.4, "violence": 0.001}
        )
        moderator.client.chat.completions.create.return_value = _chat_response(
            {"verdict": "unsafe", "categories": ["harassment"], "reason": "Targets another user."}
        )

        moderator.screen_text("...", "comment on a cooking post")

        sent = moderator.client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        assert "harassment 0.97" in sent
        assert "violence" not in sent  # below the noise floor

    def test_classifier_outage_does_not_fail_the_call(self, moderator):
        moderator.client.moderations.create.side_effect = RuntimeError("moderation api down")
        moderator.client.chat.completions.create.return_value = _chat_response(
            {"verdict": "safe", "categories": [], "reason": "Nothing wrong here."}
        )

        result = moderator.screen_text("add the cumin", "comment on a cooking post")

        assert result["verdict"] == "safe"
        sent = moderator.client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        assert "unavailable" in sent

    def test_context_is_named_for_the_model(self, moderator):
        moderator.client.chat.completions.create.return_value = _chat_response(
            {"verdict": "safe", "categories": [], "reason": ""}
        )

        moderator.screen_text("something", "recipe tip")

        sent = moderator.client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        assert "recipe tip" in sent
