#!/usr/bin/env python3
"""
test_env_file.py --- covers loading a checkout's .env into the environment

Contains:
    test_pairs_are_parsed(): plain assignments are read
    test_comments_and_blanks_are_skipped(): noise lines are ignored
    test_export_prefix_is_tolerated(): a shell-style export still parses
    test_quoted_values_are_unwrapped(): surrounding quotes are stripped
    test_missing_file_is_not_an_error(): no .env yields no settings
    test_environment_wins_over_the_file(): an exported value is never replaced
    test_saved_key_survives_a_restart(): a key written to .env is picked up
"""

from pathlib import Path

import pytest

from agent.env_file import load_env_file, parse_env_file


def _write(tmp_path: Path, body: str) -> Path:
    """Writes a .env file into a checkout.

    Args:
        tmp_path: Per-test temporary directory.
        body: Contents of the .env file.

    Returns:
        repo_path: Checkout holding the written file.
    """
    (tmp_path / ".env").write_text(body)
    return tmp_path


def test_pairs_are_parsed(tmp_path: Path) -> None:
    """Asserts plain KEY=VALUE assignments are read out of the file."""
    repo = _write(tmp_path, "ANTHROPIC_API_KEY=sk-ant-1\nPORT=4000\n")

    assert parse_env_file(repo / ".env") == {"ANTHROPIC_API_KEY": "sk-ant-1", "PORT": "4000"}


def test_comments_and_blanks_are_skipped(tmp_path: Path) -> None:
    """Asserts comments and empty lines do not become settings."""
    repo = _write(tmp_path, "# a comment\n\n  \nPORT=4000\n")

    assert parse_env_file(repo / ".env") == {"PORT": "4000"}


def test_export_prefix_is_tolerated(tmp_path: Path) -> None:
    """Asserts a shell-style `export NAME=value` line still parses."""
    repo = _write(tmp_path, "export OPENAI_API_KEY=sk-openai\n")

    assert parse_env_file(repo / ".env") == {"OPENAI_API_KEY": "sk-openai"}


def test_quoted_values_are_unwrapped(tmp_path: Path) -> None:
    """Asserts a value wrapped in matching quotes loses them."""
    repo = _write(tmp_path, "REPO_URL=\"https://example.test/repo\"\nNAME='shipwright'\n")

    parsed = parse_env_file(repo / ".env")

    assert parsed["REPO_URL"] == "https://example.test/repo"
    assert parsed["NAME"] == "shipwright"


def test_missing_file_is_not_an_error(tmp_path: Path) -> None:
    """Asserts a checkout with no .env simply yields nothing."""
    assert parse_env_file(tmp_path / ".env") == {}
    assert load_env_file(tmp_path) == []


def test_environment_wins_over_the_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserts a value already exported is never replaced by the stored one."""
    repo = _write(tmp_path, "ANTHROPIC_API_KEY=sk-ant-from-file\n")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-from-shell")

    applied = load_env_file(repo)

    assert applied == []
    assert __import__("os").environ["ANTHROPIC_API_KEY"] == "sk-ant-from-shell"


def test_saved_key_survives_a_restart(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserts a key the setup panel stored is picked up on the next launch."""
    from tui.widgets.setup_panel import detect_missing, persist_key

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    persist_key("ANTHROPIC_API_KEY", "sk-ant-saved", tmp_path)

    load_env_file(tmp_path)

    missing = {status.env_var for status in detect_missing()}
    assert "ANTHROPIC_API_KEY" not in missing
