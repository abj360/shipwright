#!/usr/bin/env python3
"""
test_app_commands.py --- covers the slash commands the app actually registers

Contains:
    _app(): builds an app against a temporary checkout
    test_every_documented_command_is_registered(): no command is advertised but missing
    test_model_switches_the_provider(): /model retargets later runs
    test_model_records_the_chosen_model(): the switch is remembered for later runs
    test_model_without_a_key_is_refused(): a provider with no credential is rejected
    test_model_rejects_an_unknown_provider(): a typo does not change the provider
    test_plan_toggles_plan_mode(): /plan turns plan-then-execute on and off
"""

import asyncio
from collections.abc import Callable
from pathlib import Path

import pytest

from tui.app import ShipwrightApp
from tui.commands import USAGE_MODEL

DOCUMENTED_COMMANDS = {"plan", "resume", "model", "max-cost", "max-steps"}


def _app(tmp_path: Path) -> ShipwrightApp:
    """Builds an app against a temporary checkout.

    Args:
        tmp_path: Checkout the app is pointed at.

    Returns:
        app: Configured application instance.
    """
    return ShipwrightApp(tmp_path, provider="anthropic")


def _mounted[T](app: ShipwrightApp, action: Callable[[], T]) -> T:
    """Runs one action against a mounted app.

    Args:
        app: Application to mount.
        action: Called once the app has settled.

    Returns:
        result: Whatever the action returned.
    """

    async def _run() -> T:
        async with app.run_test() as pilot:
            await pilot.pause()
            return action()

    return asyncio.run(_run())


def test_every_documented_command_is_registered(tmp_path: Path) -> None:
    """Asserts every command the README advertises has a handler behind it."""
    app = _app(tmp_path)

    registered = _mounted(app, lambda: set(app.router.handlers))

    assert registered >= DOCUMENTED_COMMANDS


def test_model_switches_the_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserts /model retargets the provider later runs will use."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
    app = _app(tmp_path)

    line = _mounted(app, lambda: app.handle_line("/model openai"))

    assert "openai" in line
    assert app.provider == "openai"


def test_model_records_the_chosen_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserts an explicit model is remembered for the runs that follow."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
    app = _app(tmp_path)

    line = _mounted(app, lambda: app.handle_line("/model openai gpt-4.1"))

    assert "gpt-4.1" in line
    assert (app.provider, app.model) == ("openai", "gpt-4.1")


def test_model_without_a_key_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserts switching to a provider with no credential is reported, not silent."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = _app(tmp_path)

    line = _mounted(app, lambda: app.handle_line("/model openai"))

    assert "OPENAI_API_KEY" in line
    assert app.provider == "anthropic"


def test_model_rejects_an_unknown_provider(tmp_path: Path) -> None:
    """Asserts a mistyped provider leaves the current one in place."""
    app = _app(tmp_path)

    line = _mounted(app, lambda: app.handle_line("/model mistral"))

    assert line == USAGE_MODEL
    assert app.provider == "anthropic"


def test_plan_toggles_plan_mode(tmp_path: Path) -> None:
    """Asserts /plan turns plan-then-execute on, and off again."""
    app = _app(tmp_path)

    def _toggle() -> tuple[bool, bool]:
        app.handle_line("/plan")
        first = app.plan_mode
        app.handle_line("/plan")
        return first, app.plan_mode

    turned_on, turned_off = _mounted(app, _toggle)

    assert turned_on is True
    assert turned_off is False
