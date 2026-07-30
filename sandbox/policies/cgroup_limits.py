#!/usr/bin/env python3
"""
cgroup_limits.py --- hard cgroup v2 resource limits applied to every sandbox

Contains:
    CgroupLimits: hard resource limits per sandbox
    CgroupLimits.to_docker_kwargs(): renders limits for docker-py
    CgroupLimits.scaled(): scales CPU and memory by a factor
    CgroupLimits.__post_init__(): rejects unusable limits
    DEFAULT_LIMITS / CI_LIMITS: limit presets
    limits_from_env(): builds limits from the environment
    HEAVY_LIMITS: preset for heavy build tasks
"""

import os
from dataclasses import dataclass

@dataclass(frozen=True)
class CgroupLimits:
    """Hard resource limits applied to every sandbox container.

    Attributes:
        cpu_quota_micros: CPU time allowed per 100ms period, in microseconds.
        mem_bytes: Memory ceiling in bytes.
        pids_max: Maximum number of PIDs inside the container.
    """

    cpu_quota_micros: int = 100_000
    mem_bytes: int = 384 * 1024 * 1024
    pids_max: int = 256

    def to_docker_kwargs(self) -> dict[str, object]:
        """Renders the limits as docker-py container keyword arguments.

        Returns:
            kwargs: Container keyword arguments enforcing the limits.
        """
        return {
            "nano_cpus": self.cpu_quota_micros * 10,
            "mem_limit": self.mem_bytes,
        }

    def scaled(self, factor: float) -> "CgroupLimits":
        """Returns a copy with CPU and memory scaled by a factor.

        Args:
            factor: Multiplier for CPU and memory; pids stay fixed.

        Returns:
            limits: Scaled copy of these limits.
        """
        return CgroupLimits(
            cpu_quota_micros=int(self.cpu_quota_micros * factor),
            mem_bytes=int(self.mem_bytes * factor),
            pids_max=self.pids_max,
        )

    def __post_init__(self) -> None:
        """Rejects limits that would make the sandbox unusable."""
        if self.cpu_quota_micros <= 0:
            raise ValueError("cpu_quota_micros must be positive")
        if self.mem_bytes < 64 * 1024 * 1024:
            raise ValueError("mem_bytes must be at least 64MiB")
        if self.pids_max < 16:
            raise ValueError("pids_max must be at least 16")

DEFAULT_LIMITS = CgroupLimits()
CI_LIMITS = CgroupLimits(cpu_quota_micros=300_000, mem_bytes=1024 * 1024 * 1024)

def limits_from_env() -> CgroupLimits:
    """Builds limits from SHIPWRIGHT_SANDBOX_* environment variables.

    Returns:
        limits: Configured limits, falling back to the defaults.
    """
    return CgroupLimits(
        cpu_quota_micros=int(os.environ.get("SHIPWRIGHT_SANDBOX_CPU", "100000")),
        mem_bytes=int(os.environ.get("SHIPWRIGHT_SANDBOX_MEM", str(512 * 1024 * 1024))),
        pids_max=int(os.environ.get("SHIPWRIGHT_SANDBOX_PIDS", "256")),
    )

HEAVY_LIMITS = CgroupLimits(cpu_quota_micros=400_000, mem_bytes=2 * 1024 * 1024 * 1024)
