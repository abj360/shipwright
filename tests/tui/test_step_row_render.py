#!/usr/bin/env python3
"""
test_step_row_render.py --- covers the activity row's drawn output

Contains:
    RowHarness: app mounting a single activity row
    _mounted_text(): mounts a row and returns what it drew
    test_collapsed_row_draws_only_its_summary(): output stays hidden
    test_expanded_row_draws_its_output(): opening reveals the observation
    test_failed_row_is_styled(): a failed row carries the error colour
"""

import asyncio

from textual.app import App, ComposeResult

from tui.theme import DARK
from tui.widgets.step_row import StepRow


class RowHarness(App[None]):
    """Mounts one activity row so a pilot can render it.

    Attributes:
        row: The activity row under test.
    """

    def __init__(self, row: StepRow) -> None:
        """Builds the harness around one row.

        Args:
            row: The activity row under test.
        """
        super().__init__()
        self.row = row

    def compose(self) -> ComposeResult:
        """Mounts the row under test."""
        yield self.row


async def _mounted_text(row: StepRow, expand: bool) -> str:
    """Mounts a row, optionally opens it, and returns what it drew.

    Args:
        row: The activity row under test.
        expand: Whether to open the row before reading it.

    Returns:
        drawn: Plain text the row rendered.
    """
    app = RowHarness(row)
    async with app.run_test() as pilot:
        if expand:
            row.action_toggle()
        await pilot.pause()
        return row.render().plain


def test_collapsed_row_draws_only_its_summary() -> None:
    """Asserts a closed row draws its summary and none of its output."""
    row = StepRow("read_file", {"path": "a.py"}, "secret contents", palette=DARK)

    drawn = asyncio.run(_mounted_text(row, expand=False))

    assert "Read" in drawn
    assert "secret contents" not in drawn


def test_expanded_row_draws_its_output() -> None:
    """Asserts opening a row draws the observation beneath the summary."""
    row = StepRow("read_file", {"path": "a.py"}, "line one\nline two", palette=DARK)

    drawn = asyncio.run(_mounted_text(row, expand=True))

    assert "line one" in drawn
    assert "line two" in drawn


def test_failed_row_is_styled() -> None:
    """Asserts a failed row's summary carries the palette's error colour."""
    row = StepRow("run_shell", {"command": "pytest"}, "error: boom", palette=DARK)

    styles = {str(span.style) for span in row.render().spans}

    assert DARK.status_error in styles
