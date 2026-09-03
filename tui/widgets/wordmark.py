#!/usr/bin/env python3
"""
wordmark.py --- ASCII wordmark drawn with a horizontal colour gradient

Contains:
    WORDMARK_LINES: the ASCII art shown on the boot screen
    GRADIENT_START / GRADIENT_END: the two colours the gradient runs between
    parse_hex(): splits a hex colour into its channels
    to_hex(): renders channels back into a hex colour
    blend(): mixes two colours at a given ratio
    _ratio_at(): position of one column within the gradient
    gradient_line(): renders one line with the gradient applied across it
    Wordmark: boot-screen widget drawing the gradient wordmark
    Wordmark.render(): renders every wordmark line
"""

from rich.text import Text
from textual.widgets import Static

WORDMARK_LINES = (
    " ___ _  _ ___ ___ _    _ ___ ___ ___ _  _ _____ ",
    "/ __| || |_ _| _ \\ \\  / / _ \\_ _/ __| || |_   _|",
    "\\__ \\ __ || ||  _/\\ \\/ /| " + "   /| | (_ | __ | | |  ",
    "|___/_||_|___|_|   \\__/ |_|_\\___|\\___|_||_| |_|  ",
)
GRADIENT_START = "#6cb6ff"
GRADIENT_END = "#d2a8ff"


def parse_hex(color: str) -> tuple[int, int, int]:
    """Splits a hex colour into its red, green, and blue channels.

    Args:
        color: Colour written as #rrggbb.

    Returns:
        channels: Red, green, and blue values between 0 and 255.
    """
    raw = color.lstrip("#")
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def to_hex(channels: tuple[int, int, int]) -> str:
    """Renders red, green, and blue channels back into a hex colour.

    Args:
        channels: Red, green, and blue values between 0 and 255.

    Returns:
        color: Colour written as #rrggbb.
    """
    return "#{:02x}{:02x}{:02x}".format(*channels)


def blend(start: str, end: str, ratio: float) -> str:
    """Mixes two colours at the given ratio.

    Args:
        start: Colour returned when the ratio is 0.
        end: Colour returned when the ratio is 1.
        ratio: Position between the two colours, clamped to 0..1.

    Returns:
        color: Blended colour written as #rrggbb.
    """
    clamped = min(1.0, max(0.0, ratio))
    first = parse_hex(start)
    second = parse_hex(end)
    mixed = tuple(round(a + (b - a) * clamped) for a, b in zip(first, second, strict=True))
    return to_hex(mixed)  # type: ignore[arg-type]


def _ratio_at(index: int, width: int) -> float:
    """Computes where one column sits within the gradient.

    Args:
        index: Zero-based column being rendered.
        width: Total number of columns on the line.

    Returns:
        ratio: Position between 0 and 1 across the gradient.
    """
    return index / (width - 1)


def gradient_line(text: str, start: str = GRADIENT_START, end: str = GRADIENT_END) -> Text:
    """Renders one line with the gradient applied across its width.

    Args:
        text: Line of the wordmark to colour.
        start: Colour the gradient begins at.
        end: Colour the gradient finishes at.

    Returns:
        rendered: Rich text carrying one colour span per character.
    """
    rendered = Text()
    for index, character in enumerate(text):
        rendered.append(character, style=blend(start, end, _ratio_at(index, len(text))))
    return rendered


class Wordmark(Static):
    """Draws the ASCII wordmark under a horizontal gradient on the boot screen."""

    def render(self) -> Text:
        """Renders every wordmark line with the gradient applied.

        Returns:
            rendered: The wordmark as a single gradient-coloured block.
        """
        block = Text()
        for line in WORDMARK_LINES:
            block.append_text(gradient_line(line))
            block.append("\n")
        return block
