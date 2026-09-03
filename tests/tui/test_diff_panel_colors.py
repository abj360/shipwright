#!/usr/bin/env python3
"""
test_diff_panel_colors.py --- golden tests pinning the diff panel's colour scheme

Contains:
    GOLDEN_DARK: the colour each line kind must render in on a colour terminal
    test_dark_scheme_matches_golden(): every kind keeps its documented colour
    test_add_delete_and_hunk_are_distinct(): the three colours never collide
    test_monochrome_terminal_gets_no_colour(): NO_COLOR yields empty tokens
"""

from tui.theme import DARK, MONOCHROME
from tui.widgets.diff_panel import DiffPanel, LineKind

GOLDEN_DARK = {
    LineKind.ADD: "#2ea043",
    LineKind.DELETE: "#f85149",
    LineKind.HUNK: "#8b949e",
    LineKind.CONTEXT: "#c9d1d9",
}


def test_dark_scheme_matches_golden() -> None:
    """Asserts each line kind renders in exactly its documented colour."""
    panel = DiffPanel("", palette=DARK)

    rendered = {kind: panel.color_for(kind) for kind in GOLDEN_DARK}

    assert rendered == GOLDEN_DARK


def test_add_delete_and_hunk_are_distinct() -> None:
    """Asserts the three diff colours stay visually distinct from each other."""
    panel = DiffPanel("", palette=DARK)

    three = {panel.color_for(k) for k in (LineKind.ADD, LineKind.DELETE, LineKind.HUNK)}

    assert len(three) == 3


def test_monochrome_terminal_gets_no_colour() -> None:
    """Asserts a colourless terminal is handed empty colour tokens."""
    panel = DiffPanel("", palette=MONOCHROME)

    assert panel.color_for(LineKind.ADD) == ""
    assert panel.color_for(LineKind.DELETE) == ""
