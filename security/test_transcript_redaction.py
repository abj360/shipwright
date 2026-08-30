#!/usr/bin/env python3
"""
test_transcript_redaction.py --- asserts provider keys never reach a saved transcript

Contains:
    test_known_key_is_removed(): a registered key does not survive redaction
    test_anthropic_shaped_key_is_removed(): an unregistered key is still caught
    test_surrounding_text_is_preserved(): redaction leaves other text intact
"""

from tui.redaction import REDACTION_PLACEHOLDER, redact_secrets

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
