#!/usr/bin/env python3
"""
test_step_row.py --- covers the Read/Edited/Ran activity row

Contains:
    test_summary_uses_the_shared_labels(): wording matches the shared label map
    test_summary_names_what_it_acted_on(): the path or command is shown
    test_collapsed_row_hides_its_output(): output only appears when expanded
    test_toggle_opens_and_closes(): toggling flips the disclosure state
    test_target_prefers_path_then_command(): the target argument is chosen in order
"""

from tui.widgets.step_row import COLLAPSED_MARKER, EXPANDED_MARKER, StepRow, step_target


def test_summary_uses_the_shared_labels() -> None:
    """Asserts the row's wording comes from the shared activity label map."""
    row = StepRow("read_file", {"path": "pkg/widget.py"}, "contents")

    assert "Read" in row.summary_line()


def test_summary_names_what_it_acted_on() -> None:
    """Asserts the collapsed summary names the file or command involved."""
    row = StepRow("run_shell", {"command": "pytest -q"}, "ok")

    summary = row.summary_line()

    assert summary.startswith(COLLAPSED_MARKER)
    assert "Ran" in summary
    assert "pytest -q" in summary


def test_collapsed_row_hides_its_output() -> None:
    """Asserts a collapsed row reveals none of its observation."""
    row = StepRow("read_file", {"path": "a.py"}, "line one\nline two")

    assert row.detail_lines() == []


def test_toggle_opens_and_closes() -> None:
    """Asserts toggling reveals the output and then hides it again."""
    row = StepRow("read_file", {"path": "a.py"}, "line one\nline two")

    row.action_toggle()
    assert row.detail_lines() == ["line one", "line two"]
    assert row.summary_line().startswith(EXPANDED_MARKER)

    row.action_toggle()
    assert row.detail_lines() == []


def test_target_prefers_path_then_command() -> None:
    """Asserts the target is chosen from the recognized arguments in order."""
    assert step_target({"path": "a.py", "command": "ls"}) == "a.py"
    assert step_target({"command": "ls"}) == "ls"
    assert step_target({"depth": "2"}) == ""
