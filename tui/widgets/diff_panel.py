#!/usr/bin/env python3
"""
diff_panel.py --- renders a unified diff in the add/delete/hunk colour scheme

Contains:
    LineKind: how one diff line is classified
    DiffLine: one classified diff line with its line numbers
    DiffFile: one file's classified lines
    HUNK_HEADER_PATTERN: matches the line numbers in a hunk header
    FILE_MARKER_PREFIXES: old/new file markers that are not content lines
    _hunk_start(): reads the old and new starting lines out of a hunk header
    parse_diff(): parses a unified diff into per-file classified lines
    diff_stats(): counts added and removed lines across files
    DiffPanel: renders a parsed diff with per-line colour
    DiffPanel.compose(): lays out one section per changed file
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from textual.app import ComposeResult
from textual.widgets import Label, Static

from tui.theme import Palette, palette_for

HUNK_HEADER_PATTERN = re.compile(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
FILE_HEADER_PREFIX = "diff --git"
# The ---/+++ markers name the file; counting them as changes inflates every stat.
FILE_MARKER_PREFIXES = ("---", "+++")
EMPTY_DIFF_NOTICE = "no changes yet"


class LineKind(StrEnum):
    """Classifies one line of a unified diff."""

    ADD = "add"
    DELETE = "delete"
    CONTEXT = "context"
    HUNK = "hunk"


@dataclass(frozen=True)
class DiffLine:
    """Holds one classified diff line and the numbers it sits at.

    Attributes:
        kind: How the line is classified.
        text: Raw line text, including its leading marker.
        old_no: Line number on the old side, None when the line is new.
        new_no: Line number on the new side, None when the line was removed.
    """

    kind: LineKind
    text: str
    old_no: int | None
    new_no: int | None


@dataclass
class DiffFile:
    """Holds one file's classified diff lines.

    Attributes:
        path: Path of the file the hunks belong to.
        lines: Classified lines in the order they appear.
    """

    path: str
    lines: list[DiffLine] = field(default_factory=list)


def _hunk_start(line: str, old_no: int, new_no: int) -> tuple[int, int]:
    """Reads the starting line numbers out of a hunk header.

    Args:
        line: Hunk header line beginning with @@.
        old_no: Current old-side number, kept when the header is malformed.
        new_no: Current new-side number, kept when the header is malformed.

    Returns:
        old_no: Old-side line number the hunk starts at.
        new_no: New-side line number the hunk starts at.
    """
    match = HUNK_HEADER_PATTERN.search(line)
    if match is None:
        return old_no, new_no
    return int(match.group(1)), int(match.group(2))


def parse_diff(patch: str) -> list[DiffFile]:
    """Parses a unified diff into per-file lists of classified lines.

    Args:
        patch: Unified diff text as git produced it.

    Returns:
        files: One entry per changed file, in the order the diff lists them.
    """
    files: list[DiffFile] = []
    current: DiffFile | None = None
    old_no = 1
    new_no = 1
    for line in patch.split("\n"):
        if line.startswith(FILE_HEADER_PREFIX):
            path = line.rpartition(" b/")[2].strip() or "unknown"
            current = DiffFile(path=path)
            files.append(current)
            continue
        if current is None:
            continue
        if line.startswith(FILE_MARKER_PREFIXES):
            continue
        if line.startswith("+"):
            current.lines.append(DiffLine(LineKind.ADD, line, None, new_no))
            new_no += 1
        elif line.startswith("-"):
            current.lines.append(DiffLine(LineKind.DELETE, line, old_no, None))
            old_no += 1
        elif line.startswith("@@"):
            current.lines.append(DiffLine(LineKind.HUNK, line, None, None))
            old_no, new_no = _hunk_start(line, old_no, new_no)
        else:
            current.lines.append(DiffLine(LineKind.CONTEXT, line, old_no, new_no))
            old_no += 1
            new_no += 1
    return files


def diff_stats(files: Sequence[DiffFile]) -> tuple[int, int]:
    """Counts added and removed lines across every parsed file.

    Args:
        files: Parsed diff files.

    Returns:
        added: Number of added lines.
        removed: Number of removed lines.
    """
    lines = [line for changed in files for line in changed.lines]
    added = sum(1 for line in lines if line.kind is LineKind.ADD)
    removed = sum(1 for line in lines if line.kind is LineKind.DELETE)
    return added, removed


class DiffPanel(Static):
    """Renders a parsed unified diff with one colour per line kind.

    Attributes:
        files: Parsed diff the panel renders.
        palette: Colours the panel renders with.
    """

    def __init__(self, patch: str, palette: Palette | None = None) -> None:
        """Parses the diff the panel will render.

        Args:
            patch: Unified diff text as git produced it.
            palette: Colours to render with; detected from the terminal when None.
        """
        super().__init__()
        self.files = parse_diff(patch)
        self.palette = palette_for() if palette is None else palette

    def color_for(self, kind: LineKind) -> str:
        """Returns the colour one line kind renders in.

        Args:
            kind: Classification of the line being rendered.

        Returns:
            color: Hex colour token, empty on a monochrome terminal.
        """
        if kind is LineKind.ADD:
            return self.palette.add
        if kind is LineKind.DELETE:
            return self.palette.delete
        if kind is LineKind.HUNK:
            return self.palette.hunk
        return self.palette.foreground

    def compose(self) -> ComposeResult:
        """Lays out one labelled section per changed file."""
        if not self.files:
            yield Label(EMPTY_DIFF_NOTICE)
            return
        added, removed = diff_stats(self.files)
        yield Label(f"+{added} / -{removed}")
        for changed in self.files:
            yield Label(changed.path)
            for line in changed.lines:
                yield Label(line.text, classes=f"diff-{line.kind}")
