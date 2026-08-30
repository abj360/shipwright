#!/usr/bin/env python3
"""
redaction.py --- strips provider credentials out of text before it is stored

Contains:
    REDACTION_PLACEHOLDER: text substituted in place of a credential
    SECRET_PATTERNS: shapes that look like a provider API key
    redact_secrets(): removes known and key-shaped secrets from text
"""

import re
from collections.abc import Iterable

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
