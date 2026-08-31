#!/usr/bin/env python3
"""
test_plan_panel.py --- covers the plan panel's accept, discard, and timeout paths

Contains:
    _sample_plan(): a two-step plan used across the cases
    test_accepting_releases_the_waiting_run(): accept unblocks and approves
    test_discarding_releases_the_waiting_run(): discard unblocks and refuses
    test_timeout_is_treated_as_a_refusal(): silence never approves a plan
    test_hint_line_names_both_keys(): the footer hint lists accept and discard
"""

from agent.planner import Plan, PlanStep
from tui.widgets.plan_panel import PlanPanel


def _sample_plan() -> Plan:
    """Builds a small plan for the panel to render.

    Returns:
        plan: Two-step plan attributed to a sample task.
    """
    return Plan(
        task="add a health endpoint",
        steps=[
            PlanStep(index=0, description="read the server module"),
            PlanStep(index=1, description="add the route"),
        ],
    )


def test_accepting_releases_the_waiting_run() -> None:
    """Asserts accepting the plan unblocks the waiting run with approval."""
    panel = PlanPanel(_sample_plan())

    panel.action_accept()

    assert panel.wait_for_decision(timeout_s=0.1) is True


def test_discarding_releases_the_waiting_run() -> None:
    """Asserts discarding the plan unblocks the waiting run with a refusal."""
    panel = PlanPanel(_sample_plan())

    panel.action_reject()

    assert panel.wait_for_decision(timeout_s=0.1) is False


def test_timeout_is_treated_as_a_refusal() -> None:
    """Asserts an unanswered plan is refused rather than silently executed."""
    panel = PlanPanel(_sample_plan())

    assert panel.wait_for_decision(timeout_s=0.01) is False


def test_hint_line_names_both_keys() -> None:
    """Asserts the hint line tells the operator both keys they can press."""
    hint = PlanPanel(_sample_plan()).hint_line()

    assert "accept" in hint
    assert "discard" in hint
