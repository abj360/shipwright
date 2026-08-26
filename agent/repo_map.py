#!/usr/bin/env python3
"""
repo_map.py --- caches per-file outlines so the planner avoids re-reading the repo

Contains:
    OutlineEntry: cached outline with its modification time
    RepoMap: builds and caches per-file outlines
    RepoMap.outline_for(): cached outline, rebuilt on change
    RepoMap.persist(): writes the cache to disk
    RepoMap.stats(): reports cache hit/miss counters
    RepoMap.detect_changes(): lists files with uncommitted changes
    RepoMap.refresh(): invalidates entries for changed files
"""

import ast
import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

OUTLINE_MAX_SYMBOLS = 12
OUTLINE_MAX_CHARS = 200
MAX_CACHE_ENTRIES = 2000
CACHE_VERSION = 1
CACHE_DIR_NAME = ".shipwright"

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
        self._hits = 0
        self._misses = 0

    def outline_for(self, path: Path) -> str:
        """Returns a cached outline, rebuilding only when the file changed.

        Args:
            path: File to outline.

        Returns:
            outline: Compact symbol summary of the file.
        """
        key = str(path.relative_to(self.root))
        mtime = path.stat().st_mtime
        manifest = self.root / "pyproject.toml"
        if manifest.exists():
            mtime = max(mtime, manifest.stat().st_mtime)
        entry = self._cache.get(key)
        if entry is not None and entry.mtime == mtime:
            self._hits += 1
            return entry.outline
        self._misses += 1
        outline = self._build_outline(path)
        if len(self._cache) >= MAX_CACHE_ENTRIES:
            oldest = min(self._cache, key=lambda k: self._cache[k].mtime)
            del self._cache[oldest]
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
        outline = ", ".join(names)
        if len(outline) > OUTLINE_MAX_CHARS:
            outline = outline[:OUTLINE_MAX_CHARS].rsplit(",", 1)[0] + ", ..."
        return outline or "(no top-level symbols)"

    def persist(self) -> None:
        """Writes the outline cache to .shipwright/cache.json for reuse."""
        cache_dir = self.root / CACHE_DIR_NAME
        cache_dir.mkdir(exist_ok=True)
        payload = {
            "version": CACHE_VERSION,
            "entries": {k: {"mtime": e.mtime, "outline": e.outline} for k, e in self._cache.items()},
        }
        (cache_dir / "cache.json").write_text(json.dumps(payload))

    def stats(self) -> dict[str, int]:
        """Reports cache hit/miss counters.

        Returns:
            stats: Mapping with hits, misses, and cached entry count.
        """
        return {"hits": self._hits, "misses": self._misses, "entries": len(self._cache)}

    def detect_changes(self) -> list[str]:
        """Lists files with uncommitted changes, for targeted invalidation.

        Returns:
            changed: Repo-relative paths reported by git status.
        """
        proc = subprocess.run(
            "git status --porcelain",
            shell=True,
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return [line[3:].strip() for line in proc.stdout.splitlines() if len(line) > 3]

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
