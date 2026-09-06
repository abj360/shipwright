#!/usr/bin/env python3
"""
redaction.py --- strips provider credentials out of text before it is stored

Contains:
    REDACTION_PLACEHOLDER: text substituted in place of a credential
    SECRET_PATTERNS: shapes that look like a provider API key
    redact_secrets(): removes known and key-shaped secrets from text
    REDACTED_FIELDS: transcript fields scrubbed before a transcript is saved
    redact_transcript(): scrubs every credential out of a saved transcript
"""

import re
from collections.abc import Iterable
from typing import Any

REDACTION_PLACEHOLDER = "[redacted]"
SECRET_PATTERNS = (
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
)


def redact_secrets(text: str, known_secrets: Iterable[str] = ()) -> str:
    """Removes credentials from text so it is safe to persist.

    Known values are replaced first, then anything still shaped like a provider
    key, so a credential the caller never registered is caught as well.

    Args:
        text: Text about to be written to a transcript or log.
        known_secrets: Credential values the caller already holds.

    Returns:
        cleaned: Text with every recognized credential replaced.
    """
    cleaned = text
    for secret in known_secrets:
        if not secret:
            continue
        cleaned = cleaned.replace(secret, REDACTION_PLACEHOLDER)
    for pattern in SECRET_PATTERNS:
        cleaned = pattern.sub(REDACTION_PLACEHOLDER, cleaned)
    return cleaned


REDACTED_FIELDS = ("thought", "observation")


def redact_transcript(
    entries: list[dict[str, Any]],
    known_secrets: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """Scrubs credentials out of every step of a transcript before it is saved.

    Both the reasoning text and the tool arguments are scrubbed, because a key
    pasted into the composer reaches the transcript through either one.

    Args:
        entries: Transcript steps as they would be serialized to JSON.
        known_secrets: Credential values the caller already holds.

    Returns:
        cleaned: Transcript steps with every recognized credential removed.
    """
    secrets = list(known_secrets)
    cleaned: list[dict[str, Any]] = []
    for entry in entries:
        step = dict(entry)
        for field in REDACTED_FIELDS:
            if isinstance(step.get(field), str):
                step[field] = redact_secrets(step[field], secrets)
        args = step.get("tool_args")
        if isinstance(args, dict):
            step["tool_args"] = {
                key: redact_secrets(value, secrets) if isinstance(value, str) else value
                for key, value in args.items()
            }
        cleaned.append(step)
    return cleaned
