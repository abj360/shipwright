#!/usr/bin/env python3
"""
test_wordmark.py --- covers the boot-screen wordmark and its brand colour

Contains:
    test_wordmark_spells_the_project_name(): the art is SHIPWRIGHT, letter by letter
    test_project_name_is_upper_case(): the wordmark is drawn in capitals
    test_every_row_is_the_same_width(): the block letters line up in a rectangle
    test_render_word_handles_a_single_letter(): one letter reproduces its glyph
    test_wordmark_uses_the_brand_blue(): the only colour used is the brand token
    test_monochrome_terminal_gets_no_colour(): a colourless terminal gets no style
    test_render_covers_every_line(): the rendered block carries all five rows
"""

from tui.theme import BRAND_BLUE, DARK, MONOCHROME
from tui.widgets.wordmark import (
    BLOCK_FONT,
    GLYPH_HEIGHT,
    PROJECT_NAME,
    WORDMARK_LINES,
    Wordmark,
    render_word,
)


def test_wordmark_spells_the_project_name() -> None:
    """Asserts the boot art is the word SHIPWRIGHT, checked letter by letter."""
    assert PROJECT_NAME == "SHIPWRIGHT"

    for position, letter in enumerate(PROJECT_NAME):
        column_start = position * (len(BLOCK_FONT[letter][0]) + 1)
        for row in range(GLYPH_HEIGHT):
            width = len(BLOCK_FONT[letter][row])
            sliced = WORDMARK_LINES[row][column_start : column_start + width]
            assert sliced == BLOCK_FONT[letter][row], (letter, row)


def test_project_name_is_upper_case() -> None:
    """Asserts the wordmark is drawn in capitals, as the boot screen expects."""
    assert PROJECT_NAME.isupper()
    assert set(PROJECT_NAME) <= set(BLOCK_FONT)


def test_every_row_is_the_same_width() -> None:
    """Asserts every rendered row is the same width so the block stays rectangular."""
    widths = {len(row) for row in WORDMARK_LINES}

    assert len(WORDMARK_LINES) == GLYPH_HEIGHT
    assert len(widths) == 1


def test_render_word_handles_a_single_letter() -> None:
    """Asserts rendering one letter reproduces that letter's glyph exactly."""
    assert render_word("T") == BLOCK_FONT["T"]


def test_wordmark_uses_the_brand_blue() -> None:
    """Asserts the wordmark is drawn in the brand blue and nothing else."""
    wordmark = Wordmark(palette=DARK)

    assert wordmark.style_for_palette() == BRAND_BLUE
    assert BRAND_BLUE == "#2f81f7"

    styles = {str(span.style) for span in wordmark.render().spans}
    assert styles <= {BRAND_BLUE, ""}


def test_monochrome_terminal_gets_no_colour() -> None:
    """Asserts a terminal without colour is handed no style at all."""
    assert Wordmark(palette=MONOCHROME).style_for_palette() == ""


def test_render_covers_every_line() -> None:
    """Asserts the rendered block contains each row of the wordmark."""
    block = Wordmark(palette=DARK).render().plain

    for line in WORDMARK_LINES:
        assert line in block
