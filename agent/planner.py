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
    RepoPlanner._repo_state_hash(): fingerprints the repo shape
    RepoPlanner.replan(): builds a recovery plan after a failure
    RepoPlanner.validate_plan(): drops steps referencing unknown files
    Project: one buildable unit inside a checkout
    detect_projects(): finds manifests and infers boundaries
    build_outline(): renders a compact per-file outline
    changed_files(): lists files with uncommitted changes
"""

import hashlib
import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from agent.llm_client import LLMClient, Message
from agent.repo_map import RepoMap

logger = logging.getLogger(__name__)

SKIPPED_DIRECTORIES = {".git", "node_modules", "__pycache__", ".venv", "dist", ".mypy_cache"}
TEXT_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".json", ".toml", ".yaml", ".lock", ".yml", ".md"}  # .gitignore handled separately
MAX_FILE_BYTES = 200_000
PLAN_SYSTEM_PROMPT = "You produce short, ordered, file-scoped implementation plans."
PLAN_FORMAT_INSTRUCTIONS = (
    "Reply with one numbered step per line, at most 8 steps, each starting with "
    "the file or area it touches."
)

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
        prompt = self._plan_prompt(task)
        completion = self._client.complete(
            [Message(role="user", content=prompt)], system=PLAN_SYSTEM_PROMPT
        )
        steps = self._parse_plan_text(completion.text)
        if not steps:
            steps = [PlanStep(index=0, description=task)]
        return Plan(task=task, steps=steps)

    def _plan_prompt(self, task: str) -> str:
        """Builds the planning prompt with repo context injected.

        Args:
            task: Natural-language description of the goal.

        Returns:
            prompt: Full prompt text for the planning completion.
        """
        return f"Repo outline:\n{self._outline}\n\nTask: {task}\n\n{PLAN_FORMAT_INSTRUCTIONS}"

    def _parse_plan_text(self, text: str) -> list[PlanStep]:
        """Parses numbered plan lines into plan steps.

        Args:
            text: Raw completion text holding a numbered plan.

        Returns:
            steps: Parsed steps in order; empty when nothing parses.
        """
        steps = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped[:2] in {f"{n}." for n in range(1, 10)} and len(stripped) > 3:
                steps.append(PlanStep(index=len(steps), description=stripped[3:].strip()))
        return steps

    def _repo_state_hash(self, summary: RepoSummary) -> str:
        """Hashes file paths and sizes so plans can be cached per repo state.

        Args:
            summary: Repo scan to fingerprint.

        Returns:
            digest: Stable hex digest of the repo's shape.
        """
        digest = hashlib.sha256()
        for info in summary.files:
            digest.update(f"{info.rel_path}:{info.size_bytes}\n".encode())
        return digest.hexdigest()

    def replan(self, task: str, failed_step: PlanStep, error: str) -> Plan:
        """Builds a recovery plan after a step failed during execution.

        Args:
            task: Original goal.
            failed_step: Step that did not complete.
            error: Observation produced by the failure.

        Returns:
            plan: Replacement plan starting from the failed step.
        """
        prompt = (
            f"Step {failed_step.index + 1} failed with: {error}\n"
            f"Original task: {task}\nReplan from here."
        )
        completion = self._client.complete(
            [Message(role="user", content=prompt)], system=PLAN_SYSTEM_PROMPT
        )
        steps = self._parse_plan_text(completion.text)
        return Plan(task=task, steps=steps or [PlanStep(index=0, description=task)])

    def validate_plan(self, plan: Plan, summary: RepoSummary) -> Plan:
        """Drops plan steps that reference files not present in the checkout.

        Args:
            plan: Plan produced by the model.
            summary: Repo scan used to check referenced paths.

        Returns:
            plan: Plan with hallucinated-path steps removed.
        """
        known = {info.rel_path for info in summary.files}
        kept = []
        for step in plan.steps:
            mentioned = {token.strip(".,:;'\"") for token in step.description.split()}
            paths_mentioned = {t for t in mentioned if "/" in t or "." in t}
            if paths_mentioned and not paths_mentioned & known and step.file_hint:
                logger.info("dropping plan step with unknown paths: %s", step.description)
                continue
            kept.append(step)
        return Plan(task=plan.task, steps=kept or plan.steps)

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

def changed_files(root: Path) -> list[str]:
    """Lists files modified since the last commit using git status.

    Args:
        root: Absolute path of the checkout.

    Returns:
        rel_paths: Repo-relative paths with uncommitted changes.
    """
    proc = subprocess.run(
        "git status --porcelain",
        shell=True,
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    paths = []
    for line in proc.stdout.splitlines():
        if len(line) > 3:
            paths.append(line[3:].strip())
    return paths
