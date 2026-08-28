#!/usr/bin/env python3
"""
test_app.py --- covers the app's four-region composition and command routing

Contains:
    _app(): builds the app against a temporary checkout
    test_four_regions_mount(): header, timeline, composer, and footer all mount
    test_slash_command_is_routed(): a breaker command reaches the breaker
    test_unknown_command_is_reported(): an unknown command is reported, not raised
    test_plain_text_starts_a_turn(): ordinary text opens a turn on the timeline
"""

import asyncio
from pathlib import Path

from tui.app import ShipwrightApp
from tui.screens.composer import Composer
from tui.screens.footer import FooterBar
from tui.screens.header import HeaderBar
from tui.screens.timeline import Timeline


def _app(tmp_path: Path) -> ShipwrightApp:
    """Builds the app against a temporary checkout.

    Args:
        tmp_path: Checkout the app is pointed at.

    Returns:
        app: Configured application instance.
    """
    return ShipwrightApp(tmp_path, provider="anthropic")


def test_four_regions_mount(tmp_path: Path) -> None:
    """Asserts all four regions of the layout mount under a headless pilot."""

    async def _boot() -> list[str]:
        app = _app(tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            return [
                type(app.query_one(widget)).__name__
                for widget in (HeaderBar, Timeline, Composer, FooterBar)
            ]

    assert asyncio.run(_boot()) == ["HeaderBar", "Timeline", "Composer", "FooterBar"]


def test_slash_command_is_routed(tmp_path: Path) -> None:
    """Asserts a breaker slash command reaches the live circuit breaker."""

    async def _run() -> float:
        app = _app(tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.handle_line("/max-cost 7.5")
            return app.breaker.max_cost_usd

    assert asyncio.run(_run()) == 7.5


def test_unknown_command_is_reported(tmp_path: Path) -> None:
    """Asserts an unregistered command is reported instead of crashing the app."""

    async def _run() -> str:
        app = _app(tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            return app.handle_line("/teleport now")

    assert "unknown command" in asyncio.run(_run())


def test_plain_text_starts_a_turn(tmp_path: Path) -> None:
    """Asserts ordinary text opens a turn on the timeline rather than routing."""

    async def _run() -> int:
        app = _app(tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.handle_line("add a health endpoint")
            return len(app.query_one(Timeline).turns)

    assert asyncio.run(_run()) == 1
