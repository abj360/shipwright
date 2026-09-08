#!/usr/bin/env python3
"""
test_llm_client_safety.py --- covers empty replies and credential disclosure

Pins two failures seen in a live run: a reply carrying no content blocks
crashed the agent mid-run, and the crash report printed the API key in full
because it was held in a plain header dict.

Contains:
    test_empty_content_yields_empty_text(): a reply with no blocks does not raise
    test_text_blocks_are_joined(): a multi-block reply keeps all of its text
    test_non_text_blocks_are_skipped(): thinking blocks contribute no text
    test_empty_openai_choices_yield_empty_text(): the same for OpenAI shapes
    test_auth_repr_redacts_the_credential(): the auth object never renders it
    test_credential_never_reaches_a_traceback(): a crash cannot disclose the key
"""

import io

from rich.console import Console
from rich.traceback import Traceback

from agent.llm_client import (
    AnthropicLLMClient,
    Message,
    _anthropic_text,
    _openai_text,
    _ProviderAuth,
)

# Referenced, never assigned inside a test, so it is a global rather than a
# frame local: the fixture itself must not be what shows up in the traceback.
_SECRET = "sk-ant-api03-ZWSdUNwxONhCkxb20zJDZUvgUo-zQ9kkTPZy0_mOMeaLghblhlFFm"
_DEAD_ENDPOINT = "http://127.0.0.1:9/v1/messages"

# The exact body that ended a live run: end_turn with nothing in content.
EMPTY_REPLY = {
    "model": "claude-haiku-4-5-20251001",
    "content": [],
    "stop_reason": "end_turn",
    "usage": {"input_tokens": 5209, "output_tokens": 3},
}


def test_empty_content_yields_empty_text() -> None:
    """Asserts a reply carrying no content blocks is empty, not an IndexError."""
    assert _anthropic_text(EMPTY_REPLY) == ""


def test_text_blocks_are_joined() -> None:
    """Asserts every text block is kept, not just the first one."""
    reply = {"content": [{"type": "text", "text": "hello "}, {"type": "text", "text": "world"}]}

    assert _anthropic_text(reply) == "hello world"


def test_non_text_blocks_are_skipped() -> None:
    """Asserts a non-text block contributes nothing to the completion text."""
    reply = {"content": [{"type": "thinking", "text": "hmm"}, {"type": "text", "text": "answer"}]}

    assert _anthropic_text(reply) == "answer"


def test_empty_openai_choices_yield_empty_text() -> None:
    """Asserts the OpenAI shapes degrade the same way rather than raising."""
    assert _openai_text({"choices": []}) == ""
    assert _openai_text({"choices": [{"message": {"content": None}}]}) == ""


def test_auth_repr_redacts_the_credential() -> None:
    """Asserts the auth object names its header but never its secret."""
    rendered = repr(_ProviderAuth("x-api-key", _SECRET))

    assert _SECRET not in rendered
    assert "<redacted>" in rendered
    assert "x-api-key" in rendered


def test_credential_never_reaches_a_traceback() -> None:
    """Asserts a failure in the request path cannot disclose the API key.

    The crash handler renders every frame local, so this drives a real failure
    through the request path and inspects what would have been printed.
    """
    client = AnthropicLLMClient(api_key=_SECRET, base_url=_DEAD_ENDPOINT)

    try:
        client.complete([Message(role="user", content="hi")], "system")
    except Exception:
        buffer = io.StringIO()
        Console(file=buffer, width=200).print(Traceback(show_locals=True))
        rendered = buffer.getvalue()
    else:  # pragma: no cover - the dead endpoint always fails
        raise AssertionError("expected the request to fail")

    assert len(rendered) > 0
    assert _SECRET not in rendered
