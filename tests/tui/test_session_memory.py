#!/usr/bin/env python3
"""
test_session_memory.py --- asserts a run reasons over the whole session

A follow-up like "now do the same for the other module" is meaningless without
the turns before it, so each run replays the session's earlier turns.

Contains:
    Recorder: records the messages each turn was handed
    MemoryApp: app whose loop is backed by the recorder
    _run_turns(): drives several instructions through one app
    test_first_turn_has_no_history(): a fresh session starts clean
    test_later_turn_replays_earlier_turns(): the follow-up sees what came before
    test_history_is_capped(): a long session cannot grow without bound
"""

import asyncio
from pathlib import Path

from agent.llm_client import Completion, Message
from agent.loop import AgentConfig, AgentLoop
from tui.app import HISTORY_TURN_LIMIT, ShipwrightApp
from tui.screens.timeline import Timeline


class Recorder:
    """Records what each turn was asked, then finishes immediately.

    Attributes:
        seen: Message lists, one per completion requested.
    """

    def __init__(self) -> None:
        """Starts a recorder with nothing seen yet."""
        self.seen: list[list[Message]] = []

    def complete(self, messages: list[Message], system: str, max_tokens: int = 8192) -> Completion:
        """Records the conversation and answers immediately.

        Args:
            messages: Conversation handed to the model.
            system: Ignored.
            max_tokens: Ignored.

        Returns:
            completion: A closing answer so the turn ends at once.
        """
        self.seen.append(list(messages))
        return Completion(
            text="FINAL: ok", model="claude-haiku-4-5", input_tokens=1, output_tokens=1
        )


class MemoryApp(ShipwrightApp):
    """Runs against a recorder so the replayed history can be inspected.

    Attributes:
        recorder: Captures the messages each turn was given.
    """

    def __init__(self, repo_path: Path) -> None:
        """Builds the app around a fresh recorder.

        Args:
            repo_path: Checkout the app is pointed at.
        """
        super().__init__(repo_path, provider="anthropic")
        self.recorder = Recorder()

    def build_loop(self, instruction: str) -> AgentLoop:
        """Builds a loop backed by the recorder, carrying session history.

        Args:
            instruction: What the operator asked for.

        Returns:
            loop: Loop that records rather than calling a provider.
        """
        config = AgentConfig(
            repo_path=str(self.repo_path),
            task=instruction,
            cost_tracker=self.cost_tracker,
        )
        config.breaker = self.breaker
        config.history = list(self.conversation)
        return AgentLoop(self.recorder, config)


def _run_turns(tmp_path: Path, instructions: list[str]) -> MemoryApp:
    """Drives several instructions through one app session.

    Args:
        tmp_path: Checkout the app is pointed at.
        instructions: Instructions to submit in order.

    Returns:
        app: The app, after every turn has finished.
    """

    async def _run() -> MemoryApp:
        app = MemoryApp(tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            for instruction in instructions:
                app.handle_line(instruction)
                for _ in range(40):
                    await pilot.pause()
                    await asyncio.sleep(0.02)
                    if app.query_one(Timeline).turns[-1].is_finished:
                        break
        return app

    return asyncio.run(_run())


def test_first_turn_has_no_history(tmp_path: Path) -> None:
    """Asserts the opening turn is asked about nothing but itself."""
    app = _run_turns(tmp_path, ["add a health endpoint"])

    opening = app.recorder.seen[0]

    assert [message.content for message in opening] == ["add a health endpoint"]


def test_later_turn_replays_earlier_turns(tmp_path: Path) -> None:
    """Asserts a follow-up is asked in the context of what came before."""
    app = _run_turns(tmp_path, ["add a health endpoint", "now do the same for metrics"])

    follow_up = [message.content for message in app.recorder.seen[-1]]

    assert "add a health endpoint" in follow_up
    assert follow_up.index("add a health endpoint") < follow_up.index("now do the same for metrics")


def test_history_is_capped(tmp_path: Path) -> None:
    """Asserts a long session does not grow its replayed history without bound."""
    app = _run_turns(tmp_path, [f"step {index}" for index in range(HISTORY_TURN_LIMIT + 4)])

    assert len(app.conversation) <= HISTORY_TURN_LIMIT * 2
