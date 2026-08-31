#!/usr/bin/env python3
"""
test_plan_gate.py --- covers the confirmation gate guarding plan execution

Contains:
    StubPlanner: returns a fixed plan without calling a model
    _build_loop(): wires a loop in plan-execute mode around a stub planner
    test_plan_runs_when_no_gate_configured(): unattended runs still execute
    test_declined_plan_executes_nothing(): a refused plan touches no tool
    test_accepted_plan_executes_its_steps(): an approved plan runs as before
"""

from pathlib import Path

from agent.circuit_breaker import CircuitBreaker
from agent.llm_client import ScriptedLLM
from agent.loop import AgentConfig, AgentLoop
from agent.planner import Plan, PlanStep


class StubPlanner:
    """Returns one fixed plan so the gate can be tested without a model.

    Attributes:
        plan: Plan handed back for every task.
    """

    def __init__(self, plan: Plan) -> None:
        """Stores the plan this stub always returns.

        Args:
            plan: Plan handed back for every task.
        """
        self.plan = plan

    def build_plan(self, task: str) -> Plan:
        """Returns the fixed plan regardless of the task.

        Args:
            task: Ignored; the stub is positional.

        Returns:
            plan: The plan this stub was built with.
        """
        return self.plan


def _build_loop(tmp_path: Path) -> tuple[AgentLoop, AgentConfig]:
    """Wires a plan-execute loop around a stub planner.

    Args:
        tmp_path: Checkout the loop is pointed at.

    Returns:
        loop: Loop ready to run in plan-execute mode.
        config: The config the loop was built from.
    """
    plan = Plan(task="tidy up", steps=[PlanStep(index=0, description="list the checkout")])
    config = AgentConfig(repo_path=str(tmp_path), task="tidy up", mode="plan_execute")
    config.planner = StubPlanner(plan)  # type: ignore[assignment]
    config.breaker = CircuitBreaker(max_iterations=10, max_cost_usd=1.0)
    return AgentLoop(ScriptedLLM([]), config), config


def test_plan_runs_when_no_gate_configured(tmp_path: Path) -> None:
    """Asserts a run with no gate still executes its plan unattended."""
    loop, _ = _build_loop(tmp_path)

    result = loop.run()

    assert result.final_answer is not None


def test_declined_plan_executes_nothing(tmp_path: Path) -> None:
    """Asserts refusing the plan leaves the transcript empty and returns no answer."""
    loop, config = _build_loop(tmp_path)
    config.plan_gate = lambda plan: False

    result = loop.run()

    assert result.final_answer is None
    assert result.steps == []


def test_accepted_plan_executes_its_steps(tmp_path: Path) -> None:
    """Asserts approving the plan runs its steps exactly as before the gate existed."""
    loop, config = _build_loop(tmp_path)
    seen: list[str] = []
    config.plan_gate = lambda plan: seen.append(plan.task) is None

    result = loop.run()

    assert seen == ["tidy up"]
    assert result.final_answer is not None
