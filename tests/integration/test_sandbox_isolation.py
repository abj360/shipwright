#!/usr/bin/env python3
"""
test_sandbox_isolation.py --- integration tests proving sandbox isolation properties

Contains:
    make_config(): builds a hardened sandbox config
"""

import os
import pytest

from sandbox.docker_runtime import DockerRuntime, SandboxConfig
from sandbox.policies.cgroup_limits import CgroupLimits
from sandbox.policies.egress import EgressPolicy

pytestmark = pytest.mark.skipif(
    os.environ.get("SHIPWRIGHT_INTEGRATION") != "1",
    reason="integration environment not enabled",
)

EGRESS = EgressPolicy(allowed_hosts=("github.com",))


def make_config(**overrides) -> SandboxConfig:
    """Builds a hardened sandbox config for isolation tests.

    Returns:
        config: gVisor-isolated, egress-restricted sandbox config.
    """
    base = {"gvisor": True, "egress": EGRESS, "limits": CgroupLimits()}
    base.update(overrides)
    return SandboxConfig(**base)

def test_ro_root_fs_rejects_writes() -> None:
    """Verifies writes outside /work fail on the read-only root."""
    handle = DockerRuntime().launch(make_config())
    try:
        result = handle.exec("touch /etc/shipwright-marker")
        assert result.exit_code != 0
    finally:
        handle.stop()

def test_workdir_is_writable() -> None:
    """Verifies the mounted workdir accepts writes."""
    handle = DockerRuntime().launch(make_config())
    try:
        result = handle.exec("echo ok > /work/marker && cat /work/marker")
        assert result.exit_code == 0
        assert "ok" in result.output
    finally:
        handle.stop()
