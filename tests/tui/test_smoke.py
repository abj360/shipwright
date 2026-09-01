#!/usr/bin/env python3
"""
test_smoke.py --- boots the terminal widgets under a headless Textual pilot

Contains:
    SmokeApp: minimal app mounting the widgets CI should prove still boot
    _boot(): runs the app under a pilot and reports what mounted
    test_widgets_mount_headless(): the interface boots with no display attached
    test_footer_renders_its_bindings(): the hint bar draws once mounted
"""

import asyncio

from textual.app import App, ComposeResult
from textual.binding import Binding

from agent.planner import Plan, PlanStep
from tui.screens.footer import FooterBar
from tui.widgets.plan_panel import PlanPanel

SMOKE_BINDINGS = [
    Binding("ctrl+c", "quit", "Quit"),
    Binding("ctrl+p", "plan", "Plan"),
]


class SmokeApp(App[None]):
    """Mounts the widgets CI should prove still boot without a terminal."""

    def compose(self) -> ComposeResult:
        """Mounts the plan panel above the generated hint bar."""
        plan = Plan(task="smoke", steps=[PlanStep(index=0, description="do nothing")])
        yield PlanPanel(plan)
        yield FooterBar(SMOKE_BINDINGS)


async def _boot() -> tuple[list[str], str]:
    """Runs the app under a pilot and reports what mounted.

    Returns:
        mounted: Class names of the widgets that mounted.
        footer_text: What the hint bar rendered.
    """
    app = SmokeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        mounted = [type(node).__name__ for node in app.query("PlanPanel, FooterBar")]
        footer_text = str(app.query_one(FooterBar).render())
    return mounted, footer_text


def test_widgets_mount_headless() -> None:
    """Asserts the interface boots with no display attached, as CI runs it."""
    mounted, _ = asyncio.run(_boot())

    assert "PlanPanel" in mounted
    assert "FooterBar" in mounted


def test_footer_renders_its_bindings() -> None:
    """Asserts the hint bar has drawn its keys by the time the app settles."""
    _, footer_text = asyncio.run(_boot())

    assert "ctrl+c Quit" in footer_text
