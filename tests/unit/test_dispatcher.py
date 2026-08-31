#!/usr/bin/env python3
"""
test_dispatcher.py --- unit tests for the tool-call dispatcher
"""

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
    result = dispatcher.dispatch("git_diff", {"path": None})
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
    result = dispatcher.dispatch("run_shell", {"path": None})
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


def test_disp_case_output_truncated(tmp_path: Path) -> None:
    """Verifies dispatcher behavior: output is truncated to budget."""
    (tmp_path / "big.txt").write_text("z" * 9000)
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("read_file", {"path": "big.txt"})
    assert len(result.output) <= 8000


def test_missing_required_arg_is_an_error() -> None:
    """Verifies calls missing required args fail before touching tools."""
    dispatcher = ToolDispatcher(Path("."))
    result = dispatcher.dispatch("read_file", {})
    assert not result.ok
    assert "missing args" in result.error


def test_dispatch_list_dir_defaults_to_root(tmp_path: Path) -> None:
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


def test_dispatch_list_dir_missing_dir(tmp_path: Path) -> None:
    """Verifies dispatch behavior: missing dir."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("list_dir", {"path": "missing-dir"})
    assert result.ok is False


def test_disp_case_resolve_dotdot(tmp_path: Path) -> None:
    """Verifies dispatcher behavior: dotdot escape rejected."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("read_file", {"path": "a/../../etc/passwd"})
    assert not result.ok


def test_disp_case_error_is_toolresult(tmp_path: Path) -> None:
    """Verifies dispatcher behavior: errors carry a message."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("read_file", {})
    assert result.error


def test_dispatch_read_file_missing_path(tmp_path: Path) -> None:
    """Verifies dispatch behavior: missing path."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("read_file", {})
    assert result.ok is False


def test_disp_case_shell_stderr(tmp_path: Path) -> None:
    """Verifies dispatcher behavior: stderr is captured."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("run_shell", {"command": "echo e >&2"})
    assert "e" in result.output


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
    result = dispatcher.dispatch("read_file", {"path": None})
    assert result.ok is False


def test_dispatch_write_file_missing_content_ok(tmp_path: Path) -> None:
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
    result = dispatcher.dispatch("list_dir", {"path": None})
    assert result.ok is False


def test_disp_case_shell_cwd(tmp_path: Path) -> None:
    """Verifies dispatcher behavior: shell runs in the checkout."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("run_shell", {"command": "pwd"})
    assert str(tmp_path) in result.output


def test_disp_mx2_extra4(tmp_path) -> None:
    """Verifies dispatch: root listing stable (case 5)."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("list_dir", {"path": "."})
    assert result.ok is True


def test_disp_mx_4_1(tmp_path) -> None:
    """Verifies dispatch: run_tests fails on null path."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("run_tests", {"path": None})
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


def test_disp_case_resolve_nested(tmp_path: Path) -> None:
    """Verifies dispatcher behavior: nested paths resolve."""
    dispatcher = ToolDispatcher(tmp_path)
    resolved = dispatcher._resolve("a/b/c")
    assert str(resolved).endswith("a/b/c")


def test_apply_patch_rejects_empty_patch(tmp_path) -> None:
    """Verifies an empty patch is rejected before invoking git."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("apply_patch", {"patch": " "})
    assert not result.ok


def test_disp_mx2_extra5(tmp_path) -> None:
    """Verifies dispatch: root listing stable (case 6)."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("list_dir", {"path": "."})
    assert result.ok is True


def test_write_file_creates_parents(tmp_path) -> None:
    """Verifies write_file creates missing parent directories."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("write_file", {"path": "x/y/z.txt", "content": "hi"})
    assert result.ok
    assert (tmp_path / "x" / "y" / "z.txt").read_text() == "hi"


def test_dispatch_run_tests_no_selector_allowed(tmp_path: Path) -> None:
    """Verifies dispatch behavior: no selector allowed."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("run_tests", {})
    assert result.ok is True


def test_disp_mx_0_0(tmp_path) -> None:
    """Verifies dispatch: list_dir without args lists the checkout root."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("list_dir", {})
    assert result.ok is True


def test_dispatch_run_shell_missing_command(tmp_path: Path) -> None:
    """Verifies dispatch behavior: missing command."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("run_shell", {})
    assert result.ok is False


