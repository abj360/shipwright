#!/usr/bin/env python3
"""
context_bar.py --- compact readout of context fullness and the active model

Contains:
    RING_GLYPHS: the fill states the context ring cycles through
    WARN_AT / CRITICAL_AT: fractions at which the ring changes colour
    ring_for(): picks the glyph representing one fullness fraction
    ContextBar: the bar drawn under the composer
    ContextBar.set_usage(): records how full the context is
    ContextBar.set_model(): records which model is answering
    ContextBar.render_text(): renders the ring, the percentage, and the model
"""

from textual.widgets import Static

from tui.theme import Palette, palette_for

RING_GLYPHS = ("○", "◔", "◑", "◕", "●")
WARN_AT = 0.70
CRITICAL_AT = 0.90


def ring_for(usage: float) -> str:
    """Picks the glyph representing one fullness fraction.

    Args:
        usage: How full the context is, between 0 and 1.

    Returns:
        glyph: Ring glyph for that fraction.
    """
    clamped = min(1.0, max(0.0, usage))
    index = round(clamped * (len(RING_GLYPHS) - 1))
    return RING_GLYPHS[index]


class ContextBar(Static):
    """Draws context fullness and the active model under the composer.

    Attributes:
        usage: How full the working context is, between 0 and 1.
        model_label: Provider and model currently answering.
        palette: Colours the bar draws from.
    """

    def __init__(self, model_label: str = "", palette: Palette | None = None) -> None:
        """Builds the bar for one model, showing an empty context.

        Args:
            model_label: Provider and model currently answering.
            palette: Colours to draw from; detected from the terminal when None.
        """
        super().__init__()
        self.usage = 0.0
        self.model_label = model_label
        self.palette: Palette = palette_for() if palette is None else palette

    def colour_for_usage(self) -> str:
        """Returns the colour the ring is drawn in.

        Returns:
            colour: Muted while there is room, warning then error as it fills.
        """
        if self.usage >= CRITICAL_AT:
            return self.palette.status_error
        if self.usage >= WARN_AT:
            return self.palette.hunk
        return self.palette.accent

    def render_text(self) -> str:
        """Renders the ring, the percentage, and the model.

        Returns:
            line: Compact readout for the bar under the composer.
        """
        percent = int(round(self.usage * 100))
        parts = [f"{ring_for(self.usage)} {percent}% context"]
        if self.model_label:
            parts.append(self.model_label)
        return "   ".join(parts)

    def set_usage(self, usage: float) -> None:
        """Records how full the context is and repaints.

        Args:
            usage: Fraction of the working context in use.
        """
        self.usage = usage
        self.styles.color = self.colour_for_usage() or None
        self.update(self.render_text())

    def set_model(self, model_label: str) -> None:
        """Records which model is answering and repaints.

        Args:
            model_label: Provider and model currently answering.
        """
        self.model_label = model_label
        self.update(self.render_text())
