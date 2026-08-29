#!/usr/bin/env python3
"""
test_timeline.py --- covers turn recording in the timeline

Contains:
    _row(): builds a throwaway activity row
    test_starting_a_turn_records_the_instruction(): the turn keeps what was asked
    test_steps_attach_to_the_open_turn(): steps land on the newest turn
    test_finishing_records_the_answer(): the answer closes the turn
    test_recording_without_a_turn_raises(): a step with no turn fails loudly
    test_summary_pluralizes_step_count(): one step reads singular
"""

import pytest

from tui.screens.timeline import Timeline
from tui.widgets.step_row import StepRow


def _row() -> StepRow:
    """Builds a throwaway activity row.

    Returns:
        row: A Read row against a sample path.
    """
    return StepRow("read_file", {"path": "a.py"}, "contents")


def test_starting_a_turn_records_the_instruction() -> None:
    """Asserts a new turn keeps the instruction it was opened with."""
    timeline = Timeline()

    turn = timeline.start_turn("add a health endpoint")

    assert turn.instruction == "add a health endpoint"
    assert turn.is_finished is False


def test_steps_attach_to_the_open_turn() -> None:
    """Asserts recorded steps land on the most recently started turn."""
    timeline = Timeline()
    timeline.start_turn("first")
    timeline.start_turn("second")

    timeline.record_step(_row())

    assert timeline.turns[0].step_count() == 0
    assert timeline.turns[1].step_count() == 1


def test_finishing_records_the_answer() -> None:
    """Asserts finishing a turn records the answer and marks it done."""
    timeline = Timeline()
    timeline.start_turn("do the thing")

    timeline.finish_turn("done it")

    assert timeline.turns[-1].answer == "done it"
    assert timeline.turns[-1].is_finished is True


def test_recording_without_a_turn_raises() -> None:
    """Asserts recording a step before any turn exists fails rather than passing."""
    with pytest.raises(RuntimeError):
        Timeline().record_step(_row())

    with pytest.raises(RuntimeError):
        Timeline().finish_turn("nothing to answer")


def test_summary_pluralizes_step_count() -> None:
    """Asserts the collapsed summary reads naturally for one step and for many."""
    timeline = Timeline()
    turn = timeline.start_turn("tidy up")

    timeline.record_step(_row())
    assert turn.summary_line().endswith("1 step")

    timeline.record_step(_row())
    assert turn.summary_line().endswith("2 steps")
