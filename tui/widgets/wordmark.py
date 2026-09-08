#!/usr/bin/env python3
"""
wordmark.py --- block-capital project wordmark drawn in the brand blue

Contains:
    PROJECT_NAME: the word the boot screen spells out
    GLYPH_HEIGHT: how many rows tall one block letter is
    GLYPH_SEPARATOR: text placed between two adjacent glyphs
    BLOCK_FONT: one block-capital glyph per letter of the project name
    render_word(): renders a word as block-capital rows
    WORDMARK_LINES: the ASCII art shown on the boot screen
    Wordmark: boot-screen widget drawing the wordmark
    Wordmark.style_for_palette(): the colour the wordmark is drawn in
    Wordmark.render(): renders every wordmark line
"""

from rich.text import Text
from textual.widgets import Static

from tui.theme import BRAND_BLUE, Palette, palette_for

PROJECT_NAME = "SHIPWRIGHT"
GLYPH_HEIGHT = 5
GLYPH_SEPARATOR = " "
BLOCK_FONT: dict[str, tuple[str, ...]] = {
    "S": ("█████", "█    ", "█████", "    █", "█████"),
    "H": ("█   █", "█   █", "█████", "█   █", "█   █"),
    "I": ("█████", "  █  ", "  █  ", "  █  ", "█████"),
    "P": ("█████", "█   █", "█████", "█    ", "█    "),
    "W": ("█   █", "█   █", "█ █ █", "██ ██", "█   █"),
    "R": ("█████", "█   █", "█████", "█  █ ", "█   █"),
    "G": ("█████", "█    ", "█  ██", "█   █", "█████"),
    "T": ("█████", "  █  ", "  █  ", "  █  ", "  █  "),
}


def render_word(word: str) -> tuple[str, ...]:
    """Renders a word as block-capital rows.

    Args:
        word: Upper-case word whose letters all appear in BLOCK_FONT.

    Returns:
        rows: One string per row of the rendered word.

    Raises:
        KeyError: A letter of the word has no glyph in BLOCK_FONT.
    """
    glyphs = [BLOCK_FONT[letter] for letter in word]
    return tuple(
        GLYPH_SEPARATOR.join(glyph[row] for glyph in glyphs) for row in range(GLYPH_HEIGHT)
    )


WORDMARK_LINES = render_word(PROJECT_NAME)


class Wordmark(Static):
    """Draws the block-capital wordmark in the brand blue on the boot screen.

    Attributes:
        palette: Palette deciding whether the wordmark is coloured at all.
    """

    def __init__(self, palette: Palette | None = None, id: str | None = None) -> None:
        """Builds the wordmark for one terminal's colour capability.

        Args:
            palette: Colours to render with; detected from the terminal when None.
            id: Element id, so the layout can target the mark in CSS.
        """
        super().__init__(id=id)
        self.palette = palette_for() if palette is None else palette

    def style_for_palette(self) -> str:
        """Returns the colour the wordmark is drawn in.

        Returns:
            style: The brand blue, or empty on a terminal without colour.
        """
        return BRAND_BLUE if self.palette.accent else ""

    def render(self) -> Text:
        """Renders every wordmark line in a single flat brand colour.

        Returns:
            rendered: The wordmark as one block of brand-coloured text.
        """
        style = self.style_for_palette()
        block = Text()
        for line in WORDMARK_LINES:
            block.append(line, style=style)
            block.append("\n")
        return block
