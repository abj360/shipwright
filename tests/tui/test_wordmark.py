#!/usr/bin/env python3
"""
test_wordmark.py --- covers the boot-screen wordmark gradient

Contains:
    test_blend_returns_each_end(): ratio 0 and 1 return the endpoint colours
    test_blend_midpoint_is_between(): the midpoint sits between both channels
    test_gradient_line_colours_every_character(): one span per character
    test_wordmark_renders_every_line(): the block carries all four lines
"""

from tui.widgets.wordmark import (
    GRADIENT_END,
    GRADIENT_START,
    WORDMARK_LINES,
    Wordmark,
    blend,
    gradient_line,
    parse_hex,
)


def test_blend_returns_each_end() -> None:
    """Asserts a ratio of 0 and of 1 return the two endpoint colours."""
    assert blend(GRADIENT_START, GRADIENT_END, 0.0) == GRADIENT_START
    assert blend(GRADIENT_START, GRADIENT_END, 1.0) == GRADIENT_END


def test_blend_midpoint_is_between() -> None:
    """Asserts the midpoint colour sits between both endpoints on every channel."""
    low = parse_hex(GRADIENT_START)
    high = parse_hex(GRADIENT_END)
    middle = parse_hex(blend(GRADIENT_START, GRADIENT_END, 0.5))

    for channel in range(3):
        assert min(low[channel], high[channel]) <= middle[channel]
        assert middle[channel] <= max(low[channel], high[channel])


def test_gradient_line_colours_every_character() -> None:
    """Asserts every character of a line gets its own colour span."""
    rendered = gradient_line("shipwright")

    assert len(rendered.plain) == len("shipwright")
    assert len(rendered.spans) == len("shipwright")


def test_wordmark_renders_every_line() -> None:
    """Asserts the rendered block contains each line of the wordmark."""
    block = Wordmark().render().plain

    for line in WORDMARK_LINES:
        assert line in block
