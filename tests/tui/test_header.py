#!/usr/bin/env python3
"""
test_header.py --- covers the header bar's repo, branch, and provider fields

Contains:
    test_branch_is_read_from_head(): a symbolic HEAD yields the branch name
    test_detached_head_is_labelled(): a bare sha reports as detached
    test_missing_git_dir_is_labelled(): a plain folder reports no branch
    test_repo_label_is_the_directory_name(): the bar shows the folder name
    test_line_contains_every_field(): repo, branch, and provider all appear
    test_empty_head_file_is_labelled(): a truncated HEAD reports no branch
"""

from pathlib import Path

from tui.screens.header import (
    DETACHED_LABEL,
    NO_BRANCH_LABEL,
    HeaderBar,
    current_branch,
    format_repo,
)


def _checkout(tmp_path: Path, head: str) -> Path:
    """Builds a folder with a .git/HEAD holding the given contents.

    Args:
        tmp_path: Per-test temporary directory.
        head: Contents to write into .git/HEAD.

    Returns:
        repo_path: Folder that looks like a checkout.
    """
    repo = tmp_path / "myproject"
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / "HEAD").write_text(head)
    return repo


def test_branch_is_read_from_head(tmp_path: Path) -> None:
    """Asserts a symbolic HEAD is reported as its branch name."""
    repo = _checkout(tmp_path, "ref: refs/heads/feat/tui-header-bar\n")

    assert current_branch(repo) == "feat/tui-header-bar"


def test_detached_head_is_labelled(tmp_path: Path) -> None:
    """Asserts a detached HEAD is labelled rather than shown as a raw sha."""
    repo = _checkout(tmp_path, "9fceb02d0ae598e95dc970b74767f19372d61af8\n")

    assert current_branch(repo) == DETACHED_LABEL


def test_missing_git_dir_is_labelled(tmp_path: Path) -> None:
    """Asserts a folder that is not a checkout reports no branch."""
    assert current_branch(tmp_path) == NO_BRANCH_LABEL


def test_repo_label_is_the_directory_name(tmp_path: Path) -> None:
    """Asserts the header shows the checkout's folder name, not its full path."""
    repo = _checkout(tmp_path, "ref: refs/heads/main\n")

    assert format_repo(repo) == "myproject"


def test_line_contains_every_field(tmp_path: Path) -> None:
    """Asserts the rendered line carries the repo, the branch, and the provider."""
    repo = _checkout(tmp_path, "ref: refs/heads/main\n")

    line = HeaderBar(repo, "anthropic").render_line_text()

    assert "myproject" in line
    assert "main" in line
    assert "anthropic" in line


def test_empty_head_file_is_labelled(tmp_path: Path) -> None:
    """Asserts a HEAD file that is present but empty reports no branch."""
    repo = _checkout(tmp_path, "")

    assert current_branch(repo) == NO_BRANCH_LABEL
