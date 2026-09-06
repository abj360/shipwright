#!/usr/bin/env python3
"""
test_transcript_redaction.py --- asserts provider keys never reach a saved transcript

Contains:
    test_known_key_is_removed(): a registered key does not survive redaction
    test_anthropic_shaped_key_is_removed(): an unregistered key is still caught
    test_surrounding_text_is_preserved(): redaction leaves other text intact
    test_openai_shaped_key_is_removed(): an OpenAI-shaped key is caught too
    test_empty_secret_is_ignored(): an empty registered value changes nothing
    test_transcript_observation_is_scrubbed(): a key in an observation is removed
    test_transcript_tool_args_are_scrubbed(): a key in tool arguments is removed
"""

from tui.redaction import REDACTION_PLACEHOLDER, redact_secrets, redact_transcript

ANTHROPIC_KEY = "sk-ant-api03-ZZm9QvW2ktLpR7xNs4Hb1TcUeY6gJd0A"


def test_known_key_is_removed() -> None:
    """Asserts a credential the caller registered is stripped from the text."""
    transcript = f"exported ANTHROPIC_API_KEY={ANTHROPIC_KEY} before the run"

    cleaned = redact_secrets(transcript, [ANTHROPIC_KEY])

    assert ANTHROPIC_KEY not in cleaned
    assert REDACTION_PLACEHOLDER in cleaned


def test_anthropic_shaped_key_is_removed() -> None:
    """Asserts a key-shaped value is stripped even when it was never registered."""
    cleaned = redact_secrets(f"pasted {ANTHROPIC_KEY} into the panel")

    assert ANTHROPIC_KEY not in cleaned


def test_surrounding_text_is_preserved() -> None:
    """Asserts redaction only removes the credential, not the text around it."""
    cleaned = redact_secrets(f"step 3 failed: {ANTHROPIC_KEY} rejected", [ANTHROPIC_KEY])

    assert cleaned.startswith("step 3 failed: ")
    assert cleaned.endswith(" rejected")


def test_openai_shaped_key_is_removed() -> None:
    """Asserts an OpenAI-shaped credential is stripped from the text."""
    openai_key = "sk-Xa91LmQr7TbV3wKd8ZnH2yPcE5uJf0Rg"

    cleaned = redact_secrets(f"OPENAI_API_KEY={openai_key}")

    assert openai_key not in cleaned


def test_empty_secret_is_ignored() -> None:
    """Asserts an empty registered value does not shred the surrounding text."""
    cleaned = redact_secrets("nothing secret here", [""])

    assert cleaned == "nothing secret here"


def test_transcript_observation_is_scrubbed() -> None:
    """Asserts a credential inside a step observation never reaches the saved file."""
    entries = [{"thought": "checking the key", "observation": f"env: {ANTHROPIC_KEY}"}]

    cleaned = redact_transcript(entries, [ANTHROPIC_KEY])

    assert ANTHROPIC_KEY not in cleaned[0]["observation"]
    assert cleaned[0]["thought"] == "checking the key"


def test_transcript_tool_args_are_scrubbed() -> None:
    """Asserts a credential passed as a tool argument is removed as well."""
    entries = [{"thought": "run it", "tool_args": {"command": f"export K={ANTHROPIC_KEY}"}}]

    cleaned = redact_transcript(entries, [ANTHROPIC_KEY])

    assert ANTHROPIC_KEY not in cleaned[0]["tool_args"]["command"]
