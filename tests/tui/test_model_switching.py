#!/usr/bin/env python3
"""
test_model_switching.py --- covers the /model live provider switch

Contains:
    _loop(): builds a loop with a scripted backend
    _factory(): records the provider asked for and returns a scripted client
    test_switch_reports_the_new_provider(): a valid switch confirms itself
    test_switch_passes_the_model_through(): an explicit model reaches the factory
    test_unknown_provider_is_refused(): a bad provider name changes nothing
    test_missing_credential_is_reported(): the credential error reaches the operator
    test_bare_model_command_shows_usage(): /model alone explains itself
"""

from pathlib import Path

from agent.llm_client import LLMClient, MissingCredentialError, Provider, ScriptedLLM
from agent.loop import AgentConfig, AgentLoop
from tui.commands import USAGE_MODEL, switch_model


def _loop(tmp_path: Path) -> AgentLoop:
    """Builds a loop with a scripted backend.

    Args:
        tmp_path: Checkout the loop is pointed at.

    Returns:
        loop: Loop ready to have its backend swapped.
    """
    config = AgentConfig(repo_path=str(tmp_path), task="anything")
    return AgentLoop(ScriptedLLM([]), config)


def _factory(seen: list[tuple[Provider, str | None]]) -> object:
    """Builds a factory that records what it was asked for.

    Args:
        seen: List the factory appends each request to.

    Returns:
        factory: Callable matching the ClientFactory shape.
    """

    def build(provider: Provider, model: str | None) -> LLMClient:
        seen.append((provider, model))
        return ScriptedLLM([])

    return build


def test_switch_reports_the_new_provider(tmp_path: Path) -> None:
    """Asserts switching to a known provider confirms the change."""
    seen: list[tuple[Provider, str | None]] = []

    line = switch_model(_loop(tmp_path), "openai", _factory(seen))  # type: ignore[arg-type]

    assert "openai" in line
    assert seen == [(Provider.OPENAI, None)]


def test_switch_passes_the_model_through(tmp_path: Path) -> None:
    """Asserts an explicit model identifier is handed to the factory."""
    seen: list[tuple[Provider, str | None]] = []

    line = switch_model(
        _loop(tmp_path), "anthropic claude-opus-4-1", _factory(seen)
    )  # type: ignore[arg-type]

    assert seen == [(Provider.ANTHROPIC, "claude-opus-4-1")]
    assert "claude-opus-4-1" in line


def test_unknown_provider_is_refused(tmp_path: Path) -> None:
    """Asserts an unrecognized provider name is rejected without building a client."""
    seen: list[tuple[Provider, str | None]] = []

    line = switch_model(_loop(tmp_path), "mistral", _factory(seen))  # type: ignore[arg-type]

    assert line == USAGE_MODEL
    assert seen == []


def test_missing_credential_is_reported(tmp_path: Path) -> None:
    """Asserts a missing provider credential is surfaced instead of crashing."""

    def build(provider: Provider, model: str | None) -> LLMClient:
        raise MissingCredentialError("OPENAI_API_KEY is not set")

    line = switch_model(_loop(tmp_path), "openai", build)

    assert "OPENAI_API_KEY is not set" in line


def test_bare_model_command_shows_usage(tmp_path: Path) -> None:
    """Asserts /model with no argument explains itself instead of switching."""
    seen: list[tuple[Provider, str | None]] = []

    assert switch_model(_loop(tmp_path), "", _factory(seen)) == USAGE_MODEL  # type: ignore[arg-type]
    assert seen == []
