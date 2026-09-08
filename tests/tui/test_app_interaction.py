#!/usr/bin/env python3
"""
test_app_interaction.py --- drives the app the way an operator does

Covers the wiring between typing and running that method-level tests miss:
the caret has to start in the composer, Enter has to submit, and a submitted
instruction has to actually reach the agent loop.

Contains:
    ScriptedApp: app whose loop is backed by a scripted model
    _drive(): types an instruction, presses Enter, and waits for the turn
    test_caret_starts_in_the_composer(): typing lands in the input, not the timeline
    test_enter_opens_a_turn_and_clears_the_input(): Enter submits
    test_submitted_instruction_reaches_the_agent(): the loop actually runs
    test_missing_credential_is_reported_in_the_timeline(): no crash without a key
"""

import asyncio
from pathlib import Path

import pytest
from textual.widgets import Input

from agent.llm_client import ScriptedLLM
from agent.loop import AgentConfig, AgentLoop
from tui.app import ShipwrightApp
from tui.screens.timeline import Timeline

SCRIPT = [
    "Looking first.\nAction: read_file\npath=widget.py",
    "FINAL: read the file and left it alone",
]


class ScriptedApp(ShipwrightApp):
    """Runs against a scripted model so the wiring can be tested offline."""

    def build_loop(self, instruction: str) -> AgentLoop:
        """Builds a loop backed by a scripted model.

        Args:
            instruction: What the operator asked the agent to do.

        Returns:
            loop: Loop that replays SCRIPT instead of calling a provider.
        """
        config = AgentConfig(
            repo_path=str(self.repo_path),
            task=instruction,
            cost_tracker=self.cost_tracker,
        )
        config.breaker = self.breaker
        return AgentLoop(ScriptedLLM(list(SCRIPT)), config)


def _checkout(tmp_path: Path) -> Path:
    """Builds a checkout holding one readable file.

    Args:
        tmp_path: Per-test temporary directory.

    Returns:
        repo_path: Directory the app is pointed at.
    """
    (tmp_path / "widget.py").write_text("def area(w, h):\n    return w * h\n")
    return tmp_path


async def _drive(app: ShipwrightApp, instruction: str) -> tuple[Timeline, str]:
    """Types an instruction, presses Enter, and waits for the turn to finish.

    Args:
        app: Application under test.
        instruction: Text to type into the composer.

    Returns:
        timeline: The app's timeline once the turn has settled.
        leftover: What the instruction field still holds, read before shutdown.
    """
    async with app.run_test() as pilot:
        await pilot.pause()
        for character in instruction:
            await pilot.press("space" if character == " " else character)
        await pilot.press("enter")
        for _ in range(60):
            await pilot.pause()
            await asyncio.sleep(0.05)
            timeline = app.query_one(Timeline)
            if timeline.turns and timeline.turns[-1].is_finished:
                break
        return app.query_one(Timeline), app.query_one(Input).value


def test_caret_starts_in_the_composer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserts typing on a configured app lands in the instruction field."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-configured")

    async def _run() -> str:
        app = ScriptedApp(_checkout(tmp_path), provider="anthropic")
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("h", "i")
            await pilot.pause()
            return app.query_one(Input).value

    assert asyncio.run(_run()) == "hi"


def test_enter_opens_a_turn_and_clears_the_input(tmp_path: Path) -> None:
    """Asserts Enter submits the line rather than leaving it sitting in the box."""

    async def _run() -> tuple[int, str]:
        app = ScriptedApp(_checkout(tmp_path), provider="anthropic")
        timeline, leftover = await _drive(app, "read the widget")
        return len(timeline.turns), leftover

    turn_count, leftover = asyncio.run(_run())

    assert turn_count == 1
    assert leftover == ""


def test_submitted_instruction_reaches_the_agent(tmp_path: Path) -> None:
    """Asserts a submitted instruction actually runs and records its steps."""

    async def _run() -> tuple[list[str], str]:
        app = ScriptedApp(_checkout(tmp_path), provider="anthropic")
        timeline, _ = await _drive(app, "read the widget")
        turn = timeline.turns[-1]
        return [row.summary_line() for row in turn.steps], turn.answer

    summaries, answer = asyncio.run(_run())

    assert any("Read" in line for line in summaries)
    assert "widget.py" in " ".join(summaries)
    assert answer == "read the file and left it alone"


def test_missing_credential_is_reported_in_the_timeline(tmp_path: Path) -> None:
    """Asserts a run with no provider key closes the turn instead of crashing."""

    async def _run() -> str:
        app = ShipwrightApp(_checkout(tmp_path), provider="anthropic")
        timeline, _ = await _drive(app, "do something")
        return timeline.turns[-1].answer

    answer = asyncio.run(_run())

    assert "API_KEY" in answer
