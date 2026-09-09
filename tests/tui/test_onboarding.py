#!/usr/bin/env python3
"""
test_onboarding.py --- covers the first-run provider-and-key flow

Contains:
    _keyless(): clears every provider credential from the environment
    test_panel_appears_with_no_key(): a fresh machine is asked to set up
    test_panel_offers_every_provider(): the operator picks which provider to use
    test_saving_dismisses_onboarding(): a verified key clears the panel
    test_skipping_dismisses_onboarding(): declining also clears the panel
    test_panel_absent_once_configured(): a configured machine is not asked again
    test_enter_submits_the_key(): the Enter key verifies, no button needed
    test_rejected_key_is_not_stored(): a key the provider refuses is not saved
    test_unreachable_provider_still_stores_the_key(): offline does not re-prompt
    test_force_setup_reopens_onboarding(): --setup asks again despite a stored key
    test_setup_command_reopens_onboarding(): /setup asks again mid-session
    test_setup_offers_configured_providers_too(): switching provider is possible
"""

import asyncio
from pathlib import Path

import pytest

from agent.llm_client import CREDENTIAL_ENV_VARS
from tui.app import ShipwrightApp
from tui.screens.composer import Composer
from tui.widgets.setup_panel import SetupPanel, Verification


def _keyless(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clears every provider credential from the environment.

    Args:
        monkeypatch: Fixture used to unset the variables.
    """
    for env_var in CREDENTIAL_ENV_VARS.values():
        monkeypatch.delenv(env_var, raising=False)


def _accept(provider: object, key: str) -> Verification:
    """Stands in for a provider that accepts the key.

    Args:
        provider: Ignored.
        key: Ignored.

    Returns:
        result: A clean verification.
    """
    return Verification(is_rejected=False, message="")


def _reject(provider: object, key: str) -> Verification:
    """Stands in for a provider that refuses the key.

    Args:
        provider: Ignored.
        key: Ignored.

    Returns:
        result: A refusal from the provider.
    """
    return Verification(is_rejected=True, message="provider returned 401")


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
            if action in {"save", "enter"}:
                panel = app.query_one(SetupPanel)
                panel.query_one("#setup-key").value = "sk-ant-entered-by-hand"
                if action == "enter":
                    panel.query_one("#setup-key").focus()
                    await pilot.press("enter")
                else:
                    await pilot.click("#setup-save")
                for _ in range(30):
                    await pilot.pause()
                    await asyncio.sleep(0.02)
                    if not app.query(SetupPanel):
                        break
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

    app = ShipwrightApp(tmp_path)
    app.credential_verifier = _accept

    remaining, focused = _panel_count(app, action="save")

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


def test_enter_submits_the_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserts Enter in the key field completes setup, with no button press."""
    _keyless(monkeypatch)
    app = ShipwrightApp(tmp_path)
    app.credential_verifier = _accept

    remaining, _ = _panel_count(app, action="enter")

    assert remaining == 0
    assert (tmp_path / ".env").exists()


def test_rejected_key_is_not_stored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserts a key the provider refuses is neither saved nor allowed through."""
    _keyless(monkeypatch)
    app = ShipwrightApp(tmp_path)
    app.credential_verifier = _reject

    remaining, _ = _panel_count(app, action="save")

    assert remaining == 1
    assert not (tmp_path / ".env").exists()


def _unreachable(provider: object, key: str) -> Verification:
    """Stands in for a provider that cannot be reached at all.

    Args:
        provider: Ignored.
        key: Ignored.

    Returns:
        result: Not a refusal, just an unreachable provider.
    """
    return Verification(is_rejected=False, message="ConnectError: connection refused")


def test_unreachable_provider_still_stores_the_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Asserts an unreachable provider does not cost the operator their key.

    Being offline says nothing about whether a key is valid, and discarding it
    means being asked for it again on every single launch.
    """
    _keyless(monkeypatch)
    app = ShipwrightApp(tmp_path)
    app.credential_verifier = _unreachable

    remaining, _ = _panel_count(app, action="save")

    assert remaining == 0
    assert "ANTHROPIC_API_KEY" in (tmp_path / ".env").read_text()


def test_force_setup_reopens_onboarding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserts --setup asks again even though a credential is already stored.

    Uninstalling never removes a key: it lives in the checkout's .env, not in
    the install. Without this there is no way back to onboarding at all.
    """
    _keyless(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-already-configured")

    remaining, _ = _panel_count(ShipwrightApp(tmp_path, force_setup=True))

    assert remaining == 1


def test_setup_command_reopens_onboarding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserts /setup brings onboarding back mid-session."""
    _keyless(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-already-configured")
    app = ShipwrightApp(tmp_path)

    async def _run() -> tuple[int, int]:
        async with app.run_test() as pilot:
            await pilot.pause()
            before = len(app.query(SetupPanel))
            app.handle_line("/setup")
            for _ in range(20):
                await pilot.pause()
                await asyncio.sleep(0.02)
                if app.query(SetupPanel):
                    break
            return before, len(app.query(SetupPanel))

    before, after = asyncio.run(_run())

    assert (before, after) == (0, 1)


def test_setup_offers_configured_providers_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Asserts re-running setup lists every provider, so one can be swapped."""
    _keyless(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-already-configured")
    app = ShipwrightApp(tmp_path, force_setup=True)

    async def _run() -> set[str]:
        async with app.run_test() as pilot:
            await pilot.pause()
            return {status.env_var for status in app.query_one(SetupPanel).missing}

    assert asyncio.run(_run()) == set(CREDENTIAL_ENV_VARS.values())
