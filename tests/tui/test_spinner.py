#!/usr/bin/env python3
"""
test_spinner.py --- covers the in-flight step spinner

Contains:
    SpinnerHarness: app hosting a single spinner
    _advance_twice(): mounts a spinner and advances it twice
    test_spinner_cycles_frames(): advancing changes the visible frame
    test_stopped_spinner_stops_advancing(): a finished step freezes
"""

import asyncio

from textual.app import App, ComposeResult

from tui.widgets.spinner import BRAILLE_FRAMES, IDLE_GLYPH, Spinner


class SpinnerHarness(App[None]):
    """Hosts one spinner so a pilot can advance it."""

    def compose(self) -> ComposeResult:
        """Mounts the spinner under test."""
        yield Spinner()


async def _advance_twice() -> tuple[str, str]:
    """Mounts a spinner, advances it, then stops it.

    Returns:
        advanced: Frame shown after two advances.
        stopped: Frame shown after the step finished.
    """
    app = SpinnerHarness()
    async with app.run_test() as pilot:
        spinner = app.query_one(Spinner)
        spinner.advance()
        spinner.advance()
        advanced = str(spinner.render())
        spinner.stop()
        spinner.advance()
        stopped = str(spinner.render())
        await pilot.pause()
    return advanced, stopped


def test_spinner_cycles_frames() -> None:
    """Asserts advancing the spinner moves it onto a later braille frame."""
    advanced, _ = asyncio.run(_advance_twice())

    assert advanced == BRAILLE_FRAMES[2]


def test_stopped_spinner_stops_advancing() -> None:
    """Asserts a stopped spinner stays parked instead of animating on."""
    _, stopped = asyncio.run(_advance_twice())

    assert stopped == IDLE_GLYPH
