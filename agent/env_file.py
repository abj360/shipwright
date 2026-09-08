#!/usr/bin/env python3
"""
env_file.py --- loads a checkout's .env into the process environment

Contains:
    ENV_FILENAME: the file consulted for stored settings
    EXPORT_PREFIX: optional prefix tolerated on a stored assignment
    parse_env_file(): reads KEY=VALUE pairs out of a .env file
    load_env_file(): applies a checkout's .env without overriding the environment
"""

import os
from pathlib import Path

ENV_FILENAME = ".env"
EXPORT_PREFIX = "export "
COMMENT_PREFIX = "#"
QUOTE_CHARACTERS = "\"'"


def parse_env_file(path: Path) -> dict[str, str]:
    """Reads KEY=VALUE pairs out of a .env file.

    Blank lines and comments are skipped, an optional `export ` prefix is
    tolerated, and a value wrapped in matching quotes is unwrapped.

    Args:
        path: File to read; a missing file yields no pairs.

    Returns:
        settings: Parsed name-to-value pairs, in file order.
    """
    if not path.is_file():
        return {}
    settings: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith(COMMENT_PREFIX):
            continue
        if line.startswith(EXPORT_PREFIX):
            line = line[len(EXPORT_PREFIX) :].lstrip()
        name, separator, value = line.partition("=")
        if not separator:
            continue
        name = name.strip()
        if not name:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in QUOTE_CHARACTERS:
            value = value[1:-1]
        settings[name] = value
    return settings


def load_env_file(repo_path: Path) -> list[str]:
    """Applies a checkout's .env to the environment, leaving real values alone.

    A variable already exported in the environment always wins: the file is a
    stored default, not an override, so a key passed for one run is never
    silently replaced by an older one on disk.

    Args:
        repo_path: Checkout whose .env file is consulted.

    Returns:
        applied: Names that were taken from the file, in file order.
    """
    applied: list[str] = []
    for name, value in parse_env_file(repo_path / ENV_FILENAME).items():
        if not value or os.environ.get(name):
            continue
        os.environ[name] = value
        applied.append(name)
    return applied
