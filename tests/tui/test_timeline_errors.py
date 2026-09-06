#!/usr/bin/env python3
"""
test_timeline_errors.py --- covers failure reporting on collapsed turns

Contains:
    _ok_row() / _bad_row(): activity rows that succeeded and failed
    test_clean_turn_reports_no_failures(): a good turn says nothing about errors
    test_failed_steps_are_counted(): the collapsed summary counts failures
    test_summary_mentions_failures(): a collapsed turn surfaces that it failed
    test_empty_turn_reports_no_failures(): a turn with no steps counts zero
"""

from tui.screens.timeline import Timeline
from tui.widgets.step_row import StepRow


def _ok_row() -> StepRow:
    """Builds a row whose tool succeeded.

    Returns:
        row: A successful Read row.
    """
    return StepRow("read_file", {"path": "a.py"}, "contents")


def _bad_row() -> StepRow:
    """Builds a row whose tool returned an error.

    Returns:
        row: A failed Ran row.
    """
    return StepRow("run_shell", {"command": "pytest"}, "error: 1 failed")


def test_clean_turn_reports_no_failures() -> None:
    """Asserts a turn where everything worked reports no failures."""
    timeline = Timeline()
    timeline.start_turn("tidy up")
    timeline.record_step(_ok_row())

    assert timeline.turns[-1].failed_step_count() == 0
    assert "failed" not in timeline.turns[-1].summary_line()


def test_failed_steps_are_counted() -> None:
    """Asserts only the failed steps are counted, not every step."""
    timeline = Timeline()
    timeline.start_turn("fix the build")
    timeline.record_step(_ok_row())
    timeline.record_step(_bad_row())
    timeline.record_step(_bad_row())

    assert timeline.turns[-1].failed_step_count() == 2


def test_summary_mentions_failures() -> None:
    """Asserts a collapsed turn still tells the operator something went wrong."""
    timeline = Timeline()
    timeline.start_turn("fix the build")
    timeline.record_step(_bad_row())

    assert "1 failed" in timeline.turns[-1].summary_line()


def test_empty_turn_reports_no_failures() -> None:
    """Asserts a turn that ran no steps reports no failures rather than erroring."""
    timeline = Timeline()
    timeline.start_turn("nothing to do")

    assert timeline.turns[-1].failed_step_count() == 0
