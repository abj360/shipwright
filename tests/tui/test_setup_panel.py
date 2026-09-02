#!/usr/bin/env python3
"""
test_setup_panel.py --- covers credential detection and .env persistence

Contains:
    test_every_provider_reported_missing(): a keyless environment needs setup
    test_present_key_is_not_reported(): a configured provider is left alone
    test_persist_key_writes_owner_only_file(): the .env file is not world-readable
    test_persist_key_replaces_existing_entry(): re-saving does not duplicate a variable
"""

import stat
from pathlib import Path

from agent.llm_client import CREDENTIAL_ENV_VARS, Provider
from tui.widgets.setup_panel import detect_missing, persist_key


def test_every_provider_reported_missing(keyless_environ: dict[str, str]) -> None:
    """Asserts a keyless environment reports every provider as needing a key."""
    missing = detect_missing(keyless_environ)

    assert {status.provider for status in missing} == set(CREDENTIAL_ENV_VARS)


def test_present_key_is_not_reported(keyless_environ: dict[str, str]) -> None:
    """Asserts a provider with a credential set is not reported as missing."""
    environ = keyless_environ | {CREDENTIAL_ENV_VARS[Provider.ANTHROPIC]: "sk-ant-configured"}

    missing = detect_missing(environ)

    assert Provider.ANTHROPIC not in {status.provider for status in missing}


def test_persist_key_writes_owner_only_file(keyless_repo: Path) -> None:
    """Asserts the written .env file is readable only by its owner."""
    env_path = persist_key("ANTHROPIC_API_KEY", "sk-ant-example", keyless_repo)

    assert "ANTHROPIC_API_KEY=sk-ant-example" in env_path.read_text()
    assert stat.S_IMODE(env_path.stat().st_mode) == 0o600


def test_persist_key_replaces_existing_entry(keyless_repo: Path) -> None:
    """Asserts saving a second time replaces the entry rather than appending one."""
    persist_key("ANTHROPIC_API_KEY", "sk-ant-first", keyless_repo)
    env_path = persist_key("ANTHROPIC_API_KEY", "sk-ant-second", keyless_repo)

    body = env_path.read_text()
    assert body.count("ANTHROPIC_API_KEY=") == 1
    assert "sk-ant-second" in body
