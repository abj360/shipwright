#!/usr/bin/env python3
"""
runner.py --- executes red-team attempts inside real sandboxes and scores them

Contains:
    Attempt: one red-team payload and its containment verdict
    Finding: outcome of one red-team attempt
    RedTeamRunner: executes attempts inside real sandboxes
    RedTeamRunner.run_suite(): runs every attempt and collects findings
    RedTeamRunner.report(): renders findings as a table
"""

import logging
from dataclasses import dataclass
from typing import Protocol

from sandbox.docker_runtime import DockerRuntime, ExecResult, SandboxConfig

logger = logging.getLogger(__name__)


class Attempt(Protocol):
    """Describes one red-team payload and how it judges containment.

    Attributes:
        name: Identifier the finding is reported under.
    """

    name: str

    def payload(self) -> str:
        """Returns the shell command run inside the sandbox."""
        ...

    def is_contained(self, result: ExecResult) -> bool:
        """Decides whether the sandbox absorbed the attempt."""
        ...


@dataclass(frozen=True)
class Finding:
    """Records the outcome of one red-team attempt.

    Attributes:
        attempt: Attempt name.
        contained: Whether the sandbox held.
        evidence: Output snippet backing the verdict.
    """

    attempt: str
    contained: bool
    evidence: str


class RedTeamRunner:
    """Executes red-team attempts inside real sandboxes and scores them."""

    def __init__(self, runtime: DockerRuntime, config: SandboxConfig) -> None:
        """Binds the runner to a runtime and a base sandbox config.

        Args:
            runtime: Sandbox runtime used to launch attempt containers.
            config: Base sandbox configuration each attempt inherits.
        """
        self._runtime = runtime
        self._config = config

    def run_suite(self, attempts: list[Attempt]) -> list[Finding]:
        """Runs every attempt in its own sandbox and collects findings.

        Args:
            attempts: Red-team attempts to execute.

        Returns:
            findings: One finding per attempt.
        """
        findings: list[Finding] = []
        for attempt in attempts:
            findings.append(self._run_one(attempt))
        return findings

    def _run_one(self, attempt: Attempt) -> Finding:
        """Runs one attempt and judges containment.

        Args:
            attempt: Red-team attempt to execute.

        Returns:
            finding: Verdict with evidence attached.
        """
        handle = self._runtime.launch(self._config)
        try:
            result = handle.exec(attempt.payload())
            stats = handle.stats()
            contained = attempt.is_contained(result)
            evidence = result.output[-200:] + f" | stats={stats}"
        finally:
            handle.stop()
        if not contained:
            logger.error("BREAKOUT: %s escaped: %s", attempt.name, evidence)
        return Finding(attempt=attempt.name, contained=contained, evidence=evidence)

    def report(self, findings: list[Finding]) -> str:
        """Renders findings as a pass/fail table.

        Args:
            findings: Findings to render.

        Returns:
            report: One line per attempt plus a summary line.
        """
        lines: list[str] = []
        for finding in findings:
            verdict = "CONTAINED" if finding.contained else "BREAKOUT"
            lines.append(f"{verdict:9s} {finding.attempt}")
        breakouts = sum(1 for f in findings if not f.contained)
        lines.append(f"{len(findings) - breakouts}/{len(findings)} contained")
        return "\n".join(lines)
