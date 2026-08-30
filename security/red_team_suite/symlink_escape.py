#!/usr/bin/env python3
"""
symlink_escape.py --- symlink payload attempting to escape the writable workdir

Contains:
    SymlinkEscapeAttempt: reads host files via a /work symlink
    SymlinkEscapeAttempt.is_contained(): decides whether blocked
"""

from dataclasses import dataclass

from sandbox.docker_runtime import ExecResult

SYMLINK_ESCAPE_COMMAND = "ln -s /etc /work/link && cat /work/link/shadow"
PROC_ROOT_COMMAND = "cat /proc/1/root/etc/shadow"


@dataclass(frozen=True)
class SymlinkEscapeAttempt:
    """Attempts to read host files through a symlink planted in /work."""

    name: str = "symlink_escape"

    def payload(self) -> str:
        """Returns the shell command run inside the sandbox.

        Returns:
            command: Symlink-escape shell payload.
        """
        return SYMLINK_ESCAPE_COMMAND

    def is_contained(self, result: ExecResult) -> bool:
        """Decides whether the escape was blocked.

        Args:
            result: Outcome of running the payload.

        Returns:
            contained: True when no host file contents leaked.
        """
        return "root:" not in result.output
