#!/usr/bin/env python3
"""
spinner.py --- braille-dot spinner marking a step that is still in flight

Contains:
    BRAILLE_FRAMES: frames cycled while a step is running
    FRAME_INTERVAL_S: seconds between two frames
    IDLE_GLYPH: what the spinner shows once its step has finished
    Spinner: animates a braille dot while its step is in flight
    Spinner.on_mount(): starts the animation timer
    Spinner.advance(): moves the animation on by one frame
    Spinner.stop(): freezes the spinner once the step completes
"""

from textual.widgets import Static

BRAILLE_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
FRAME_INTERVAL_S = 0.08
IDLE_GLYPH = " "


class Spinner(Static):
    """Animates a braille dot for as long as its step is in flight.

    Attributes:
        is_spinning: True while the animation should keep advancing.
    """

    def __init__(self) -> None:
        """Builds a spinner parked on its first frame."""
        super().__init__(BRAILLE_FRAMES[0])
        self.is_spinning = True
        self._index = 0

    def on_mount(self) -> None:
        """Starts the animation timer once the spinner is attached."""
        self.set_interval(FRAME_INTERVAL_S, self.advance)

    def advance(self) -> None:
        """Moves the animation on by one frame and repaints."""
        if not self.is_spinning:
            return
        self._index = (self._index + 1) % len(BRAILLE_FRAMES)
        self.update(BRAILLE_FRAMES[self._index])
        self.app.refresh(layout=True)

    def stop(self) -> None:
        """Freezes the spinner once its step has finished."""
        self.is_spinning = False
        self.update(IDLE_GLYPH)
