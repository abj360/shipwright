#!/usr/bin/env python3
"""
setup_panel.py --- first-run panel collecting a missing provider API key

Contains:
    CredentialStatus: whether one provider has a usable credential
    detect_missing(): lists providers whose credential is unset
    persist_key(): writes one provider credential into the .env file
    SetupPanel: prompts for a provider key on first run
    SetupPanel.compose(): builds the prompt, input, and save button
    SetupPanel.on_button_pressed(): saves the key that was entered
"""

import os
from dataclasses import dataclass
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, Input, Label, Static

from agent.llm_client import CREDENTIAL_ENV_VARS, Provider

ENV_FILENAME = ".env"
ENV_FILE_MODE = 0o600
KEY_INPUT_ID = "setup-key"
SAVE_BUTTON_ID = "setup-save"


@dataclass(frozen=True)
class CredentialStatus:
    """Records whether one provider can be used without further setup.

    Attributes:
        provider: Provider the status describes.
        env_var: Environment variable holding that provider's credential.
        is_present: True when the credential is set and non-empty.
    """

    provider: Provider
    env_var: str
    is_present: bool


def detect_missing(environ: dict[str, str] | None = None) -> list[CredentialStatus]:
    """Lists the providers whose credential is absent from the environment.

    Args:
        environ: Environment to inspect; defaults to the process environment.

    Returns:
        missing: Status entries for providers that still need a key.
    """
    source = os.environ if environ is None else environ
    statuses = [
        CredentialStatus(
            provider=provider,
            env_var=env_var,
            is_present=bool(source.get(env_var, "").strip()),
        )
        for provider, env_var in CREDENTIAL_ENV_VARS.items()
    ]
    return [status for status in statuses if not status.is_present]


def persist_key(env_var: str, key: str, repo_path: Path) -> Path:
    """Writes one provider credential into the checkout's .env file.

    The file is created with owner-only permissions so a key never lands in a
    world-readable file, and an existing entry for the same variable is
    replaced rather than duplicated.

    Args:
        env_var: Environment variable name to write.
        key: Credential value to store.
        repo_path: Checkout whose .env file is updated.

    Returns:
        env_path: Path of the .env file that was written.
    """
    env_path = repo_path / ENV_FILENAME
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    kept = [line for line in lines if not line.startswith(f"{env_var}=")]
    kept.append(f"{env_var}={key}")
    env_path.write_text("\n".join(kept) + "\n")
    env_path.chmod(ENV_FILE_MODE)
    return env_path


class SetupPanel(Static):
    """Prompts for a provider API key when none is configured yet.

    Attributes:
        repo_path: Checkout whose .env file the entered key is written to.
        missing: Providers still waiting on a credential.
    """

    def __init__(self, repo_path: Path) -> None:
        """Builds the panel for whichever providers lack a credential.

        Args:
            repo_path: Checkout whose .env file the entered key is written to.
        """
        super().__init__()
        self.repo_path = repo_path
        self.missing = detect_missing()

    def compose(self) -> ComposeResult:
        """Builds the prompt, the key input, and the save button."""
        target = self.missing[0]
        yield Vertical(
            Label(f"No {target.env_var} found. Paste a key to get started."),
            Input(placeholder=target.env_var, id=KEY_INPUT_ID),
            Button("Save key", id=SAVE_BUTTON_ID),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Saves the entered key and reports where it was written.

        Args:
            event: Button press identifying which control was activated.
        """
        if event.button.id != SAVE_BUTTON_ID:
            return
        entry = self.query_one(f"#{KEY_INPUT_ID}", Input)
        key = entry.value.strip()
        if not key:
            return
        target = self.missing[0]
        env_path = persist_key(target.env_var, key, self.repo_path)
        self.post_message(self.Saved(target.env_var, key, env_path))

    class Saved(Input.Changed):
        """Signals that a credential was written to disk."""
