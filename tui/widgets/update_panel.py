#!/usr/bin/env python3
"""
update_panel.py --- offers an update when a newer release is out

Contains:
    NOTICE: what the card says
    UPDATE_LABEL / SKIP_LABEL: the two options
    UPDATE_BUTTON_ID / SKIP_BUTTON_ID: their element ids
    UpdatePanel: bordered card offering the update
    UpdatePanel.compose(): the notice above the two options
    UpdatePanel.on_mount(): puts the keyboard on Update, so enter takes it
    UpdatePanel.on_button_pressed(): reports whichever was chosen
    UpdatePanel.action_skip(): escape leaves this launch alone
    UpdatePanel.Answered: reports which the operator chose
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Static

from tui.theme import Palette, palette_for

NOTICE = "New update available"
UPDATE_LABEL = "Update"
SKIP_LABEL = "Skip for now"
UPDATE_BUTTON_ID = "update-now"
SKIP_BUTTON_ID = "update-skip"


class UpdatePanel(Vertical):
    """Offers the update the launcher found, and reports the answer.

    Attributes:
        latest: Version that is published.
        current: Version running right now.
        palette: Colours the card is drawn in.
    """

    DEFAULT_CSS = """
    UpdatePanel {
        height: auto;
        margin-bottom: 1;
        padding: 0 1;
        border: round $caution;
    }
    UpdatePanel #update-notice {
        color: $caution;
        text-style: bold;
    }
    UpdatePanel Horizontal {
        height: auto;
    }
    UpdatePanel Button {
        min-width: 0;
        width: auto;
        margin-right: 2;
    }
    UpdatePanel Button:hover {
        background: $caution;
        text-style: bold;
    }
    """

    BINDINGS = [Binding("escape", "skip", "Skip for now")]

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

    def __init__(self, latest: str = "", current: str = "", palette: Palette | None = None) -> None:
        """Builds the card.

        The versions are kept for the record, not shown: the card says there is
        an update and offers the two things that can be done about it.

        Args:
            latest: Version that is published.
            current: Version running right now.
            palette: Colours to draw from; detected from the terminal when None.
        """
        super().__init__()
        self.latest = latest
        self.current = current
        self.palette: Palette = palette_for() if palette is None else palette

    def compose(self) -> ComposeResult:
        """Lays out the notice above the two options."""
        yield Static(NOTICE, id="update-notice")
        with Horizontal():
            yield Button(UPDATE_LABEL, id=UPDATE_BUTTON_ID, variant="primary", compact=True)
            yield Button(SKIP_LABEL, id=SKIP_BUTTON_ID, compact=True)

    def on_mount(self) -> None:
        """Puts the keyboard on Update, so enter takes it and tab reaches Skip."""
        self.query_one(f"#{UPDATE_BUTTON_ID}", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Reports whichever option was chosen.

        Args:
            event: Button press identifying the option.
        """
        event.stop()
        self.post_message(self.Answered(event.button.id == UPDATE_BUTTON_ID))

    def action_skip(self) -> None:
        """Leaves this launch on the version it already has."""
        self.post_message(self.Answered(False))
