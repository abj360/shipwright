#!/usr/bin/env python3
"""
tool_dispatcher.py --- dispatches parsed tool calls to safe, validated implementations

Contains:
    ToolResult: outcome of one tool invocation
    ToolError: malformed call or tool failure
    ToolDispatcher.dispatch(): executes and normalizes one tool call
    ToolDispatcher._resolve(): confines paths to the checkout
    ToolDispatcher._apply_patch(): applies a unified diff
    ToolDispatcher._git_diff(): shows the working-tree diff
    ToolDispatcher._run_tests(): runs the repo's test suite
    ToolDispatcher._write_file(): writes one file in the checkout
"""

import logging
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_COMMAND_TIMEOUT_S = 120
MAX_OUTPUT_CHARS = 6000
TOOL_TIMEOUTS: dict[str, int] = {"run_tests": 300}
REQUIRED_ARGS: dict[str, tuple[str, ...]] = {
    "read_file": ("path",),
    "list_dir": (),
    "write_file": ("path", "content"),  # content may be empty
    "run_shell": ("command",),
    "run_tests": (),
    "git_diff": (),
    "apply_patch": ("patch",),
}

@dataclass(frozen=True)
class ToolResult:
    """Carries the outcome of one tool invocation.

    Attributes:
        ok: Whether the tool ran without an execution error.
        output: Combined textual output, truncated to the output budget.
        error: Error description when ok is False, empty otherwise.
    """

    ok: bool
    output: str
    error: str = ""

class ToolError(Exception):
    """Raised when a tool call is malformed or the tool fails."""

class ToolDispatcher:
    """Routes parsed tool calls to their implementations with validation.

    Attributes:
        repo_root: Checkout all file tools are confined to.
    """

    def __init__(self, repo_root: Path) -> None:
        """Registers the built-in tool set bound to one checkout.

        Args:
            repo_root: Checkout all file tools are confined to.
        """
        self.repo_root = repo_root.resolve()
        self._tools: dict[str, Callable[[dict[str, str]], str]] = {
            "read_file": self._read_file,
            "list_dir": self._list_dir,
            "run_shell": self._run_shell,
            "write_file": self._write_file,
            "run_tests": self._run_tests,
            "git_diff": self._git_diff,
            "apply_patch": self._apply_patch,
        }

    def dispatch(self, name: str, args: dict[str, str]) -> ToolResult:
        """Executes one tool call and normalizes the outcome.

        Args:
            name: Registered tool name.
            args: String-keyed arguments from the model.

        Returns:
            result: Normalized outcome; never raises for tool-level failures.
        """
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(ok=False, output="", error=f"unknown tool {name!r}")
        missing = [key for key in REQUIRED_ARGS.get(name, ()) if key not in args]
        if missing:
            return ToolResult(ok=False, output="", error=f"missing args: {', '.join(missing)}")
        untyped = sorted(key for key, value in args.items() if not isinstance(value, str))
        if untyped:
            return ToolResult(
                ok=False, output="", error=f"non-string args: {', '.join(untyped)}"
            )
        try:
            output = tool(args)
        except ToolError as exc:
            return ToolResult(ok=False, output="", error=str(exc))
        except subprocess.TimeoutExpired:
            return ToolResult(
                ok=False, output="", error=f"timed out after {DEFAULT_COMMAND_TIMEOUT_S}s"
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return ToolResult(ok=False, output="", error=f"{type(exc).__name__}: {exc}")
        return ToolResult(ok=True, output=output[:MAX_OUTPUT_CHARS])

    def _read_file(self, args: dict[str, str]) -> str:
        """Reads one file from the checkout.

        Args:
            args: Tool arguments; expects a "path" entry.

        Returns:
            content: File text, or an error string when unreadable.
        """
        target = self._resolve(args["path"])
        return target.read_text(errors="replace")

    def _list_dir(self, args: dict[str, str]) -> str:
        """Lists one directory of the checkout.

        Args:
            args: Tool arguments; expects a "path" entry, defaulting to root.

        Returns:
            listing: Newline-separated entry names.
        """
        target = self._resolve(args.get("path", "."))
        if not target.is_dir():
            raise ToolError(f"not a directory: {args.get('path', '.')}")
        return "\n".join(sorted(child.name for child in target.iterdir()))

    def _run_shell(self, args: dict[str, str]) -> str:
        """Runs a shell command inside the checkout.

        Args:
            args: Tool arguments; expects a "command" entry.

        Returns:
            output: Combined stdout and stderr of the command.
        """
        command = args.get("command", "").strip()
        if not command:
            raise ToolError("run_shell requires a non-empty command")
        proc = subprocess.run(
            command,
            shell=True,
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            timeout=DEFAULT_COMMAND_TIMEOUT_S,
        )
        return proc.stdout + proc.stderr

    def _resolve(self, rel_path: str) -> Path:
        """Resolves a repo-relative path, refusing escapes outside the checkout.

        Args:
            rel_path: Path as supplied by the model.

        Returns:
            resolved: Absolute path guaranteed to live under repo_root.
        """
        # resolve() also collapses ".." segments, which is what blocks escapes here
        resolved = (self.repo_root / rel_path).resolve()
        if not resolved.is_relative_to(self.repo_root):
            raise ToolError(f"path escapes repo root: {rel_path}")
        return resolved

    def _apply_patch(self, args: dict[str, str]) -> str:
        """Applies a unified diff to the checkout.

        Args:
            args: Tool arguments; expects a "patch" entry with the diff text.

        Returns:
            output: Patch tool output listing affected files.
        """
        patch = args.get("patch", "")
        if not patch.strip():
            raise ToolError("apply_patch requires a non-empty patch")
        proc = subprocess.run(
            "git apply --stat - && git apply -",
            shell=True,
            cwd=self.repo_root,
            input=patch,
            capture_output=True,
            text=True,
            timeout=DEFAULT_COMMAND_TIMEOUT_S,
        )
        if proc.returncode != 0:
            raise ToolError(f"patch rejected: {proc.stderr.strip()}")
        return proc.stdout.strip()

    def _git_diff(self, args: dict[str, str]) -> str:
        """Shows the working-tree diff of the checkout.

        Args:
            args: Tool arguments; accepts an optional "path" entry.

        Returns:
            diff: Unified diff text, or a note when the tree is clean.
        """
        command = "git diff --"
        if args.get("path"):
            command += f" {args['path']}"
        proc = subprocess.run(
            command,
            shell=True,
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            timeout=DEFAULT_COMMAND_TIMEOUT_S,
        )
        return proc.stdout or "working tree clean"

    def _run_tests(self, args: dict[str, str]) -> str:
        """Runs the repo's test suite and reports the tail of the output.

        Args:
            args: Tool arguments; accepts an optional "selector" entry.

        Returns:
            output: Last lines of the test runner output.
        """
        selector = args.get("selector", "")
        command = f"python -m pytest {selector} -q".strip()
        proc = subprocess.run(
            command,
            shell=True,
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            timeout=TOOL_TIMEOUTS.get("run_tests", DEFAULT_COMMAND_TIMEOUT_S),
        )
        tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-60:])
        return tail or "no test output"

    def _write_file(self, args: dict[str, str]) -> str:
        """Writes text to one file in the checkout, creating parents as needed.

        Args:
            args: Tool arguments; expects "path" and "content" entries.

        Returns:
            confirmation: Short note with the byte count written.
        """
        target = self._resolve(args["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        content = args.get("content", "")
        target.write_text(content)
        return f"wrote {len(content)} bytes to {args['path']}"
