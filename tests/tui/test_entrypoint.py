#!/usr/bin/env python3
"""
test_entrypoint.py --- covers the ship console entrypoint and the --tui flag

Contains:
    test_defaults_point_at_the_current_checkout(): no arguments works
    test_repo_argument_is_honoured(): --repo selects the checkout
    test_provider_argument_is_honoured(): --provider selects the backend
    test_unknown_provider_is_rejected(): a bad provider fails at parse time
    test_cli_exposes_a_tui_flag(): shipwright --tui is a real flag
"""

from pathlib import Path

import pytest

from agent.cli import build_parser as build_cli_parser
from tui.__main__ import build_app, build_parser


def test_defaults_point_at_the_current_checkout() -> None:
    """Asserts running ship with no arguments targets the current directory."""
    app = build_app([])

    assert app.repo_path == Path(".")


def test_repo_argument_is_honoured(tmp_path: Path) -> None:
    """Asserts --repo points the interface at the given checkout."""
    app = build_app(["--repo", str(tmp_path)])

    assert app.repo_path == tmp_path


def test_provider_argument_is_honoured() -> None:
    """Asserts --provider selects which backend answers the run."""
    app = build_app(["--provider", "openai"])

    assert app.provider == "openai"


def test_unknown_provider_is_rejected() -> None:
    """Asserts an unsupported provider is refused at parse time."""
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--provider", "mistral"])


def test_cli_exposes_a_tui_flag() -> None:
    """Asserts the main entrypoint still offers --tui alongside its other modes."""
    args = build_cli_parser().parse_args(["--tui"])

    assert args.tui is True
