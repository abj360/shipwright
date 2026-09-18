#!/usr/bin/env python3
"""
test_update_prompt.py --- covers the update offered when a newer release is out

Contains:
    configured: keeps onboarding out of the way of the offer
    _app(): builds an app told that a given version is published
    test_offer_appears_when_a_newer_version_is_out(): both versions are named
    test_no_offer_when_up_to_date(): the same version is not an update
    test_no_offer_when_the_launcher_says_nothing(): a quiet network offers nothing
    test_accepting_leaves_the_marker_and_closes(): the launcher takes it from there
    test_skipping_dismisses_the_offer(): skip leaves the version alone
    test_offer_returns_next_launch(): skipping is for this launch only
"""

import asyncio
from pathlib import Path

import pytest

from tui.app import ShipwrightApp
from tui.screens.composer import Composer
from tui.sessions import UPDATE_MARKER
from tui.widgets.update_panel import UpdatePanel


@pytest.fixture(autouse=True)
def configured(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Gives every test a key and a state directory, as an install would.

    Args:
        monkeypatch: Fixture used to set the environment.
        tmp_path: Per-test temporary directory.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-configured")
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("SHIPWRIGHT_STATE_DIR", str(state))
    (state / "onboarded").touch()


def _app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, latest: str, current: str
) -> ShipwrightApp:
    """Builds an app told which version is published.

    Args:
        tmp_path: Checkout the app is pointed at.
        monkeypatch: Fixture used to set the environment.
        latest: Version the launcher found, empty when it found none.
        current: Version this install is running.

    Returns:
        app: Application under test.
    """
    monkeypatch.setenv("SHIPWRIGHT_UPDATE_AVAILABLE", latest)
    monkeypatch.setenv("SHIPWRIGHT_VERSION", current)
    return ShipwrightApp(tmp_path)


def _panels(app: ShipwrightApp, keys: list[str]) -> tuple[int, str]:
    """Mounts the app, presses keys, and reports what is left.

    Args:
        app: Application under test.
        keys: Keys to press once it has settled.

    Returns:
        remaining: How many offers are still shown.
        drawn: What the offer said, empty when there was none.
    """

    async def _run() -> tuple[int, str]:
        async with app.run_test() as pilot:
            await pilot.pause()
            offers = app.query(UpdatePanel)
            drawn = str(offers.first().render()) if offers else ""
            for key in keys:
                await pilot.press(key)
                await pilot.pause()
            return len(app.query(UpdatePanel)), drawn

    return asyncio.run(_run())


def test_offer_appears_when_a_newer_version_is_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Asserts the offer names the published version and the one running."""
    remaining, drawn = _panels(_app(tmp_path, monkeypatch, "1.2.0", "1.1.1"), [])

    assert remaining == 1
    assert "1.2.0" in drawn
    assert "1.1.1" in drawn
    assert "[enter] update" in drawn


def test_no_offer_when_up_to_date(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserts the running version being the published one is not an update."""
    remaining, _ = _panels(_app(tmp_path, monkeypatch, "1.1.1", "1.1.1"), [])

    assert remaining == 0


def test_no_offer_when_the_launcher_says_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Asserts nothing is offered when the launcher could not check."""
    remaining, _ = _panels(_app(tmp_path, monkeypatch, "", "1.1.1"), [])

    assert remaining == 0


def test_accepting_leaves_the_marker_and_closes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Asserts accepting records the session for the launcher and closes the interface."""
    app = _app(tmp_path, monkeypatch, "1.2.0", "1.1.1")

    _panels(app, ["enter"])

    marker = tmp_path / "state" / UPDATE_MARKER
    assert marker.read_text().strip() == app.session_id


def test_skipping_dismisses_the_offer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserts skipping takes the card away and hands the keyboard back."""
    app = _app(tmp_path, monkeypatch, "1.2.0", "1.1.1")

    async def _run() -> tuple[int, bool, bool]:
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            composer = app.query_one(Composer)
            focused = app.focused is not None and composer in app.focused.ancestors
            marker = (tmp_path / "state" / UPDATE_MARKER).exists()
            return len(app.query(UpdatePanel)), focused, marker

    remaining, focused, marker = asyncio.run(_run())

    assert (remaining, focused, marker) == (0, True, False)


def test_offer_returns_next_launch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserts skipping is only for that launch; the next one asks again."""
    _panels(_app(tmp_path, monkeypatch, "1.2.0", "1.1.1"), ["escape"])

    remaining, _ = _panels(_app(tmp_path, monkeypatch, "1.2.0", "1.1.1"), [])

    assert remaining == 1
