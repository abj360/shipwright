#!/usr/bin/env python3
"""
test_resume.py --- covers /resume routing and transcript replay

Contains:
    _write_transcript(): writes a two-step transcript to a temp file
    test_rows_are_marked_historical(): replayed rows are dimmed
    test_failed_step_is_flagged(): an error observation marks the row failed
    test_router_dispatches_resume(): /resume reaches its handler
    test_plain_text_is_not_a_command(): an ordinary task is left alone
    test_missing_transcript_raises(): a path that does not exist fails loudly
    test_bare_resume_shows_usage(): /resume with no path explains itself
    test_absent_path_reports_itself(): a wrong path is reported, not raised
    test_malformed_tool_args_survive(): a non-object tool_args does not crash
"""

import json
from pathlib import Path

import pytest

from tui.commands import CommandRouter
from tui.transcript import MISSING_PATH_NOTICE, describe_resume, load_prior_rows, resume


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


def test_missing_transcript_raises(tmp_path: Path) -> None:
    """Asserts pointing resume at a missing file fails rather than silently passing."""
    with pytest.raises(FileNotFoundError):
        load_prior_rows(tmp_path / "absent.json")


def test_bare_resume_shows_usage() -> None:
    """Asserts a bare /resume explains what it needs instead of failing."""
    assert resume("") == MISSING_PATH_NOTICE
    assert resume("   ") == MISSING_PATH_NOTICE


def test_absent_path_reports_itself(tmp_path: Path) -> None:
    """Asserts a wrong path is reported to the operator rather than raising."""
    message = resume(str(tmp_path / "nope.json"))

    assert "no transcript at" in message


def test_malformed_tool_args_survive(tmp_path: Path) -> None:
    """Asserts a transcript whose tool_args is not an object still loads."""
    path = tmp_path / "odd.json"
    path.write_text(json.dumps([{"thought": "x", "tool_name": "read_file", "tool_args": "oops"}]))

    rows = load_prior_rows(path)

    assert rows[0].target == ""
