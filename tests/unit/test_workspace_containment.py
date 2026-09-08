#!/usr/bin/env python3
"""
test_workspace_containment.py --- asserts a run stays in the checkout it was given

Pins the failure where an agent pointed at one folder walked out into the home
directory and ran a system-wide install.

Contains:
    test_real_escape_from_the_incident(): the exact command that walked out is caught
    test_home_reference_is_caught(): ~ is treated as leaving the checkout
    test_parent_climb_is_caught(): ../.. above the root is caught
    test_work_inside_the_checkout_is_allowed(): ordinary commands are untouched
    test_system_tooling_is_allowed(): interpreters and binaries still resolve
    test_escape_is_refused_without_a_gate(): no gate means refusal, not execution
    test_gate_can_decline(): a declining gate refuses the command
    test_gate_can_approve(): an approving gate lets it through
    test_gate_is_told_why(): the gate receives the command and the reason
"""

from pathlib import Path

from agent.tool_dispatcher import ToolDispatcher
from agent.workspace import find_escapes

INCIDENT_COMMAND = (
    "cd /home/uapb-ai/Projects/llmjudge && pip install -q -r requirements.txt "
    "--break-system-packages"
)


def test_real_escape_from_the_incident(tmp_path: Path) -> None:
    """Asserts the command that actually walked out of the checkout is caught."""
    escapes = find_escapes(INCIDENT_COMMAND, tmp_path)

    assert escapes
    assert "/home/uapb-ai/Projects/llmjudge" in escapes[0].token


def test_home_reference_is_caught(tmp_path: Path) -> None:
    """Asserts a ~ reference counts as leaving the checkout."""
    assert find_escapes("cat ~/.claude.json", tmp_path)


def test_parent_climb_is_caught(tmp_path: Path) -> None:
    """Asserts climbing above the checkout root is caught."""
    assert find_escapes("cd ../../ && ls", tmp_path)


def test_work_inside_the_checkout_is_allowed(tmp_path: Path) -> None:
    """Asserts ordinary in-checkout work is not flagged."""
    assert find_escapes("python3 -m pytest -q tests/", tmp_path) == []
    assert find_escapes("cat README.md && ls docs/", tmp_path) == []


def test_system_tooling_is_allowed(tmp_path: Path) -> None:
    """Asserts interpreters and system binaries are not treated as escapes."""
    assert find_escapes("/usr/bin/python3 -m pip list", tmp_path) == []
    assert find_escapes("/bin/sh -c 'echo hi'", tmp_path) == []


def test_escape_is_refused_without_a_gate(tmp_path: Path) -> None:
    """Asserts an escape fails closed when no approval gate is configured."""
    result = ToolDispatcher(tmp_path).dispatch("run_shell", {"command": "ls /home"})

    assert result.ok is False
    assert "leaves" in (result.error or "")


def test_gate_can_decline(tmp_path: Path) -> None:
    """Asserts a declining gate refuses the command."""
    dispatcher = ToolDispatcher(tmp_path, escape_gate=lambda command, reason: False)

    assert dispatcher.dispatch("run_shell", {"command": "ls /home"}).ok is False


def test_gate_can_approve(tmp_path: Path) -> None:
    """Asserts an approving gate lets the command run."""
    dispatcher = ToolDispatcher(tmp_path, escape_gate=lambda command, reason: True)

    result = dispatcher.dispatch("run_shell", {"command": "echo out /home"})

    assert result.ok is True
    assert "out" in result.output


def test_gate_is_told_why(tmp_path: Path) -> None:
    """Asserts the gate is handed the command and the reason it was stopped."""
    asked: list[tuple[str, str]] = []

    def gate(command: str, reason: str) -> bool:
        asked.append((command, reason))
        return False

    ToolDispatcher(tmp_path, escape_gate=gate).dispatch("run_shell", {"command": "ls /home"})

    assert len(asked) == 1
    assert "ls /home" in asked[0][0]
    assert "/home" in asked[0][1]
