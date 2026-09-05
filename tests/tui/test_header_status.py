#!/usr/bin/env python3
"""
test_header_status.py --- covers the header's reactive client-status field

Contains:
    test_provider_only_label(): a default model shows the provider alone
    test_pinned_model_label(): a pinned model is shown beside the provider
    test_switching_status_updates_the_line(): reassigning repaints the bar text
    test_status_is_immutable(): the status cannot be mutated in place
    test_blank_model_is_treated_as_default(): an empty model shows provider alone
"""

from pathlib import Path

import pytest

from tui.screens.header import ClientStatus, HeaderBar


def test_provider_only_label() -> None:
    """Asserts a provider running its default model shows just the provider."""
    assert ClientStatus("anthropic").label() == "anthropic"


def test_pinned_model_label() -> None:
    """Asserts a pinned model is rendered beside its provider."""
    assert ClientStatus("openai", "gpt-4.1").label() == "openai/gpt-4.1"


def test_switching_status_updates_the_line(tmp_path: Path) -> None:
    """Asserts reassigning the status changes what the bar renders."""
    bar = HeaderBar(tmp_path, "anthropic")
    before = bar.render_line_text()

    bar.client_status = ClientStatus("openai", "gpt-4.1")

    assert "anthropic" in before
    assert "openai/gpt-4.1" in bar.render_line_text()


def test_status_is_immutable() -> None:
    """Asserts the status is frozen, so a switch replaces it rather than edits it."""
    status = ClientStatus("anthropic")

    with pytest.raises(AttributeError):
        status.provider = "openai"  # type: ignore[misc]


def test_blank_model_is_treated_as_default() -> None:
    """Asserts an empty model string is treated as 'provider default', not shown."""
    assert ClientStatus("anthropic", "").label() == "anthropic"
