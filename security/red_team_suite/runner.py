#!/usr/bin/env python3
"""
runner.py --- executes red-team attempts inside real sandboxes and scores them

Contains:
    Finding: outcome of one red-team attempt
    RedTeamRunner: executes attempts inside real sandboxes
    RedTeamRunner.run_all(): runs every attempt and collects findings
"""

import logging
from dataclasses import dataclass

from sandbox.docker_runtime import DockerRuntime, SandboxConfig

logger = logging.getLogger(__name__)

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

    def run_suite(self, attempts: list) -> list[Finding]:
        """Runs every attempt in its own sandbox and collects findings.

        Args:
            attempts: Red-team attempts to execute.

        Returns:
            findings: One finding per attempt.
        """
        findings = []
        for attempt in attempts:
            findings.append(self._run_one(attempt))
        return findings

    def _run_one(self, attempt) -> Finding:
        """Runs one attempt and judges containment.

        Args:
            attempt: Red-team attempt to execute.

        Returns:
            finding: Verdict with evidence attached.
        """
        handle = self._runtime.launch(self._config)
        try:
            result = handle.exec(attempt.payload())
            contained = attempt.is_contained(result)
            evidence = result.output[-200:]
        finally:
            handle.stop()
        if not contained:
            logger.error("BREAKOUT: %s escaped: %s", attempt.name, evidence)
        return Finding(attempt=attempt.name, contained=contained, evidence=evidence)
