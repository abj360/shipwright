#!/usr/bin/env python3
"""
timeline.py --- scrollable turn history matching the conversation view's shape

Contains:
    KEEP_EXPANDED: how many recent turns stay open
    Turn: one instruction and the steps it produced
    Turn.step_count(): how many steps the turn ran
    Turn.summary_line(): the one-line summary a collapsed turn shows
    Turn.failed_step_count(): how many of the turn's steps errored
    _should_collapse(): whether one turn is eligible to be folded
    collapse_completed_turns(): closes finished turns, keeping the newest open
    Timeline: scrollable history of turns
    Timeline.start_turn(): opens a new turn for one instruction
    Timeline.record_step(): appends one step to the open turn
    Timeline.finish_turn(): closes the open turn with the agent's answer
"""

from dataclasses import dataclass, field

from textual.containers import VerticalScroll

from tui.widgets.step_row import StepRow

# One turn stays open: the one the operator is actually watching work.
KEEP_EXPANDED = 1
NO_ANSWER_YET = ""


@dataclass
class Turn:
    """Records one instruction and everything the agent did for it.

    Attributes:
        instruction: What the operator asked for.
        steps: Activity rows produced while answering.
        answer: Final answer, empty while the turn is still running.
        is_collapsed: True once the turn has been folded to its summary.
    """

    instruction: str
    steps: list[StepRow] = field(default_factory=list)
    answer: str = NO_ANSWER_YET
    is_collapsed: bool = False

    @property
    def is_finished(self) -> bool:
        """Reports whether the turn has produced its answer.

        Returns:
            is_finished: True once an answer has been recorded.
        """
        return bool(self.answer)

    def step_count(self) -> int:
        """Counts the steps the turn ran.

        Returns:
            count: Number of activity rows in the turn.
        """
        return len(self.steps)

    def failed_step_count(self) -> int:
        """Counts how many of the turn's steps returned an error.

        Returns:
            count: Number of failed activity rows in the turn.
        """
        return sum(1 for step in self.steps if step.has_failed())

    def summary_line(self) -> str:
        """Renders the one-line summary a collapsed turn shows.

        Returns:
            line: The instruction and how many steps it took.
        """
        count = self.step_count()
        plural = "step" if count == 1 else "steps"
        parts: list[str] = [f"{self.instruction} — {count} {plural}"]
        failures = self.failed_step_count()
        if failures:
            parts.append(f"{failures} failed")
        return ", ".join(parts)


def _should_collapse(turn: Turn, index: int, cutoff: int) -> bool:
    """Reports whether one turn is eligible to be folded away.

    Args:
        turn: Turn being considered.
        index: Its position in the timeline.
        cutoff: Index at and beyond which turns stay open.

    Returns:
        should_collapse: True when the turn is old, finished, and still open.
    """
    return index < cutoff and turn.is_finished and not turn.is_collapsed


def collapse_completed_turns(turns: list[Turn], keep_expanded: int = KEEP_EXPANDED) -> int:
    """Folds finished turns to their summary, leaving the newest ones open.

    A turn still running is never collapsed, however old it is: the operator is
    watching it work, which is the whole point of the view.

    Args:
        turns: Turns in the order they were started.
        keep_expanded: How many of the most recent turns stay open.

    Returns:
        collapsed: How many turns this call folded.
    """
    if keep_expanded < 0:
        raise ValueError("keep_expanded must not be negative")
    collapsed: int = 0
    cutoff: int = len(turns) - keep_expanded
    for index, turn in enumerate(turns):
        if not _should_collapse(turn, index, cutoff):
            continue
        turn.is_collapsed = True
        collapsed += 1
    return collapsed


class Timeline(VerticalScroll):
    """Holds the scrollable history of turns for one session.

    Attributes:
        turns: Turns in the order they were started.
    """

    def __init__(self) -> None:
        """Starts an empty timeline."""
        super().__init__()
        self.turns: list[Turn] = []

    def start_turn(self, instruction: str) -> Turn:
        """Opens a new turn for one instruction.

        Args:
            instruction: What the operator asked for.

        Returns:
            turn: The newly opened turn.
        """
        turn = Turn(instruction=instruction)
        self.turns.append(turn)
        collapse_completed_turns(self.turns)

        return turn

    def record_step(self, row: StepRow) -> None:
        """Appends one activity row to the turn currently open.

        Args:
            row: Activity row to append.

        Raises:
            RuntimeError: No turn has been started yet.
        """
        if not self.turns:
            raise RuntimeError("record_step called before any turn was started")
        self.turns[-1].steps.append(row)

    def finish_turn(self, answer: str) -> None:
        """Closes the open turn with the agent's answer.

        Args:
            answer: Final answer the agent produced.

        Raises:
            RuntimeError: No turn has been started yet.
        """
        if not self.turns:
            raise RuntimeError("finish_turn called before any turn was started")
        self.turns[-1].answer = answer
