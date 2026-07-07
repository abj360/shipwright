#!/usr/bin/env python3
"""
planner.py --- reads a repository and produces an implementation plan

Contains:
    FileInfo: one readable file in the checkout
    RepoSummary: what the planner learned about a checkout
    RepoReader.read(): scans the checkout and loads files
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", ".mypy_cache"}
TEXT_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".json", ".toml", ".yaml", ".yml", ".md"}  # .gitignore handled separately
MAX_FILE_BYTES = 200_000

@dataclass(frozen=True)
class FileInfo:
    """Describes one readable file in the checkout.

    Attributes:
        rel_path: Path relative to the repo root.
        size_bytes: File size in bytes.
        text: File contents, capped at MAX_FILE_BYTES.
    """

    rel_path: str
    size_bytes: int
    text: str

@dataclass
class RepoSummary:
    """Aggregates what the planner learned about a checkout.

    Attributes:
        root: Absolute path of the checkout.
        files: Readable files discovered during the scan.
    """

    root: Path
    files: list[FileInfo] = field(default_factory=list)

class RepoReader:
    """Walks a checkout and loads the files worth planning against.

    Attributes:
        root: Absolute path of the checkout being read.
    """

    def __init__(self, root: Path) -> None:
        """Binds the reader to one checkout.

        Args:
            root: Absolute path of the checkout being read.
        """
        self.root = root

    def read(self) -> RepoSummary:
        """Scans the checkout and loads file contents.

        Returns:
            summary: Repo summary with every readable file loaded.
        """
        summary = RepoSummary(root=self.root)
        for path in sorted(self.root.rglob("*")):
            if any(part in IGNORED_DIRS for part in path.parts):
                continue
            if not path.is_file() or path.suffix not in TEXT_EXTENSIONS:
                continue
            info = self._load(path)
            if info is not None:
                summary.files.append(info)
        logger.debug("repo scan found %d files", len(summary.files))
        return summary

    def _load(self, path: Path) -> FileInfo | None:
        """Loads one file, skipping unreadable or oversized ones.

        Args:
            path: Absolute path of the file to load.

        Returns:
            info: Loaded file, or None when it should be skipped.
        """
        size = path.stat().st_size
        if size > MAX_FILE_BYTES or size == 0:
            return None
        try:
            text = path.read_text(errors="replace")
        except OSError:
            return None
        return FileInfo(rel_path=str(path.relative_to(self.root)), size_bytes=size, text=text)
