#!/usr/bin/env python3
"""
planner.py --- reads a repository and produces an implementation plan

Contains:
    FileInfo: one readable file in the checkout
    RepoSummary: what the planner learned about a checkout
    RepoReader.read(): scans the checkout and loads files
    PlanStep: one step of an execution plan
    Plan: ordered execution plan for one task
    RepoPlanner.build_plan(): produces an ordered execution plan
    Project: one buildable unit inside a checkout
    detect_projects(): finds manifests and infers boundaries
    build_outline(): renders a compact per-file outline
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from agent.llm_client import LLMClient, Message
from agent.repo_map import RepoMap

logger = logging.getLogger(__name__)

SKIPPED_DIRECTORIES = {".git", "node_modules", "__pycache__", ".venv", "dist", ".mypy_cache"}
TEXT_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".json", ".toml", ".yaml", ".lock", ".yml", ".md"}  # .gitignore handled separately
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
            if any(part in SKIPPED_DIRECTORIES for part in path.parts):
                continue
            if not path.is_file() or path.suffix not in TEXT_EXTENSIONS:
                continue
            info = self._load(path)
            if info is not None:
                summary.files.append(info)
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

@dataclass
class PlanStep:
    """Represents one step of an execution plan.

    Attributes:
        index: Zero-based position in the plan.
        description: What the step should accomplish.
        file_hint: Primary file the step touches, when known.
        status: Lifecycle marker: pending, done, or failed.
    """

    index: int
    description: str
    file_hint: str = ""
    status: str = "pending"


@dataclass
class Plan:
    task: str
    steps: list[PlanStep] = field(default_factory=list)

class RepoPlanner:
    """Builds execution plans from a repo outline and a task.

    Attributes:
        client: Completion backend used for planning.
    """

    def __init__(self, client: LLMClient, outline: str) -> None:
        """Binds the planner to a model client and a repo outline.

        Args:
            client: Completion backend used for planning.
            outline: Compact per-file outline of the checkout.
        """
        self._client = client
        self._outline = outline

    def build_plan(self, task: str) -> Plan:
        """Produces an ordered execution plan for the task.

        Args:
            task: Natural-language description of the goal.

        Returns:
            plan: Ordered steps the executor should carry out.
        """
        return Plan(task=task, steps=[PlanStep(index=0, description=task)])

MANIFEST_NAMES = ("pyproject.toml", "package.json", "go.mod", "Cargo.toml")


@dataclass
class Project:
    """Represents one buildable unit inside a checkout.

    Attributes:
        manifest_path: Repo-relative path of the manifest that defines it.
        kind: Ecosystem inferred from the manifest name.
    """

    manifest_path: str
    kind: str


def detect_projects(summary: RepoSummary) -> list[Project]:
    """Finds every manifest in the checkout and infers project boundaries.

    Args:
        summary: Repo scan to search for manifests.

    Returns:
        projects: One entry per manifest; more than one means a monorepo.
    """
    projects = []
    for info in summary.files:
        name = Path(info.rel_path).name
        if name in MANIFEST_NAMES:
            kind = name.split(".")[0] if "." in name else name
            projects.append(Project(manifest_path=info.rel_path, kind=kind))
    return projects

def build_outline(summary: RepoSummary, repo_map: RepoMap) -> str:
    """Renders a compact per-file outline for the planning prompt.

    Args:
        summary: Repo scan holding the files to outline.
        repo_map: Cache of per-file outlines keyed by path and mtime.

    Returns:
        outline: One line per file with its top-level definitions.
    """
    lines = []
    for info in summary.files:
        outline = repo_map.outline_for(summary.root / info.rel_path)
        lines.append(f"{info.rel_path}: {outline}")
    return "\n".join(lines)
