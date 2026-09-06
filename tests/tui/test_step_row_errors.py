#!/usr/bin/env python3
"""
test_step_row_errors.py --- covers failed-step highlighting on activity rows

Contains:
    test_failed_step_is_detected(): the loop's error prefix marks a step failed
    test_failed_summary_carries_a_warning_prefix(): failure survives without colour
    test_successful_step_has_no_prefix(): a good step is not decorated
    test_failed_row_uses_the_error_colour(): a failed row draws in the error colour
    test_monochrome_failure_still_readable(): the prefix works with no colour
    test_error_prefix_matches_the_loop(): the marker is the loop's own constant
"""

from tui.theme import DARK, MONOCHROME
from tui.widgets.step_row import WARNING_PREFIX, StepRow


def _failed_row(palette=DARK) -> StepRow:
    """Builds a row whose tool returned an error.

    Args:
        palette: Colours the row draws from.

    Returns:
        row: A failed Ran row.
    """
    return StepRow("run_shell", {"command": "pytest"}, "error: 1 failed", palette=palette)


def test_failed_step_is_detected() -> None:
    """Asserts the loop's own error prefix is what marks a step as failed."""
    assert _failed_row().has_failed() is True


def test_failed_summary_carries_a_warning_prefix() -> None:
    """Asserts a failed step is flagged in text, not by colour alone."""
    assert WARNING_PREFIX in _failed_row().summary_line()


def test_successful_step_has_no_prefix() -> None:
    """Asserts a step that succeeded is not decorated as a failure."""
    row = StepRow("read_file", {"path": "a.py"}, "contents", palette=DARK)

    assert row.has_failed() is False
    assert WARNING_PREFIX not in row.summary_line()


def test_failed_row_uses_the_error_colour() -> None:
    """Asserts a failed row is drawn in the palette's error colour."""
    assert _failed_row().highlight_color() == DARK.status_error


def test_monochrome_failure_still_readable() -> None:
    """Asserts failure is still visible on a terminal with no colour at all."""
    row = _failed_row(palette=MONOCHROME)

    assert row.highlight_color() == ""
    assert WARNING_PREFIX in row.summary_line()


def test_error_prefix_matches_the_loop() -> None:
    """Asserts the row keys off the agent loop's constant, not a copied string."""
    from agent.loop import TOOL_ERROR_PREFIX

    row = StepRow("run_shell", {"command": "x"}, f"{TOOL_ERROR_PREFIX}boom", palette=DARK)

    assert row.has_failed() is True
