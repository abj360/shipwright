#!/usr/bin/env python3
"""
plan_panel.py --- dashed-border panel showing a proposed plan before it runs

Contains:
    PlanPanel: renders a proposed plan and waits for an explicit decision
    PlanPanel.compose(): lists the proposed steps
    PlanPanel.hint_line(): renders the accept and discard key hints
    PlanPanel.action_accept(): approves the plan and releases the run
    PlanPanel.action_reject(): discards the plan and releases the run
    PlanPanel.wait_for_decision(): blocks a worker until the operator answers
    PlanPanel.Decided: reports the operator's answer to the app
"""

import threading

from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widgets import Label, Static

from agent.planner import Plan

ACCEPT_KEY = "a"
REJECT_KEY = "escape"


class PlanPanel(Static):
    """Renders a proposed plan and blocks execution until it is answered.

    Attributes:
        plan: Plan awaiting the operator's decision.
        is_accepted: True once the plan has been approved.
    """

    DEFAULT_CSS = """
    PlanPanel {
        border: dashed $accent;
        padding: 1 2;
    }
    """

    BINDINGS = [
        Binding(ACCEPT_KEY, "accept", "Accept plan"),
        Binding(REJECT_KEY, "reject", "Discard plan"),
    ]

    class Decided(Message):
        """Reports the operator's answer for one proposed plan.

        Attributes:
            is_accepted: True when the operator approved the plan.
        """

        def __init__(self, is_accepted: bool) -> None:
            """Records the answer the operator gave.

            Args:
                is_accepted: True when the operator approved the plan.
            """
            super().__init__()
            self.is_accepted = is_accepted

    def __init__(self, plan: Plan) -> None:
        """Builds the panel around one proposed plan.

        Args:
            plan: Plan awaiting the operator's decision.
        """
        super().__init__()
        self.plan = plan
        self.is_accepted = False
        self._answered = threading.Event()

    def compose(self) -> ComposeResult:
        """Lists the proposed steps above the accept and discard hints."""
        yield Label(f"Proposed plan for: {self.plan.task}")
        for step in self.plan.steps:
            yield Label(f"{step.index + 1}. {step.description}")
        yield Label(self.hint_line())

    def hint_line(self) -> str:
        """Renders the key hints shown under the proposed steps.

        Returns:
            hint: One line naming the accept and discard keys.
        """
        return f"[{ACCEPT_KEY}] accept    [esc] discard"

    def action_accept(self) -> None:
        """Approves the plan and lets the waiting run proceed."""
        self._decide(True)

    def action_reject(self) -> None:
        """Discards the plan and lets the waiting run return empty-handed."""
        self._decide(False)

    def _decide(self, is_accepted: bool) -> None:
        """Records one decision and releases anything waiting on it.

        Args:
            is_accepted: True when the operator approved the plan.
        """
        self.is_accepted = is_accepted
        self._answered.set()
        self.post_message(self.Decided(is_accepted))

    def wait_for_decision(self, timeout_s: float | None = None) -> bool:
        """Blocks the calling worker until the operator answers.

        The agent loop runs off the UI thread, so it parks here rather than
        polling. A timeout is treated as a refusal so an unattended run can
        never execute a plan nobody approved.

        Args:
            timeout_s: Seconds to wait before treating silence as a refusal.

        Returns:
            is_accepted: True only when the operator explicitly approved.
        """
        if not self._answered.wait(timeout_s):
            return False
        return self.is_accepted
