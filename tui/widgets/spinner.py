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
    Spinner.watch_frame_index(): repaints only this row when the frame changes
    Spinner.stop(): freezes the spinner once the step completes
"""

from textual.reactive import reactive
from textual.widgets import Static

BRAILLE_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
FRAME_INTERVAL_S = 0.08
IDLE_GLYPH = " "


class Spinner(Static):
    """Animates a braille dot for as long as its step is in flight.

    The frame lives in a reactive attribute so Textual repaints this one
    widget per tick. Refreshing the app instead re-rendered every row in the
    timeline on every frame, which pegged a core on long runs.

    Attributes:
        frame_index: Position in BRAILLE_FRAMES currently displayed.
        is_spinning: True while the animation should keep advancing.
    """

    frame_index: reactive[int] = reactive(0)

    def __init__(self) -> None:
        """Builds a spinner parked on its first frame."""
        super().__init__(BRAILLE_FRAMES[0])
        self.is_spinning = True

    def on_mount(self) -> None:
        """Starts the animation timer once the spinner is attached."""
        self.set_interval(FRAME_INTERVAL_S, self.advance)

    def advance(self) -> None:
        """Moves the animation on by one frame.

        A spinner scrolled out of view costs nothing to leave alone, so the
        frame is only advanced while the row is actually on screen.
        """
        if not self.is_spinning or not self.display:
            return
        self.frame_index = (self.frame_index + 1) % len(BRAILLE_FRAMES)

    def watch_frame_index(self, frame_index: int) -> None:
        """Repaints only this spinner when its frame changes.

        Args:
            frame_index: Frame the spinner moved to.
        """
        self.update(BRAILLE_FRAMES[frame_index])

    def stop(self) -> None:
        """Freezes the spinner once its step has finished."""
        self.is_spinning = False
        self.update(IDLE_GLYPH)
