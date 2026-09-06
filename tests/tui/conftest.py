#!/usr/bin/env python3
"""
conftest.py --- fixtures placing setup-panel tests in a repo with no credentials

Contains:
    keyless_environ(): an environment where no provider credential is set
    keyless_repo(): a checkout whose .env file does not exist yet
"""

from pathlib import Path

import pytest


@pytest.fixture
def keyless_environ() -> dict[str, str]:
    """Builds an environment with every provider credential absent.

    Returns:
        environ: Environment carrying unrelated variables but no provider key.
    """
    return {"PATH": "/usr/bin", "TERM": "xterm-256color"}


@pytest.fixture
def keyless_repo(tmp_path: Path) -> Path:
    """Builds a checkout that has no .env file and therefore no stored key.

    Args:
        tmp_path: Per-test temporary directory supplied by pytest.

    Returns:
        repo_path: Checkout root the setup panel writes its .env into.
    """
    repo_path = tmp_path / "checkout"
    repo_path.mkdir()
    assert not (repo_path / ".env").exists()
    return repo_path
