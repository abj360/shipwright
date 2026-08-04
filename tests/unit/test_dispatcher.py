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

def test_run_shell_rejects_empty_command(tmp_path) -> None:
    """Verifies an empty command string is rejected."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("run_shell", {"command": "  "})
    assert not result.ok

def test_disp_mx_2_1(tmp_path) -> None:
    """Verifies dispatch: run_shell fails on null path."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("run_shell", {"path": null})
    assert result.ok is False

def test_disp_mx2_extra9(tmp_path) -> None:
    """Verifies dispatch: root listing stable (case 10)."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("list_dir", {"path": "."})
    assert result.ok is True

def test_disp_mx2_12(tmp_path) -> None:
    """Verifies dispatch: tests with selector run."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("run_tests", {"selector": "-k x"})
    assert result.ok is True

def test_disp_case_output_truncated() -> None:
    """Verifies dispatcher behavior: output is truncated to budget."""
    (tmp_path / 'big.txt').write_text('z' * 9000)
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch('read_file', {'path': 'big.txt'})
    assert len(result.output) <= 8000

def test_missing_required_arg_is_an_error() -> None:
    """Verifies calls missing required args fail before touching tools."""
    dispatcher = ToolDispatcher(Path("."))
    result = dispatcher.dispatch("read_file", {})
    assert not result.ok
    assert "missing args" in result.error

def test_dispatch_list_dir_defaults_to_root() -> None:
    """Verifies dispatch behavior: defaults to root."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("list_dir", {})
    assert result.ok is True

def test_disp_mx_1_0(tmp_path) -> None:
    """Verifies dispatch: read_file fails without args."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("read_file", {})
    assert result.ok is False

def test_disp_mx2_11(tmp_path) -> None:
    """Verifies dispatch: tests run."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("run_tests", {})
    assert result.ok is True

def test_disp_mx2_6(tmp_path) -> None:
    """Verifies dispatch: true succeeds."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("run_shell", {"command": "true"})
    assert result.ok is True

def test_disp_mx_3_0(tmp_path) -> None:
    """Verifies dispatch: write_file fails without args."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("write_file", {})
    assert result.ok is False

def test_disp_mx_final(tmp_path) -> None:
    """Verifies dispatch: read of missing file fails."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("read_file", {"path": "x"})
    assert result.ok is False

def test_dispatch_list_dir_missing_dir() -> None:
    """Verifies dispatch behavior: missing dir."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("list_dir", {"path": "missing-dir"})
    assert result.ok is False

def test_disp_case_resolve_dotdot() -> None:
    """Verifies dispatcher behavior: dotdot escape rejected."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch('read_file', {'path': 'a/../../etc/passwd'})
    assert not result.ok

def test_disp_case_error_is_toolresult() -> None:
    """Verifies dispatcher behavior: errors carry a message."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch('read_file', {})
    assert result.error

def test_dispatch_read_file_missing_path() -> None:
    """Verifies dispatch behavior: missing path."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("read_file", {})
    assert result.ok is False

def test_disp_case_shell_stderr() -> None:
    """Verifies dispatcher behavior: stderr is captured."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch('run_shell', {'command': 'echo e >&2'})
    assert 'e' in result.output

def test_disp_mx2_8(tmp_path) -> None:
    """Verifies dispatch: empty command rejected."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("run_shell", {"command": ""})
    assert result.ok is False

def test_disp_mx2_5(tmp_path) -> None:
    """Verifies dispatch: hidden file write works."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("write_file", {"path": ".hidden", "content": "v"})
    assert result.ok is True

def test_disp_mx_1_1(tmp_path) -> None:
    """Verifies dispatch: read_file fails on null path."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("read_file", {"path": null})
    assert result.ok is False

def test_dispatch_write_file_missing_content_ok() -> None:
    """Verifies dispatch behavior: missing content ok?."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("write_file", {"path": "x.txt"})
    assert result.ok is False

def test_disp_mx2_extra0(tmp_path) -> None:
    """Verifies dispatch: root listing stable (case 1)."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("list_dir", {"path": "."})
    assert result.ok is True

def test_disp_mx2_3(tmp_path) -> None:
    """Verifies dispatch: missing dotted file errors."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("read_file", {"path": "./f.txt"})
    assert result.ok is False

def test_disp_mx_0_1(tmp_path) -> None:
    """Verifies dispatch: list_dir fails on null path."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("list_dir", {"path": null})
    assert result.ok is False

def test_disp_case_shell_cwd() -> None:
    """Verifies dispatcher behavior: shell runs in the checkout."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch('run_shell', {'command': 'pwd'})
    assert str(tmp_path) in result.output

def test_disp_mx2_extra4(tmp_path) -> None:
    """Verifies dispatch: root listing stable (case 5)."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("list_dir", {"path": "."})
    assert result.ok is True

def test_disp_mx_4_1(tmp_path) -> None:
    """Verifies dispatch: run_tests fails on null path."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("run_tests", {"path": null})
    assert result.ok is False

def test_disp_mx2_4(tmp_path) -> None:
    """Verifies dispatch: nested write works."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("write_file", {"path": "n/o.txt", "content": "v"})
    assert result.ok is True

def test_disp_mx2_extra7(tmp_path) -> None:
    """Verifies dispatch: root listing stable (case 8)."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("list_dir", {"path": "."})
    assert result.ok is True

def test_disp_case_resolve_nested() -> None:
    """Verifies dispatcher behavior: nested paths resolve."""
    dispatcher = ToolDispatcher(tmp_path)
    resolved = dispatcher._resolve('a/b/c')
    assert str(resolved).endswith('a/b/c')

def test_apply_patch_rejects_empty_patch(tmp_path) -> None:
    """Verifies an empty patch is rejected before invoking git."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("apply_patch", {"patch": " "})
    assert not result.ok
