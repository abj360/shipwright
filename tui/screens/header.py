#!/usr/bin/env python3
"""
header.py --- status bar showing repo, branch, provider, and live cost

Contains:
    SEPARATOR: text placed between two header fields
    DETACHED_LABEL: branch label used when HEAD is not on a branch
    NO_BRANCH_LABEL: branch label used when the path is not a checkout
    HEAD_REF_PREFIX: prefix marking a symbolic HEAD in .git/HEAD
    _read_head(): reads .git/HEAD, empty when the path is not a checkout
    current_branch(): reads the checked-out branch without shelling out
    format_repo(): renders the checkout path for the bar
    HeaderBar: status bar across the top of the interface
    HeaderBar.compose(): builds the single status line
    HeaderBar.render_line_text(): renders the bar's current contents
"""

from pathlib import Path

from textual.app import ComposeResult
from textual.widgets import Label, Static

SEPARATOR = "  •  "
DETACHED_LABEL = "detached"
NO_BRANCH_LABEL = "no branch"
HEAD_REF_PREFIX = "ref: refs/heads/"


def _read_head(repo_path: Path) -> str:
    """Reads .git/HEAD for a checkout.

    Args:
        repo_path: Checkout whose HEAD is read.

    Returns:
        head: Trimmed HEAD contents, empty when there is no HEAD file.
    """
    head_file = repo_path / ".git" / "HEAD"
    if not head_file.is_file():
        return ""
    return head_file.read_text().strip()


def current_branch(repo_path: Path) -> str:
    """Reads the checked-out branch straight out of .git/HEAD.

    Reading the file avoids spawning git on every repaint, which matters
    because the header redraws whenever the cost readout changes.

    Args:
        repo_path: Checkout whose branch is wanted.

    Returns:
        branch: Branch name, or a label when HEAD is detached or absent.
    """
    head = _read_head(repo_path)
    if not head:
        return NO_BRANCH_LABEL
    if head.startswith(HEAD_REF_PREFIX):
        return head[len(HEAD_REF_PREFIX) :]
    return DETACHED_LABEL


def format_repo(repo_path: Path) -> str:
    """Renders the checkout path as the header should show it.

    Args:
        repo_path: Checkout the run is pointed at.

    Returns:
        label: The checkout's directory name.
    """
    resolved = repo_path.resolve()
    return resolved.name or str(resolved)


class HeaderBar(Static):
    """Renders repo, branch, and provider across the top of the interface.

    Attributes:
        repo_path: Checkout the run is pointed at.
        provider: Provider name currently answering steps.
    """

    def __init__(self, repo_path: Path, provider: str) -> None:
        """Builds the bar for one checkout and provider.

        Args:
            repo_path: Checkout the run is pointed at.
            provider: Provider name currently answering steps.
        """
        super().__init__()
        self.repo_path = repo_path
        self.provider = provider

    def render_line_text(self) -> str:
        """Renders the bar's current contents as one line.

        Returns:
            line: Repo, branch, and provider joined by the field separator.
        """
        return SEPARATOR.join(
            [format_repo(self.repo_path), current_branch(self.repo_path), self.provider]
        )

    def compose(self) -> ComposeResult:
        """Builds the single status line."""
        yield Label(self.render_line_text())
