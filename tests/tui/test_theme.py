#!/usr/bin/env python3
"""
test_theme.py --- covers terminal colour-capability detection

Contains:
    test_color_terminal_gets_the_dark_palette(): a normal terminal keeps colour
    test_no_color_forces_monochrome(): NO_COLOR wins regardless of TERM
    test_dumb_terminal_forces_monochrome(): TERM=dumb drops colour
    test_missing_term_forces_monochrome(): an unset TERM drops colour
"""

from tui.theme import DARK, MONOCHROME, palette_for, supports_color


def test_color_terminal_gets_the_dark_palette() -> None:
    """Asserts an ordinary colour terminal keeps the full palette."""
    assert supports_color({"TERM": "xterm-256color"}) is True
    assert palette_for({"TERM": "xterm-256color"}) is DARK


def test_no_color_forces_monochrome() -> None:
    """Asserts NO_COLOR drops colour even on a capable terminal."""
    environ = {"TERM": "xterm-256color", "NO_COLOR": ""}

    assert supports_color(environ) is False
    assert palette_for(environ) is MONOCHROME


def test_dumb_terminal_forces_monochrome() -> None:
    """Asserts a terminal reporting TERM=dumb is sent no colour."""
    assert palette_for({"TERM": "dumb"}) is MONOCHROME


def test_missing_term_forces_monochrome() -> None:
    """Asserts an environment with no TERM at all is treated as colourless."""
    assert palette_for({}) is MONOCHROME
