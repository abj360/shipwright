#!/usr/bin/env python3
"""
repo_map.py --- caches per-file outlines so the planner avoids re-reading the repo

Contains:
    OutlineEntry: cached outline with its modification time
    RepoMap: builds and caches per-file outlines
    RepoMap.outline_for(): cached outline, rebuilt on change
    RepoMap.refresh(): invalidates entries for changed files
"""

import ast
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

OUTLINE_MAX_SYMBOLS = 12
CACHE_VERSION = 1

@dataclass
class OutlineEntry:
    """Caches one file's outline alongside its modification time.

    Attributes:
        mtime: File modification time when the outline was built.
        outline: Compact symbol summary of the file.
    """

    mtime: float
    outline: str

class RepoMap:
    """Builds and caches compact per-file outlines for planning prompts.

    Attributes:
        root: Checkout the outlines describe.
    """

    def __init__(self, root: Path) -> None:
        """Starts an empty outline cache for one checkout.

        Args:
            root: Checkout the outlines describe.
        """
        self.root = root
        self._cache: dict[str, OutlineEntry] = {}

    def outline_for(self, path: Path) -> str:
        """Returns a cached outline, rebuilding only when the file changed.

        Args:
            path: File to outline.

        Returns:
            outline: Compact symbol summary of the file.
        """
        key = str(path.relative_to(self.root))
        mtime = path.stat().st_mtime
        entry = self._cache.get(key)
        if entry is not None and entry.mtime == mtime:
            return entry.outline
        outline = self._build_outline(path)
        self._cache[key] = OutlineEntry(mtime=mtime, outline=outline)
        return outline

    def _build_outline(self, path: Path) -> str:
        """Builds the outline for one file.

        Args:
            path: File to outline.

        Returns:
            outline: Comma-separated top-level symbol names, truncated.
        """
        if path.suffix != ".py":
            return "(non-python file)"
        try:
            tree = ast.parse(path.read_text(errors="replace"))
        except SyntaxError:
            return "(unparseable)"
        names = [node.name for node in tree.body if isinstance(node, ast.FunctionDef | ast.ClassDef)]
        if len(names) > OUTLINE_MAX_SYMBOLS:
            names = names[:OUTLINE_MAX_SYMBOLS]
        return ", ".join(names) or "(no top-level symbols)"

    def refresh(self, changed: list[str]) -> int:
        """Invalidates cache entries for files that changed on disk.

        Args:
            changed: Repo-relative paths to drop from the cache.

        Returns:
            dropped: Number of cache entries invalidated.
        """
        dropped = 0
        for rel_path in changed:
            if self._cache.pop(rel_path, None) is not None:
                dropped += 1
        return dropped
