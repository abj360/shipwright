#!/usr/bin/env python3
"""
robot.py --- ascii mascot and the live status line it animates beside

Contains:
    ROBOT_ART: the standing mascot shown on the idle screen
    ROBOT_FRAMES: the frames the small mascot cycles while a run is working
    FRAME_INTERVAL_S: seconds between two frames
    Phase: what the agent is currently doing
    phase_for_tool(): maps a dispatched tool onto the phase it represents
    Robot: the standing mascot
    StatusLine: animated mascot beside the phase the run is in
    StatusLine.on_mount(): starts the animation
    StatusLine.advance(): moves the mascot on by one frame
    StatusLine.watch_frame_index(): repaints only this line
    StatusLine.set_phase(): switches the reported phase
    StatusLine.stop(): parks the mascot once the run ends
"""

from enum import StrEnum

from textual.reactive import reactive
from textual.widgets import Static

ROBOT_ART = (
    "     ╭───────╮",
    "     │ ◉   ◉ │",
    "  ╾──┤   ▁   ├──╼",
    "     ╰─┬───┬─╯",
    "       ╹   ╹",
)
ROBOT_FRAMES = (
    "╾[◉‿◉]╼",
    "╾[◉_◉]╼",
    "╾[◉‿◉]╼",
    "╾[-‿-]╼",
)
IDLE_FRAME = " [◉‿◉] "
FRAME_INTERVAL_S = 0.22


class Phase(StrEnum):
    """Names what the agent is doing, for the line beside the mascot."""

    PLANNING = "planning"
    REASONING = "reasoning"
    READING = "reading"
    EDITING = "editing"
    RUNNING = "running"
    DONE = "done"


TOOL_PHASES: dict[str, Phase] = {
    "read_file": Phase.READING,
    "list_dir": Phase.READING,
    "git_diff": Phase.READING,
    "write_file": Phase.EDITING,
    "edit_file": Phase.EDITING,
    "apply_patch": Phase.EDITING,
    "run_shell": Phase.RUNNING,
    "run_tests": Phase.RUNNING,
}


def phase_for_tool(tool_name: str) -> Phase:
    """Maps a dispatched tool onto the phase it represents.

    Args:
        tool_name: Tool the agent just dispatched.

    Returns:
        phase: Phase to report while that tool runs.
    """
    return TOOL_PHASES.get(tool_name, Phase.REASONING)


class Robot(Static):
    """Draws the standing mascot shown on the idle screen."""

    def render(self) -> str:
        """Renders the mascot.

        Returns:
            art: The mascot as a block of text.
        """
        return "\n".join(ROBOT_ART)


class StatusLine(Static):
    """Animates the mascot beside whatever the run is currently doing.

    The frame lives in a reactive attribute so a tick repaints this one line
    rather than the whole timeline.

    Attributes:
        frame_index: Position in ROBOT_FRAMES currently displayed.
        phase: What the agent is doing right now.
        is_animating: True while the mascot should keep moving.
    """

    frame_index: reactive[int] = reactive(0)

    def __init__(self) -> None:
        """Builds the line parked on its first frame."""
        super().__init__()
        self.phase = Phase.PLANNING
        self.is_animating = True

    def on_mount(self) -> None:
        """Starts the animation once the line is attached."""
        self.set_interval(FRAME_INTERVAL_S, self.advance)
        self.update(self.render_text())

    def advance(self) -> None:
        """Moves the mascot on by one frame."""
        if not self.is_animating or not self.display:
            return
        self.frame_index = (self.frame_index + 1) % len(ROBOT_FRAMES)

    def render_text(self) -> str:
        """Renders the mascot beside the current phase.

        Returns:
            line: Mascot frame followed by the phase, or a parked mascot.
        """
        if not self.is_animating:
            return f"{IDLE_FRAME} {self.phase.value}"
        return f"{ROBOT_FRAMES[self.frame_index]} {self.phase.value}…"

    def watch_frame_index(self, frame_index: int) -> None:
        """Repaints only this line when the mascot moves.

        Args:
            frame_index: Frame the mascot moved to.
        """
        del frame_index
        self.update(self.render_text())

    def set_phase(self, phase: Phase) -> None:
        """Switches the phase reported beside the mascot.

        Args:
            phase: What the agent is doing now.
        """
        self.phase = phase
        self.is_animating = phase is not Phase.DONE
        self.update(self.render_text())

    def stop(self) -> None:
        """Parks the mascot once the run has finished."""
        self.set_phase(Phase.DONE)
