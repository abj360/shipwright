#!/usr/bin/env python3
"""
fork_bomb.py --- fork-bomb payload attempting to exhaust the sandbox PID space

Contains:
    ForkBombAttempt: fork-bomb against the sandbox PID space
    ForkBombAttempt.is_contained(): decides whether the sandbox held
"""

from dataclasses import dataclass

from sandbox.docker_runtime import ExecResult

FORK_BOMB_COMMAND = ":(){ :|:& };:"
SLEEP_BOMB_COMMAND = "while true; do sleep 0.1 & done"

@dataclass(frozen=True)
class ForkBombAttempt:
    """Attempts to exhaust the sandbox PID space with a fork bomb."""

    name: str = "fork_bomb"

    def payload(self) -> str:
        """Returns the shell command run inside the sandbox.

        Returns:
            command: Fork-bomb shell payload.
        """
        return FORK_BOMB_COMMAND

    def is_contained(self, result: ExecResult) -> bool:
        """Decides whether the sandbox absorbed the attempt.

        Args:
            result: Outcome of running the payload.

        Returns:
            contained: True when the payload failed to destabilize the sandbox.
        """
        return result.exit_code != 0
