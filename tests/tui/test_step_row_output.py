#!/usr/bin/env python3
"""
test_step_row_output.py --- covers previewing and revealing long step output

Contains:
    _long_row(): a row whose observation exceeds the preview length
    test_short_output_is_shown_whole(): a small observation is not truncated
    test_long_output_is_previewed(): a long observation stops at the preview
    test_hint_reports_the_remaining_lines(): the hint counts what is held back
    test_toggle_reveals_everything(): the toggle shows the whole observation
    test_collapsed_row_shows_nothing(): the toggle does not leak past collapse
"""

from tui.widgets.step_row import PREVIEW_LINES, StepRow

TOTAL_LINES = PREVIEW_LINES + 8


def _long_row() -> StepRow:
    """Builds an expanded row whose observation is longer than the preview.

    Returns:
        row: Expanded row holding TOTAL_LINES lines of output.
    """
    output = "\n".join(f"line {index}" for index in range(TOTAL_LINES))
    row = StepRow("run_tests", {}, output)
    row.is_expanded = True
    return row


def test_short_output_is_shown_whole() -> None:
    """Asserts an observation inside the preview length is shown in full."""
    row = StepRow("read_file", {"path": "a.py"}, "one\ntwo")
    row.is_expanded = True

    assert row.is_truncated() is False
    assert row.detail_lines() == ["one", "two"]


def test_long_output_is_previewed() -> None:
    """Asserts a long observation is cut to the preview plus a hint line."""
    lines = _long_row().detail_lines()

    assert len(lines) == PREVIEW_LINES + 1
    assert lines[PREVIEW_LINES].startswith("…")


def test_hint_reports_the_remaining_lines() -> None:
    """Asserts the hint says how many lines are still hidden."""
    hint = _long_row().detail_lines()[-1]

    assert str(TOTAL_LINES - PREVIEW_LINES) in hint


def test_toggle_reveals_everything() -> None:
    """Asserts asking for full output shows every line and drops the hint."""
    row = _long_row()

    row.action_show_full_output()

    assert len(row.detail_lines()) == TOTAL_LINES
    assert not row.detail_lines()[-1].startswith("…")


def test_collapsed_row_shows_nothing() -> None:
    """Asserts a collapsed row reveals nothing even after the toggle was used."""
    row = _long_row()
    row.action_show_full_output()
    row.is_expanded = False

    assert row.detail_lines() == []
