#!/usr/bin/env python3
"""
setup_panel.py --- first-run panel collecting a missing provider API key

Contains:
    CredentialStatus: whether one provider has a usable credential
    detect_missing(): lists providers whose credential is unset
    persist_key(): writes one provider credential into the .env file
    confirmation_line(): renders a save confirmation carrying no credential
    SetupPanel: prompts for a provider key on first run
    SetupPanel.target(): the provider this panel is currently collecting for
    SetupPanel.is_needed(): whether any provider still requires a key
    SetupPanel.compose(): builds the provider choice, masked input, and buttons
    SetupPanel.on_button_pressed(): saves the key or skips setup
    SetupPanel.Saved: reports which variable was written, never its value
    SetupPanel.Skipped: reports that setup was dismissed without a key
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from textual.app import ComposeResult
from textual.css.query import NoMatches
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Static

from agent.llm_client import CREDENTIAL_ENV_VARS, Provider
from tui.redaction import redact_secrets

ENV_FILENAME = ".env"
ENV_FILE_MODE = 0o600
KEY_INPUT_ID = "setup-key"
SAVE_BUTTON_ID = "setup-save"
SKIP_BUTTON_ID = "setup-skip"
PROVIDER_SET_ID = "setup-provider"
STATUS_LABEL_ID = "setup-status"
EMPTY_KEY_NOTICE = "Paste a key first, or choose Skip for now."


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


def detect_missing(environ: Mapping[str, str] | None = None) -> list[CredentialStatus]:
    """Lists the providers whose credential is absent from the environment.

    Args:
        environ: Environment to inspect; defaults to the process environment.

    Returns:
        missing: Status entries for providers that still need a key.
    """
    source: Mapping[str, str] = os.environ if environ is None else environ
    statuses = [
        CredentialStatus(provider, env_var, bool(source.get(env_var, "").strip()))
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


def confirmation_line(env_var: str, env_path: Path, key: str) -> str:
    """Renders the line the timeline shows once a key has been saved.

    The entered key is passed only so it can be scrubbed: the panel feeds the
    result straight into the visible timeline, which is persisted with the
    rest of the transcript.

    Args:
        env_var: Environment variable that was written.
        env_path: File the credential was written to.
        key: Credential the operator pasted, removed from the output.

    Returns:
        line: Confirmation text with no credential left in it.
    """
    return redact_secrets(f"Saved {env_var} to {env_path}", [key])


class SetupPanel(Static):
    """Prompts for a provider API key when none is configured yet.

    Attributes:
        repo_path: Checkout whose .env file the entered key is written to.
        missing: Providers still waiting on a credential.
    """

    class Saved(Message):
        """Reports that a credential was written, without carrying its value.

        Attributes:
            env_var: Environment variable that was written.
            env_path: File the credential was written to.
        """

        def __init__(self, env_var: str, env_path: Path) -> None:
            """Records which variable was written and where.

            Args:
                env_var: Environment variable that was written.
                env_path: File the credential was written to.
            """
            super().__init__()
            self.env_var = env_var
            self.env_path = env_path

    class Skipped(Message):
        """Reports that the operator dismissed setup without entering a key."""

    def __init__(self, repo_path: Path, missing: list[CredentialStatus] | None = None) -> None:
        """Builds the panel for whichever providers lack a credential.

        Args:
            repo_path: Checkout whose .env file the entered key is written to.
            missing: Providers to offer; detected from the environment when None.
        """
        super().__init__()
        self.repo_path = repo_path
        self.missing = detect_missing() if missing is None else missing

    def is_needed(self) -> bool:
        """Reports whether the panel has anything left to ask for.

        Returns:
            is_needed: True while at least one provider lacks a credential.
        """
        return bool(self.missing)

    def target(self) -> CredentialStatus:
        """Returns the provider whose credential the panel is collecting.

        Returns:
            status: Provider currently selected, or the first one offered.
        """
        try:
            chosen = self.query_one(f"#{PROVIDER_SET_ID}", RadioSet).pressed_index
        except NoMatches:
            return self.missing[0]
        if chosen < 0 or chosen >= len(self.missing):
            return self.missing[0]
        return self.missing[chosen]

    def compose(self) -> ComposeResult:
        """Builds the provider choice, the masked key input, and the buttons."""
        if not self.is_needed():
            yield Label("Every provider already has a key configured.")
            return

        choices = [
            RadioButton(status.env_var, value=index == 0)
            for index, status in enumerate(self.missing)
        ]
        yield Vertical(
            Label("Shipwright needs a model provider key to run."),
            RadioSet(*choices, id=PROVIDER_SET_ID),
            Input(placeholder="paste key here", password=True, id=KEY_INPUT_ID),
            Label("", id=STATUS_LABEL_ID),
            Horizontal(
                Button("Save key", variant="primary", id=SAVE_BUTTON_ID),
                Button("Skip for now", id=SKIP_BUTTON_ID),
            ),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Saves the entered key, or dismisses setup when Skip was pressed.

        Args:
            event: Button press identifying which control was activated.
        """
        if event.button.id == SKIP_BUTTON_ID:
            self.post_message(self.Skipped())
            return
        if event.button.id != SAVE_BUTTON_ID:
            return

        entry = self.query_one(f"#{KEY_INPUT_ID}", Input)
        key = entry.value.strip()
        status = self.query_one(f"#{STATUS_LABEL_ID}", Label)
        if not key:
            status.update(EMPTY_KEY_NOTICE)
            return

        target = self.target()
        env_path = persist_key(target.env_var, key, self.repo_path)
        # Clear the field before the confirmation renders: the widget keeps its
        # value in the DOM, and the transcript snapshots the DOM.
        entry.value = ""
        status.update(confirmation_line(target.env_var, env_path, key))
        self.post_message(self.Saved(target.env_var, env_path))
