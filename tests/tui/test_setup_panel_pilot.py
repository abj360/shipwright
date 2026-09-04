#!/usr/bin/env python3
"""
test_setup_panel_pilot.py --- drives the setup panel through a headless Textual pilot

Contains:
    SetupHarness: minimal app hosting just the setup panel
    test_saving_a_key_writes_the_env_file(): a pasted key reaches .env
    test_pasted_key_is_never_displayed(): the input masks what was typed
"""

import asyncio
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Input

from agent.llm_client import Provider
from tui.widgets.setup_panel import CredentialStatus, SetupPanel

ANTHROPIC_MISSING = CredentialStatus(Provider.ANTHROPIC, "ANTHROPIC_API_KEY", False)
SAMPLE_KEY = "sk-ant-api03-Qr7TbV3wKd8ZnH2yPcE5uJf0RgXa91Lm"


class SetupHarness(App[None]):
    """Hosts the setup panel on its own so a pilot can drive it.

    Attributes:
        repo_path: Checkout the panel writes its .env into.
    """

    def __init__(self, repo_path: Path) -> None:
        """Builds the harness around one checkout.

        Args:
            repo_path: Checkout the panel writes its .env into.
        """
        super().__init__()
        self.repo_path = repo_path

    def compose(self) -> ComposeResult:
        """Mounts the setup panel with a single missing provider."""
        yield SetupPanel(self.repo_path, [ANTHROPIC_MISSING])


async def _save_key(repo_path: Path, key: str) -> str:
    """Types a key into the panel and presses Save.

    Args:
        repo_path: Checkout the panel writes its .env into.
        key: Credential to type into the masked input.

    Returns:
        rendered: What the input widget would display after typing.
    """
    app = SetupHarness(repo_path)
    async with app.run_test() as pilot:
        entry = app.query_one(f"#setup-key", Input)
        entry.value = key
        rendered = str(entry.render())
        await pilot.click("#setup-save")
        await pilot.pause()
    return rendered


def test_saving_a_key_writes_the_env_file(keyless_repo: Path) -> None:
    """Asserts pressing Save persists the pasted key into the checkout's .env."""
    asyncio.run(_save_key(keyless_repo, SAMPLE_KEY))

    assert f"ANTHROPIC_API_KEY={SAMPLE_KEY}" in (keyless_repo / ".env").read_text()


def test_pasted_key_is_never_displayed(keyless_repo: Path) -> None:
    """Asserts the masked input does not render the credential on screen."""
    rendered = asyncio.run(_save_key(keyless_repo, SAMPLE_KEY))

    assert SAMPLE_KEY not in rendered
