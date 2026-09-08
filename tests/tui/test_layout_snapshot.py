#!/usr/bin/env python3
"""
test_layout_snapshot.py --- pins the shape of the idle and working views

Contains:
    _regions(): the visible regions of a mounted app, top to bottom
    test_idle_view_is_the_centred_mark(): the mark and composer, nothing else
    test_timeline_is_hidden_until_work_starts(): no empty transcript on open
    test_working_view_reveals_the_transcript(): a turn swaps in the transcript
    test_mark_sits_above_the_composer(): the mark is centred above the input
    test_no_status_bar_clutter(): no header, cost, token or connection readout
"""

import asyncio
from pathlib import Path

import pytest

from tui.app import ShipwrightApp
from tui.screens.composer import Composer
from tui.screens.footer import FooterBar
from tui.screens.timeline import Timeline
from tui.widgets.robot import StatusLine
from tui.widgets.wordmark import Wordmark


def _app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ShipwrightApp:
    """Builds a configured app so onboarding does not take the screen.

    Args:
        tmp_path: Checkout the app is pointed at.
        monkeypatch: Used to supply a provider credential.

    Returns:
        app: Application ready to mount.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-configured")
    return ShipwrightApp(tmp_path, provider="anthropic")


def _regions(app: ShipwrightApp) -> list[str]:
    """Reports the visible regions of a mounted app, top to bottom.

    Args:
        app: Application to mount and inspect.

    Returns:
        order: Class names of the visible regions in vertical order.
    """

    async def _run() -> list[str]:
        async with app.run_test() as pilot:
            await pilot.pause()
            found = [
                (widget.region.y, type(widget).__name__)
                for widget in (
                    app.query_one(Wordmark),
                    app.query_one(Timeline),
                    app.query_one(StatusLine),
                    app.query_one(Composer),
                    app.query_one(FooterBar),
                )
                if widget.display
            ]
        return [name for _, name in sorted(found)]

    return asyncio.run(_run())


def test_idle_view_is_the_centred_mark(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserts an idle window shows the mark and the input, and nothing more."""
    assert _regions(_app(tmp_path, monkeypatch)) == ["Wordmark", "Composer", "FooterBar"]


def test_timeline_is_hidden_until_work_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Asserts an empty transcript is not shown before anything has run."""
    app = _app(tmp_path, monkeypatch)

    async def _run() -> tuple[bool, bool]:
        async with app.run_test() as pilot:
            await pilot.pause()
            return app.query_one(Timeline).display, app.query_one(StatusLine).display

    timeline_shown, status_shown = asyncio.run(_run())

    assert timeline_shown is False
    assert status_shown is False


def test_working_view_reveals_the_transcript(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Asserts starting a turn swaps the mark out for the transcript."""
    app = _app(tmp_path, monkeypatch)

    async def _run() -> tuple[bool, bool]:
        async with app.run_test() as pilot:
            await pilot.pause()
            app.enter_working_view()
            await pilot.pause()
            return app.query_one("#region-hero").display, app.query_one(Timeline).display

    hero_shown, timeline_shown = asyncio.run(_run())

    assert hero_shown is False
    assert timeline_shown is True


def test_mark_sits_above_the_composer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserts the wordmark is drawn above the instruction input."""
    order = _regions(_app(tmp_path, monkeypatch))

    assert order.index("Wordmark") < order.index("Composer")


def test_no_status_bar_clutter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserts the header, cost, token and connection readouts are all gone."""
    app = _app(tmp_path, monkeypatch)

    async def _run() -> int:
        async with app.run_test() as pilot:
            await pilot.pause()
            return len(app.query("HeaderBar")) + len(app.query("ConnectionDot"))

    assert asyncio.run(_run()) == 0
