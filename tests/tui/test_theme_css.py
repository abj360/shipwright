#!/usr/bin/env python3
"""
test_theme_css.py --- covers translating the palette into Textual design tokens

Contains:
    test_dark_palette_fills_every_token(): a colour palette emits all tokens
    test_panel_tokens_match_the_palette(): panel and border tokens are carried over
    test_monochrome_emits_nothing(): a blank palette falls back to Textual defaults
"""

from tui.theme import CSS_VARIABLE_NAMES, DARK, MONOCHROME, css_variables


def test_dark_palette_fills_every_token() -> None:
    """Asserts a full colour palette produces every documented design token."""
    variables = css_variables(DARK)

    assert set(variables) == set(CSS_VARIABLE_NAMES)


def test_panel_tokens_match_the_palette() -> None:
    """Asserts the panel and border tokens carry the palette's own values."""
    variables = css_variables(DARK)

    assert variables["panel"] == DARK.panel_background
    assert variables["panel-border"] == DARK.panel_border
    assert variables["border-subtle"] == DARK.border_subtle


def test_monochrome_emits_nothing() -> None:
    """Asserts a colourless palette emits no tokens rather than empty ones."""
    assert css_variables(MONOCHROME) == {}
