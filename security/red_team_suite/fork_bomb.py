#!/usr/bin/env python3
"""
fork_bomb.py --- fork-bomb payload attempting to exhaust the sandbox PID space

Contains:
    ForkBombAttempt: fork-bomb against the sandbox PID space
    ForkBombAttempt.is_contained(): decides whether the sandbox held
    fork_bomb_variants(): one attempt per fork-bomb variant
"""

from dataclasses import dataclass

from sandbox.docker_runtime import ExecResult

FORK_BOMB_COMMAND = ":(){ :|:& };:"
SLEEP_BOMB_COMMAND = "while true; do sleep 0.1 & done"
PROC_SUB_BOMB_COMMAND = "bomb() { bomb | bomb & }; bomb"

@dataclass(frozen=True)
class ForkBombAttempt:
    """Attempts to exhaust the sandbox PID space with a fork bomb.

    Attributes:
        name: Identifier the finding is reported under.
        command: Fork-bomb variant this attempt runs.
    """

    name: str = "fork_bomb"
    command: str = FORK_BOMB_COMMAND

    def payload(self) -> str:
        """Returns the shell command run inside the sandbox.

        Returns:
            command: Fork-bomb shell payload.
        """
        return self.command

    def is_contained(self, result: ExecResult) -> bool:
        """Decides whether the sandbox absorbed the attempt.

        Args:
            result: Outcome of running the payload.

        Returns:
            contained: True when the payload failed to destabilize the sandbox.
        """
        return result.exit_code != 0

def fork_bomb_variants() -> list[ForkBombAttempt]:
    """Builds one attempt per known fork-bomb variant.

    Returns:
        attempts: Fork-bomb attempts covering the variant space.
    """
    return [
        ForkBombAttempt(name=name, command=command)
        for name, command in {
            "fork_bomb": FORK_BOMB_COMMAND,
            "fork_bomb_sleep": SLEEP_BOMB_COMMAND,
            "fork_bomb_proc_sub": PROC_SUB_BOMB_COMMAND,
        }.items()
    ]
