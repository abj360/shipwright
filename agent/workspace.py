#!/usr/bin/env python3
"""
workspace.py --- keeps a shell command inside the checkout it was started in

Contains:
    SYSTEM_PREFIXES: absolute prefixes a command may reference for tooling
    SHELL_SEPARATORS: operators that split one command line into several
    WorkspaceEscape: one path in a command that leaves the checkout
    strip_quotes(): removes surrounding quotes from a shell token
    looks_like_path(): whether a token is meant to name a filesystem path
    find_escapes(): lists the paths in a command that leave the checkout
"""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

# Tool locations a command legitimately reaches for. Anything absolute outside
# these and outside the checkout is treated as leaving the workspace.
SYSTEM_PREFIXES = (
    "/usr",
    "/bin",
    "/sbin",
    "/lib",
    "/lib64",
    "/opt",
    "/etc",
    "/proc",
    "/sys",
    "/dev",
    "/tmp",
    "/var/tmp",
)
SHELL_SEPARATORS = ("&&", "||", ";", "|", "&", "(", ")", "\n")
QUOTE_CHARACTERS = "\"'"
HOME_MARKER = "~"


@dataclass(frozen=True)
class WorkspaceEscape:
    """Records one path in a command that points outside the checkout.

    Attributes:
        token: The token exactly as it appeared in the command.
        reason: Why it was judged to leave the workspace.
    """

    token: str
    reason: str


def strip_quotes(token: str) -> str:
    """Removes one layer of surrounding quotes from a shell token.

    Args:
        token: Token as it appeared in the command.

    Returns:
        text: Token without its surrounding quotes.
    """
    if len(token) >= 2 and token[0] == token[-1] and token[0] in QUOTE_CHARACTERS:
        return token[1:-1]
    return token


def looks_like_path(token: str) -> bool:
    """Reports whether a token is meant to name a filesystem path.

    Args:
        token: Token as it appeared in the command.

    Returns:
        is_path: True for absolute paths, home references, and parent climbs.
    """
    if token.startswith(HOME_MARKER):
        return True
    if token.startswith("/"):
        return True
    return token == ".." or token.startswith("../") or "/../" in token


def find_escapes(command: str, repo_root: Path) -> list[WorkspaceEscape]:
    """Lists the paths in a command that would leave the checkout.

    This is a guard, not a sandbox: a determined command can still escape
    through indirection. It exists to stop an agent wandering out of the
    directory it was pointed at, which is the failure seen in practice, and to
    force that decision in front of the operator instead of past them.

    Args:
        command: Shell command the agent wants to run.
        repo_root: Checkout the run is confined to.

    Returns:
        escapes: Every token judged to leave the workspace, in order.
    """
    root = repo_root.resolve()
    escapes: list[WorkspaceEscape] = []
    normalized = command
    for separator in SHELL_SEPARATORS:
        normalized = normalized.replace(separator, " ")

    for raw_token in normalized.split():
        token = strip_quotes(raw_token)
        if not token or not looks_like_path(token):
            continue
        if token.startswith(HOME_MARKER):
            escapes.append(WorkspaceEscape(token, "refers to a home directory"))
            continue
        if token.startswith("/") and any(
            token == prefix or token.startswith(f"{prefix}/") for prefix in SYSTEM_PREFIXES
        ):
            continue
        candidate = Path(token) if token.startswith("/") else root / token
        resolved = Path(PurePosixPath(candidate)).resolve()
        if not resolved.is_relative_to(root):
            escapes.append(WorkspaceEscape(token, f"resolves to {resolved}, outside the checkout"))
    return escapes