def test_disp_mx2_1(tmp_path) -> None:
    """Verifies dispatch: missing subdir errors."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("list_dir", {"path": "sub"})
    assert result.ok is False


def test_disp_mx2_10(tmp_path) -> None:
    """Verifies dispatch: diff with path runs."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("git_diff", {"path": "x.py"})
    assert result.ok is True


def test_run_shell_captures_output(tmp_path) -> None:
    """Verifies run_shell returns combined output."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("run_shell", {"command": "echo hello"})
    assert result.ok
    assert "hello" in result.output


def test_disp_mx2_13(tmp_path) -> None:
    """Verifies dispatch: missing patch rejected."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("apply_patch", {})
    assert result.ok is False


def test_disp_mx2_extra6(tmp_path) -> None:
    """Verifies dispatch: root listing stable (case 7)."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("list_dir", {"path": "."})
    assert result.ok is True


def test_disp_case_resolve_root(tmp_path: Path) -> None:
    """Verifies dispatcher behavior: dot resolves to the root."""
    dispatcher = ToolDispatcher(tmp_path)
    resolved = dispatcher._resolve(".")
    assert resolved == tmp_path.resolve()


def test_disp_case_read_missing_file(tmp_path: Path) -> None:
    """Verifies dispatcher behavior: reading a missing file errors."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("read_file", {"path": "nope.txt"})
    assert not result.ok


def test_disp_mx2_0(tmp_path) -> None:
    """Verifies dispatch: root listing works."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("list_dir", {"path": "."})
    assert result.ok is True


def test_disp_mx2_extra1(tmp_path) -> None:
    """Verifies dispatch: root listing stable (case 2)."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("list_dir", {"path": "."})
    assert result.ok is True


def test_disp_mx2_14(tmp_path) -> None:
    """Verifies dispatch: empty patch rejected."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("apply_patch", {"patch": ""})
    assert result.ok is False


def test_dispatch_git_diff_no_path_allowed(tmp_path: Path) -> None:
    """Verifies dispatch behavior: no path allowed."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("git_diff", {})
    assert result.ok is True


def test_dispatch_read_file_empty_path(tmp_path: Path) -> None:
    """Verifies dispatch behavior: empty path."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("read_file", {"path": ""})
    assert result.ok is False


def test_disp_mx2_9(tmp_path) -> None:
    """Verifies dispatch: diff runs."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("git_diff", {})
    assert result.ok is True


def test_disp_mx2_2(tmp_path) -> None:
    """Verifies dispatch: missing file errors."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("read_file", {"path": "f.txt"})
    assert result.ok is False


def test_disp_mx_5_0(tmp_path) -> None:
    """Verifies dispatch: git_diff runs with no required args."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("git_diff", {})
    assert result.ok is True


def test_disp_mx_2_0(tmp_path) -> None:
    """Verifies dispatch: run_shell fails without args."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("run_shell", {})
    assert result.ok is False


def test_disp_case_write_overwrite(tmp_path: Path) -> None:
    """Verifies dispatcher behavior: write_file overwrites."""
    (tmp_path / "x.txt").write_text("old")
    dispatcher = ToolDispatcher(tmp_path)
    dispatcher.dispatch("write_file", {"path": "x.txt", "content": "new"})
    assert (tmp_path / "x.txt").read_text() == "new"


def test_disp_mx_4_0(tmp_path) -> None:
    """Verifies dispatch: run_tests runs with no required args."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("run_tests", {})
    assert result.ok is True


def test_disp_mx_3_1(tmp_path) -> None:
    """Verifies dispatch: write_file fails on null path."""
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch("write_file", {"path": None})
    assert result.ok is False


def test_describe_tools_covers_the_whole_registry(tmp_path: Path) -> None:
    """Verifies the prompt description cannot drift from the registered tools."""
    dispatcher = ToolDispatcher(tmp_path)
    described = dispatcher.describe_tools()
    for name in dispatcher._tools:
        assert f"- {name}:" in described


def test_describe_tools_names_required_arguments(tmp_path: Path) -> None:
    """Verifies a tool's required arguments are spelled out for the model."""
    described = ToolDispatcher(tmp_path).describe_tools()
    assert "write_file" in described
    assert "path=..." in described
    assert "content=..." in described


