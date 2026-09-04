#!/usr/bin/env python3
"""
test_command_routing.py --- covers routing for /plan, /resume, and /model

Contains:
    _router(): a router with all three commands registered
    test_each_command_reaches_its_own_handler(): no command bleeds into another
    test_argument_is_passed_through(): everything after the name is the argument
    test_command_name_is_case_insensitive(): /MODEL routes like /model
    test_unknown_command_raises(): an unregistered command fails loudly
    test_plain_task_is_not_routed(): ordinary text is left for the agent
"""

import pytest

from tui.commands import CommandRouter, UnknownCommandError, parse_command


def _router(calls: list[tuple[str, str]]) -> CommandRouter:
    """Builds a router recording which handler ran with what argument.

    Args:
        calls: List each handler appends its name and argument to.

    Returns:
        router: Router with /plan, /resume, and /model registered.
    """
    router = CommandRouter()
    for name in ("plan", "resume", "model"):

        def handler(argument: str, name: str = name) -> str:
            calls.append((name, argument))
            return f"{name} ok"

        router.register(name, handler)
    return router


def test_each_command_reaches_its_own_handler() -> None:
    """Asserts each of the three commands runs its own handler and no other."""
    calls: list[tuple[str, str]] = []
    router = _router(calls)

    assert router.dispatch("/plan") == "plan ok"
    assert router.dispatch("/resume") == "resume ok"
    assert router.dispatch("/model") == "model ok"
    assert [name for name, _ in calls] == ["plan", "resume", "model"]


def test_argument_is_passed_through() -> None:
    """Asserts everything after the command name arrives as the argument."""
    calls: list[tuple[str, str]] = []

    _router(calls).dispatch("/model anthropic claude-opus-4-1")

    assert calls == [("model", "anthropic claude-opus-4-1")]


def test_command_name_is_case_insensitive() -> None:
    """Asserts a command typed in capitals routes the same as in lower case."""
    calls: list[tuple[str, str]] = []

    _router(calls).dispatch("/MODEL openai")

    assert calls == [("model", "openai")]


def test_unknown_command_raises() -> None:
    """Asserts an unregistered command is reported rather than silently ignored."""
    with pytest.raises(UnknownCommandError):
        _router([]).dispatch("/teleport")


def test_plain_task_is_not_routed() -> None:
    """Asserts ordinary text is not parsed as a command at all."""
    assert parse_command("plan the migration") is None
    assert _router([]).dispatch("plan the migration") is None
