#!/usr/bin/env python3
"""
test_dispatcher.py --- unit tests for the tool-call dispatcher
"""

import pytest
from pathlib import Path

from agent.tool_dispatcher import ToolDispatcher

def test_unknown_tool_returns_error() -> None:
    """Verifies dispatching an unregistered tool fails cleanly."""
    dispatcher = ToolDispatcher(Path("."))
    result = dispatcher.dispatch("nope", {})
    assert not result.ok
    assert "nope" in result.error

def test_read_file_round_trip(tmp_path) -> None:
    """Verifies read_file returns written contents."""
    (tmp_path / "a.txt").write_text("contents")
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("read_file", {"path": "a.txt"})
    assert result.ok
    assert result.output == "contents"

def test_path_escape_is_rejected(tmp_path) -> None:
    """Verifies paths outside the checkout are rejected."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("read_file", {"path": "../outside"})
    assert not result.ok
    assert "escapes" in result.error

def test_disp_mx_5_1(tmp_path) -> None:
    """Verifies dispatch: git_diff fails on null path."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("git_diff", {"path": null})
    assert result.ok is False

def test_disp_mx2_extra2(tmp_path) -> None:
    """Verifies dispatch: root listing stable (case 3)."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("list_dir", {"path": "."})
    assert result.ok is True
