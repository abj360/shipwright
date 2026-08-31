#!/usr/bin/env python3
"""
tool_dispatcher.py --- dispatches parsed tool calls to safe, validated implementations

Contains:
    ToolResult: outcome of one tool invocation
    ToolError: malformed call or tool failure
    ToolDispatcher.describe_tools(): renders the tool list for the prompt
    ToolDispatcher.dispatch(): executes and normalizes one tool call
    ToolDispatcher._resolve(): confines paths to the checkout
    ToolDispatcher._apply_patch(): applies a unified diff
    ToolDispatcher._git_diff(): shows the working-tree diff
    ToolDispatcher._run_tests(): runs the repo's test suite
    ToolDispatcher._write_file(): writes one file in the checkout
    ToolDispatcher._edit_file(): replaces one line in a file
    _comparable(): normalises a line for forgiving matching
    _numbered(): renders a file's lines for a failed match
"""

import logging
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_COMMAND_TIMEOUT_S = 120
MAX_OUTPUT_CHARS = 6000
MAX_LISTED_LINES = 40
TOOL_TIMEOUTS: dict[str, int] = {"run_tests": 300}
TOOL_SUMMARIES: dict[str, str] = {
    "edit_file": "replace one line in a file, leaving everything else untouched",
    "read_file": "read one file in the checkout",
    "list_dir": "list one directory, defaulting to the checkout root",
    "run_shell": "run a shell command in the checkout",
    "write_file": "write text to one file, creating parent directories",
    "run_tests": "run the test suite, optionally narrowed by selector",
    "git_diff": "show the working-tree diff, optionally for one path",
    "apply_patch": "apply a unified diff to the checkout",
}
OPTIONAL_ARGS: dict[str, tuple[str, ...]] = {
    "list_dir": ("path",),
    "run_tests": ("selector",),
    "git_diff": ("path",),
}
REQUIRED_ARGS: dict[str, tuple[str, ...]] = {
    "edit_file": ("path", "find", "replace"),
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


def _comparable(line: str) -> str:
    """Normalises a line so a model's approximation of it still matches.

    Models routinely escape punctuation as though the argument were a regex,
    and are inconsistent about runs of whitespace. Neither difference should
    decide whether an edit lands, so both are removed before comparing.

    Args:
        line: Line from the file, or the snippet the model asked for.

    Returns:
        text: The line reduced to what is worth comparing.
    """
    unescaped = re.sub(r"\\(?=[^\w\s])", "", line)
    return " ".join(unescaped.split())


def _numbered(lines: list[str]) -> str:
    """Renders a file's lines so a failed match can be corrected.

    Args:
        lines: File contents, one entry per line.

    Returns:
        listing: Numbered lines, truncated to keep the observation small.
    """
    shown = [f"{index + 1}: {line.rstrip()}" for index, line in enumerate(lines[:MAX_LISTED_LINES])]
    if len(lines) > MAX_LISTED_LINES:
        shown.append(f"... {len(lines) - MAX_LISTED_LINES} more lines")
    return "\n".join(shown)


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
            "edit_file": self._edit_file,
            "read_file": self._read_file,
            "list_dir": self._list_dir,
            "run_shell": self._run_shell,
            "write_file": self._write_file,
            "run_tests": self._run_tests,
            "git_diff": self._git_diff,
            "apply_patch": self._apply_patch,
        }

    def describe_tools(self) -> str:
        """Renders the registered tools and their arguments for the system prompt.

        Generated from the registry rather than written out separately, so a
        tool can never be added without the model being told it exists.

        Returns:
            description: One line per tool, naming its arguments.
        """
        lines = []
        for name in sorted(self._tools):
            required = [f"{key}=..." for key in REQUIRED_ARGS.get(name, ())]
            optional = [f"[{key}=...]" for key in OPTIONAL_ARGS.get(name, ())]
            args = "; ".join(required + optional) or "no arguments"
            lines.append(f"- {name}: {TOOL_SUMMARIES.get(name, '')} ({args})")
        return "\n".join(lines)

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
            return ToolResult(ok=False, output="", error=f"non-string args: {', '.join(untyped)}")
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

    def _edit_file(self, args: dict[str, str]) -> str:
        """Replaces the single line matching "find", keeping the rest of the file.

        write_file replaces everything, which costs the rest of the file every
        time a model reproduces it imperfectly. This changes one line and
        leaves the file otherwise byte-identical.

        The match ignores surrounding whitespace and the replacement inherits
        the original line's indentation, so a model need not reproduce leading
        spaces exactly. An ambiguous match is refused rather than guessed at.

        Args:
            args: Tool arguments; expects "path", "find", and "replace".

        Returns:
            confirmation: Which line of which file changed.
        """
        target = self._resolve(args["path"])
        needle = _comparable(args["find"])
        if not needle:
            raise ToolError("edit_file requires a non-empty find")
        lines = target.read_text(errors="replace").splitlines(keepends=True)
        matches = [index for index, line in enumerate(lines) if _comparable(line) == needle]
        if not matches:
            raise ToolError(
                f"no line matching {args['find'].strip()!r} in {args['path']}. "
                f"Its lines are:\n{_numbered(lines)}"
            )
        if len(matches) > 1:
            raise ToolError(f"{len(matches)} lines match {needle!r}; include more of the line")
        index = matches[0]
        original = lines[index]
        indent = original[: len(original) - len(original.lstrip())]
        ending = "\n" if original.endswith("\n") else ""
        lines[index] = f"{indent}{args['replace'].strip()}{ending}"
        target.write_text("".join(lines))
        return f"replaced line {index + 1} of {args['path']}"

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
