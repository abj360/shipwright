#!/usr/bin/env python3
"""
test_onboarding.py --- covers the first-run provider-and-key flow

Contains:
    _keyless(): clears every provider credential from the environment
    test_panel_appears_with_no_key(): a fresh machine is asked to set up
    test_panel_offers_every_provider(): the operator picks which provider to use
    test_saving_dismisses_onboarding(): a stored key clears the panel
    test_skipping_dismisses_onboarding(): declining also clears the panel
    test_panel_absent_once_configured(): a configured machine is not asked again
"""

import asyncio
from pathlib import Path

import pytest

from agent.llm_client import CREDENTIAL_ENV_VARS
from tui.app import ShipwrightApp
from tui.screens.composer import Composer
from tui.widgets.setup_panel import SetupPanel


def _keyless(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clears every provider credential from the environment.

    Args:
        monkeypatch: Fixture used to unset the variables.
    """
    for env_var in CREDENTIAL_ENV_VARS.values():
        monkeypatch.delenv(env_var, raising=False)


def _panel_count(app: ShipwrightApp, action: str | None = None) -> tuple[int, bool]:
    """Mounts the app, optionally answers onboarding, and reports the outcome.

    Args:
        app: Application under test.
        action: "save", "skip", or None to leave the panel alone.

    Returns:
        remaining: How many setup panels are still mounted.
        composer_focused: Whether the caret ended up in the composer.
    """

    async def _run() -> tuple[int, bool]:
        async with app.run_test() as pilot:
            await pilot.pause()
            if action == "save":
                panel = app.query_one(SetupPanel)
                panel.query_one("#setup-key").value = "sk-ant-entered-by-hand"
                await pilot.click("#setup-save")
                await pilot.pause()
            elif action == "skip":
                await pilot.click("#setup-skip")
                await pilot.pause()
            await pilot.pause()
            focused = isinstance(app.focused, type(app.query_one(Composer).query_one("Input")))
            return len(app.query(SetupPanel)), focused

    return asyncio.run(_run())


def test_panel_appears_with_no_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserts a machine with no provider key is taken through setup."""
    _keyless(monkeypatch)

    remaining, _ = _panel_count(ShipwrightApp(tmp_path))

    assert remaining == 1


def test_panel_offers_every_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserts onboarding lets the operator choose which provider to use."""
    _keyless(monkeypatch)
    app = ShipwrightApp(tmp_path)

    async def _run() -> list[str]:
        async with app.run_test() as pilot:
            await pilot.pause()
            return [status.env_var for status in app.query_one(SetupPanel).missing]

    assert set(asyncio.run(_run())) == set(CREDENTIAL_ENV_VARS.values())


def test_saving_dismisses_onboarding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserts storing a key clears the panel and hands over to the composer."""
    _keyless(monkeypatch)

    remaining, focused = _panel_count(ShipwrightApp(tmp_path), action="save")

    assert remaining == 0
    assert focused is True
    assert (tmp_path / ".env").exists()


def test_skipping_dismisses_onboarding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserts declining setup still lets the operator reach the composer."""
    _keyless(monkeypatch)

    remaining, focused = _panel_count(ShipwrightApp(tmp_path), action="skip")

    assert remaining == 0
    assert focused is True


def test_panel_absent_once_configured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserts a machine that already has a key is not asked to set up again."""
    _keyless(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-configured")

    remaining, _ = _panel_count(ShipwrightApp(tmp_path))

    assert remaining == 0
