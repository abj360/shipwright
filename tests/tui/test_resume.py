#!/usr/bin/env python3
"""
test_resume.py --- covers /resume routing and transcript replay

Contains:
    _write_transcript(): writes a two-step transcript to a temp file
    test_rows_are_marked_historical(): replayed rows are dimmed
    test_failed_step_is_flagged(): an error observation marks the row failed
    test_router_dispatches_resume(): /resume reaches its handler
    test_plain_text_is_not_a_command(): an ordinary task is left alone
"""

import json
from pathlib import Path

from tui.commands import CommandRouter
from tui.transcript import describe_resume, load_prior_rows


def _write_transcript(tmp_path: Path) -> Path:
    """Writes a two-step transcript for the loader to read.

    Args:
        tmp_path: Per-test temporary directory.

    Returns:
        path: File the transcript was written to.
    """
    path = tmp_path / "run.json"
    path.write_text(
        json.dumps(
            [
                {"thought": "look", "tool_name": "read_file", "tool_args": {"path": "a.py"}},
                {
                    "thought": "try",
                    "tool_name": "run_shell",
                    "tool_args": {"command": "pytest"},
                    "observation": "error: boom",
                },
            ]
        )
    )
    return path


def test_rows_are_marked_historical(tmp_path: Path) -> None:
    """Asserts every replayed row is flagged so the timeline dims it."""
    rows = load_prior_rows(_write_transcript(tmp_path))

    assert [row.label for row in rows] == ["Read", "Ran"]
    assert all(row.is_historical for row in rows)


def test_failed_step_is_flagged(tmp_path: Path) -> None:
    """Asserts a step whose observation was an error is marked failed."""
    rows = load_prior_rows(_write_transcript(tmp_path))

    assert rows[0].failed is False
    assert rows[1].failed is True


def test_router_dispatches_resume(tmp_path: Path) -> None:
    """Asserts a typed /resume reaches the handler with its argument."""
    router = CommandRouter()
    path = _write_transcript(tmp_path)
    router.register("resume", lambda arg: describe_resume(load_prior_rows(Path(arg))))

    assert router.dispatch(f"/resume {path}") == "resumed 2 earlier steps"


def test_plain_text_is_not_a_command() -> None:
    """Asserts an ordinary task line is not treated as a command."""
    assert CommandRouter().dispatch("add a health endpoint") is None
