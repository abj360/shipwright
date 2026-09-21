#!/usr/bin/env python3
"""
update_panel.py --- offers an update when a newer release is out

Contains:
    UPDATE_KEY / SKIP_KEY: the keys that answer the panel
    TITLE: the heading the card carries
    NOTICE_TEMPLATE: what the card says about the two versions
    HINT: the key hints under the notice
    UpdatePanel: bordered card offering the update
    UpdatePanel.render(): draws the notice and the hints
    UpdatePanel.action_update(): accepts the update
    UpdatePanel.action_skip(): leaves this launch on the version it has
    UpdatePanel.Answered: reports which the operator chose
"""

from rich.text import Text
from textual.binding import Binding
from textual.message import Message
from textual.widgets import Static

from tui.theme import Palette, palette_for

UPDATE_KEY = "enter"
SKIP_KEY = "escape"
TITLE = "Update available"
NOTICE_TEMPLATE = "shipwright {latest} is out; this is {current}."
HINT = "[enter] update and reopen this session   [esc] skip for now"


class UpdatePanel(Static):
    """Offers the update that the launcher found, and reports the answer.

    Attributes:
        latest: Version that is published.
        current: Version running right now.
        palette: Colours the card is drawn in.
    """

    can_focus = True

    DEFAULT_CSS = """
    UpdatePanel {
        height: auto;
        margin-bottom: 1;
        padding: 0 1;
        border: round $caution;
        border-title-color: $caution;
    }
    """

    BINDINGS = [
        Binding(UPDATE_KEY, "update", "Update"),
        Binding(SKIP_KEY, "skip", "Skip"),
    ]

    class Answered(Message):
        """Reports whether the operator took the update.

        Attributes:
            is_accepted: True when the update was accepted.
        """

        def __init__(self, is_accepted: bool) -> None:
            """Records the answer.

            Args:
                is_accepted: True when the update was accepted.
            """
            super().__init__()
            self.is_accepted = is_accepted

    def __init__(self, latest: str, current: str, palette: Palette | None = None) -> None:
        """Builds the card for one pair of versions.

        Args:
            latest: Version that is published.
            current: Version running right now.
            palette: Colours to draw from; detected from the terminal when None.
        """
        super().__init__()
        self.latest = latest
        self.current = current
        self.palette: Palette = palette_for() if palette is None else palette
        self.border_title = TITLE

    def render(self) -> Text:
        """Draws the notice and the key hints.

        Returns:
            rendered: The card's text.
        """
        block = Text()
        block.append(NOTICE_TEMPLATE.format(latest=self.latest, current=self.current))
        block.append(f"\n{HINT}", style=self.palette.hunk)
        return block

    def action_update(self) -> None:
        """Accepts the update."""
        self.post_message(self.Answered(True))

    def action_skip(self) -> None:
        """Leaves this launch on the version it already has."""
        self.post_message(self.Answered(False))
