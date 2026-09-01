#!/usr/bin/env python3
"""
footer.py --- keybinding hint bar generated from the app's own bindings

Contains:
    MAX_HINTS: how many hints fit on one line before the rest are dropped
    HINT_SEPARATOR: text placed between two rendered hints
    EMPTY_BAR: what an app with nothing bound renders
    render_hint(): renders one binding as a key-and-description pair
    format_hints(): renders a binding list as one hint line
    FooterBar: hint bar that regenerates itself from the active bindings
    FooterBar.on_mount(): draws the hints once the bar is attached
    FooterBar.refresh_hints(): redraws the hints from the current bindings
"""

from collections.abc import Sequence

from textual.binding import Binding
from textual.widgets import Static

MAX_HINTS = 6
HINT_SEPARATOR = "   "
EMPTY_BAR = ""


def render_hint(binding: Binding) -> str:
    """Renders one binding as the pair shown on the bar.

    Args:
        binding: Binding to render.

    Returns:
        hint: Key and description separated by a space.
    """
    return f"{binding.key} {binding.description}"


def format_hints(bindings: Sequence[Binding], max_hints: int = MAX_HINTS) -> str:
    """Renders the active bindings as a single hint line.

    Bindings marked as hidden are skipped so internal keys never reach the bar,
    and the list is capped so a long binding set cannot wrap the footer.

    Args:
        bindings: Bindings the app currently exposes.
        max_hints: Most hints to render before the remainder are dropped.

    Returns:
        line: Rendered hint line, empty when nothing is bound.
    """
    shown = [b for b in bindings if b.show and b.description]
    if not shown:
        return EMPTY_BAR
    return HINT_SEPARATOR.join(render_hint(b) for b in shown[:max_hints])


class FooterBar(Static):
    """Renders the keybinding hints for whatever the app currently binds.

    Attributes:
        bindings: Bindings rendered on the bar.
    """

    def __init__(self, bindings: Sequence[Binding]) -> None:
        """Builds the bar around one binding set.

        Args:
            bindings: Bindings rendered on the bar.
        """
        super().__init__()
        self.bindings: list[Binding] = list(bindings)

    def on_mount(self) -> None:
        """Draws the hints once the bar is attached to the app."""
        self.refresh_hints()

    def refresh_hints(self) -> None:
        """Redraws the hint line from the bindings currently held."""
        self.update(format_hints(self.bindings))
