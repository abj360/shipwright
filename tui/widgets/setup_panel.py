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
    SetupPanel.on_input_submitted(): verifies and saves when Enter is pressed
    SetupPanel.on_button_pressed(): saves the key or skips setup
    SetupPanel.submit_key(): verifies whatever is currently typed
    SetupPanel.action_skip(): dismisses setup from the keyboard
    SetupPanel.Saved: reports which variable was written, never its value
    SetupPanel.Skipped: reports that setup was dismissed without a key
    verify_credential(): proves a key works with one real completion
    DEFAULT_MODELS_BY_ENV: the model each provider verifies against
"""

import os
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.message import Message
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Static

from agent.llm_client import (
    CREDENTIAL_ENV_VARS,
    DEFAULT_MODELS,
    MissingCredentialError,
    Provider,
    build_client,
)
from agent.llm_client import (
    Message as LLMMessage,
)
from tui.redaction import redact_secrets

ENV_FILENAME = ".env"
ENV_FILE_MODE = 0o600
KEY_INPUT_ID = "setup-key"
SAVE_BUTTON_ID = "setup-save"
SKIP_BUTTON_ID = "setup-skip"
PROVIDER_SET_ID = "setup-provider"
STATUS_LABEL_ID = "setup-status"
EMPTY_KEY_NOTICE = "Paste a key first, or choose Skip for now."
VERIFYING_NOTICE = "verifying the key with a real completion…"
VERIFIED_TEMPLATE = "verified against {model} — saved to {path}"
PANEL_TITLE = "Welcome to shipwright"
SECURITY_NOTE = "Runs sandboxed. Only this folder is mounted."
PROVIDER_PROMPT = "Choose a model provider:"
KEY_HINT = "enter to verify and save   ·   esc to skip"
VERIFY_TIMEOUT_S = 30.0


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


def verify_credential(provider: Provider, key: str) -> str:
    """Proves a credential works by asking its provider for one real completion.

    OpenClaw verifies a key before storing it, and the reason is sound: a
    rejected key discovered on the first real task looks like a broken agent
    rather than a typo. The check is deliberately tiny.

    Args:
        provider: Provider the credential belongs to.
        key: Credential to test.

    Returns:
        error: Empty when the key works, otherwise why it did not.
    """
    previous = os.environ.get(CREDENTIAL_ENV_VARS[provider])
    os.environ[CREDENTIAL_ENV_VARS[provider]] = key
    try:
        client = build_client(provider)
        client.complete([LLMMessage(role="user", content="hi")], "Reply with one word.", 16)
    except MissingCredentialError as exc:
        return str(exc)
    except Exception as exc:  # noqa: BLE001 - any provider failure is a failed check
        return f"{type(exc).__name__}: {exc}"
    finally:
        if previous is None:
            with suppress(KeyError):
                del os.environ[CREDENTIAL_ENV_VARS[provider]]
        else:
            os.environ[CREDENTIAL_ENV_VARS[provider]] = previous
    return ""


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
        verifier: Proves a key works; injected so tests need no provider.
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

    BINDINGS = [Binding("escape", "skip", "Skip setup")]

    def __init__(
        self,
        repo_path: Path,
        missing: list[CredentialStatus] | None = None,
        verifier: Callable[[Provider, str], str] | None = None,
    ) -> None:
        """Builds the panel for whichever providers lack a credential.

        Args:
            repo_path: Checkout whose .env file the entered key is written to.
            missing: Providers to offer; detected from the environment when None.
            verifier: Proves a key works; defaults to a real provider call.
        """
        super().__init__()
        self.repo_path = repo_path
        self.missing = detect_missing() if missing is None else missing
        self.verifier = verify_credential if verifier is None else verifier

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

    DEFAULT_CSS = """
    SetupPanel {
        border: round $accent;
        padding: 1 2;
        margin: 1 4;
        height: auto;
    }
    SetupPanel .setup-note { color: $text-muted; }
    SetupPanel .setup-status { color: $accent; }
    """

    def compose(self) -> ComposeResult:
        """Builds the provider choice, the masked key input, and the buttons."""
        if not self.is_needed():
            yield Label("Every provider already has a key configured.")
            return

        self.border_title = PANEL_TITLE
        yield Label(SECURITY_NOTE, classes="setup-note")
        yield Label(PROVIDER_PROMPT)
        yield RadioSet(
            *(
                RadioButton(
                    f"{status.provider.value}  ·  {DEFAULT_MODELS[status.provider]}",
                    value=index == 0,
                )
                for index, status in enumerate(self.missing)
            ),
            id=PROVIDER_SET_ID,
        )
        yield Input(placeholder="paste key here", password=True, id=KEY_INPUT_ID)
        yield Label(KEY_HINT, classes="setup-note")
        yield Label("", id=STATUS_LABEL_ID, classes="setup-status")
        yield Horizontal(
            Button("Verify and save", variant="primary", id=SAVE_BUTTON_ID),
            Button("Skip for now", id=SKIP_BUTTON_ID),
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Verifies and saves the key when Enter is pressed in the field.

        Args:
            event: Submission carrying the key that was typed.
        """
        if event.input.id != KEY_INPUT_ID:
            return
        event.stop()
        self.submit_key()

    def action_skip(self) -> None:
        """Dismisses setup from the keyboard."""
        self.post_message(self.Skipped())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Verifies and stores the entered key, or dismisses setup.

        Args:
            event: Button press identifying which control was activated.
        """
        if event.button.id == SKIP_BUTTON_ID:
            self.post_message(self.Skipped())
            return
        if event.button.id != SAVE_BUTTON_ID:
            return
        self.submit_key()

    def submit_key(self) -> None:
        """Verifies whatever is currently typed, then stores it if it works."""
        entry = self.query_one(f"#{KEY_INPUT_ID}", Input)
        status = self.query_one(f"#{STATUS_LABEL_ID}", Label)
        key = entry.value.strip()
        if not key:
            status.update(EMPTY_KEY_NOTICE)
            return

        target = self.target()
        status.update(VERIFYING_NOTICE)
        self.run_worker(lambda: self._verify_then_store(target, key), thread=True, exclusive=True)

    def _verify_then_store(self, target: CredentialStatus, key: str) -> None:
        """Checks the key against its provider, then hands the result back.

        Args:
            target: Provider the key belongs to.
            key: Credential the operator entered.
        """
        error = self.verifier(target.provider, key)
        self.app.call_from_thread(self._apply_verification, target, key, error)

    def _apply_verification(self, target: CredentialStatus, key: str, error: str) -> None:
        """Stores a verified key, or reports why it was rejected.

        Args:
            target: Provider the key belongs to.
            key: Credential the operator entered.
            error: Empty when the key worked, otherwise why it did not.
        """
        status = self.query_one(f"#{STATUS_LABEL_ID}", Label)
        if error:
            status.update(f"that key did not work — {error}")
            return

        env_path = persist_key(target.env_var, key, self.repo_path)
        # Apply it now as well: the run about to start reads the environment,
        # not the file, and re-prompting for a key just saved is nonsense.
        os.environ[target.env_var] = key
        self.query_one(f"#{KEY_INPUT_ID}", Input).value = ""
        status.update(
            VERIFIED_TEMPLATE.format(model=DEFAULT_MODELS[target.provider], path=env_path)
        )
        self.post_message(self.Saved(target.env_var, env_path))
