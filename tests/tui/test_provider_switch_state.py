#!/usr/bin/env python3
"""
test_provider_switch_state.py --- asserts a mid-run provider switch preserves run state

Contains:
    _seeded_loop(): a loop with prior steps and recorded spend
    test_transcript_survives_a_switch(): earlier steps are not discarded
    test_spend_survives_a_switch(): the run's accumulated cost is not reset
    test_breaker_survives_a_switch(): the ceilings still apply after a switch
"""

from pathlib import Path

from agent.circuit_breaker import CircuitBreaker
from agent.cost_tracker import CostTracker
from agent.llm_client import Provider, ScriptedLLM
from agent.loop import AgentConfig, AgentLoop, Step
from tui.commands import switch_model


def _seeded_loop(tmp_path: Path) -> tuple[AgentLoop, CostTracker]:
    """Builds a loop that already has history and recorded spend.

    Args:
        tmp_path: Checkout the loop is pointed at.

    Returns:
        loop: Loop with two prior steps replayed into it.
        tracker: Tracker holding the spend recorded so far.
    """
    tracker = CostTracker(budget_usd=5.0)
    tracker.record("claude-haiku-4-5", 1_000, 500)
    config = AgentConfig(repo_path=str(tmp_path), task="carry on", cost_tracker=tracker)
    config.breaker = CircuitBreaker(max_iterations=7, max_cost_usd=2.0)
    loop = AgentLoop(ScriptedLLM([]), config)
    loop.resume([Step(index=0, thought="first"), Step(index=1, thought="second")])
    return loop, tracker


def test_transcript_survives_a_switch(tmp_path: Path) -> None:
    """Asserts switching provider mid-run keeps every step already taken."""
    loop, _ = _seeded_loop(tmp_path)

    switch_model(loop, "openai", lambda provider, model: ScriptedLLM([]))

    assert [step.thought for step in loop.transcript] == ["first", "second"]


def test_spend_survives_a_switch(tmp_path: Path) -> None:
    """Asserts a provider switch does not reset the run's accumulated spend."""
    loop, tracker = _seeded_loop(tmp_path)
    before = tracker.total_usd()

    switch_model(loop, "openai", lambda provider, model: ScriptedLLM([]))

    assert tracker.total_usd() == before
    assert before > 0


def test_breaker_survives_a_switch(tmp_path: Path) -> None:
    """Asserts the ceilings configured before the switch still govern the run."""
    loop, _ = _seeded_loop(tmp_path)

    switch_model(loop, Provider.ANTHROPIC.value, lambda provider, model: ScriptedLLM([]))

    assert loop.config.breaker.max_iterations == 7
    assert loop.config.breaker.max_cost_usd == 2.0
