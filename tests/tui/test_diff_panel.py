#!/usr/bin/env python3
"""
test_diff_panel.py --- covers unified-diff parsing and line classification

Contains:
    SAMPLE_PATCH: a one-file diff with an add, a delete, and context
    test_file_path_is_read_from_the_header(): the b/ path names the file
    test_lines_are_classified(): each line lands in the right kind
    test_line_numbers_follow_the_hunk_header(): numbering restarts per hunk
    test_stats_count_adds_and_deletes(): the summary counts both sides
    test_empty_patch_parses_to_nothing(): no diff yields no files
    test_multi_file_diff_splits_per_file(): each file gets its own section
"""

from tui.widgets.diff_panel import LineKind, diff_stats, parse_diff

SAMPLE_PATCH = """diff --git a/pkg/widget.py b/pkg/widget.py
--- a/pkg/widget.py
+++ b/pkg/widget.py
@@ -10,3 +10,4 @@ def area(w, h):
 def area(w, h):
-    return w - h
+    return w * h
+
"""


def test_file_path_is_read_from_the_header() -> None:
    """Asserts the changed file is named from the diff header's b/ path."""
    files = parse_diff(SAMPLE_PATCH)

    assert [f.path for f in files] == ["pkg/widget.py"]


def test_lines_are_classified() -> None:
    """Asserts adds, deletes, hunks, and context each get their own kind."""
    lines = parse_diff(SAMPLE_PATCH)[0].lines
    kinds = [line.kind for line in lines]

    assert LineKind.HUNK in kinds
    assert LineKind.ADD in kinds
    assert LineKind.DELETE in kinds
    assert LineKind.CONTEXT in kinds


def test_line_numbers_follow_the_hunk_header() -> None:
    """Asserts numbering picks up from the hunk header rather than from one."""
    lines = parse_diff(SAMPLE_PATCH)[0].lines
    context = next(line for line in lines if line.kind is LineKind.CONTEXT)

    assert context.old_no == 10
    assert context.new_no == 10


def test_stats_count_adds_and_deletes() -> None:
    """Asserts the summary counts added and removed lines separately."""
    added, removed = diff_stats(parse_diff(SAMPLE_PATCH))

    assert (added, removed) == (2, 1)


def test_empty_patch_parses_to_nothing() -> None:
    """Asserts an empty diff produces no files rather than a stray entry."""
    assert parse_diff("") == []


def test_multi_file_diff_splits_per_file() -> None:
    """Asserts a diff touching two files is split into two sections."""
    patch = (
        "diff --git a/one.py b/one.py\n@@ -1 +1 @@\n-a\n+b\n"
        "diff --git a/two.py b/two.py\n@@ -1 +1 @@\n-c\n+d\n"
    )

    files = parse_diff(patch)

    assert [f.path for f in files] == ["one.py", "two.py"]
    assert diff_stats(files) == (2, 2)