def test_edit_file_replaces_only_the_matching_line(tmp_path: Path) -> None:
    """Verifies an edit leaves every other line of the file untouched."""
    (tmp_path / "calc.py").write_text(
        "def add(a, b):\n    return a - b\n\n\ndef mul(a, b):\n    return a * b\n"
    )
    dispatcher = ToolDispatcher(tmp_path)
    result = dispatcher.dispatch(
        "edit_file", {"path": "calc.py", "find": "return a - b", "replace": "return a + b"}
    )
    assert result.ok
    assert (tmp_path / "calc.py").read_text() == (
        "def add(a, b):\n    return a + b\n\n\ndef mul(a, b):\n    return a * b\n"
    )


def test_edit_file_keeps_the_original_indentation(tmp_path: Path) -> None:
    """Verifies a model need not reproduce leading whitespace to edit a line."""
    (tmp_path / "m.py").write_text("class C:\n        deeply = 1\n")
    ToolDispatcher(tmp_path).dispatch(
        "edit_file", {"path": "m.py", "find": "deeply = 1", "replace": "deeply = 2"}
    )
    assert (tmp_path / "m.py").read_text() == "class C:\n        deeply = 2\n"


def test_edit_file_refuses_an_ambiguous_match(tmp_path: Path) -> None:
    """Verifies a line appearing twice is refused rather than guessed at."""
    (tmp_path / "m.py").write_text("x = 1\ny = 2\nx = 1\n")
    result = ToolDispatcher(tmp_path).dispatch(
        "edit_file", {"path": "m.py", "find": "x = 1", "replace": "x = 3"}
    )
    assert not result.ok
    assert "2 lines match" in result.error
    assert (tmp_path / "m.py").read_text() == "x = 1\ny = 2\nx = 1\n"


def test_edit_file_reports_a_line_that_is_not_there(tmp_path: Path) -> None:
    """Verifies a miss is an error the model can act on, not a silent no-op."""
    (tmp_path / "m.py").write_text("x = 1\n")
    result = ToolDispatcher(tmp_path).dispatch(
        "edit_file", {"path": "m.py", "find": "nope", "replace": "y = 2"}
    )
    assert not result.ok
    assert "no line matching" in result.error


def test_edit_file_requires_something_to_find(tmp_path: Path) -> None:
    """Verifies an empty find is rejected before touching the file."""
    (tmp_path / "m.py").write_text("x = 1\n")
    result = ToolDispatcher(tmp_path).dispatch(
        "edit_file", {"path": "m.py", "find": "  ", "replace": "y = 2"}
    )
    assert not result.ok


def test_edit_file_needs_all_three_arguments(tmp_path: Path) -> None:
    """Verifies a partial call fails before the file is opened."""
    result = ToolDispatcher(tmp_path).dispatch("edit_file", {"path": "m.py"})
    assert not result.ok
    assert "missing args" in result.error


def test_edit_file_matches_through_regex_escaping(tmp_path: Path) -> None:
    """Verifies a model escaping punctuation still lands its edit.

    Small models write find= as though it were a regex; the backslashes are
    theirs, not the file's, and must not decide whether the edit applies.
    """
    (tmp_path / "m.py").write_text("def multiply(a, b):\n    return a * b\n")
    result = ToolDispatcher(tmp_path).dispatch(
        "edit_file",
        {"path": "m.py", "find": r"def multiply\(a, b\):", "replace": "def product(a, b):"},
    )
    assert result.ok
    assert (tmp_path / "m.py").read_text() == "def product(a, b):\n    return a * b\n"


def test_edit_file_matches_through_uneven_whitespace(tmp_path: Path) -> None:
    """Verifies runs of spaces inside a line do not decide the match."""
    (tmp_path / "m.py").write_text("x   =    1\n")
    assert (
        ToolDispatcher(tmp_path)
        .dispatch("edit_file", {"path": "m.py", "find": "x = 1", "replace": "x = 2"})
        .ok
    )


def test_edit_file_shows_the_file_when_nothing_matches(tmp_path: Path) -> None:
    """Verifies a miss reports the real lines so the next attempt can be right."""
    (tmp_path / "m.py").write_text("alpha = 1\nbeta = 2\n")
    error = (
        ToolDispatcher(tmp_path)
        .dispatch("edit_file", {"path": "m.py", "find": "gamma = 3", "replace": "gamma = 4"})
        .error
    )
    assert "1: alpha = 1" in error
    assert "2: beta = 2" in error
