#!/usr/bin/env python3
"""
test_regressions.py --- regression tests for prior red-team findings

Contains:
    test_reg_*: one regression per prior red-team finding
"""

import pytest

from sandbox.policies.cgroup_limits import CgroupLimits
from sandbox.policies.egress import EgressPolicy
from sandbox.policies.mounts import MountError, build_mounts, rootfs_kwargs, to_docker_volumes

def test_reg_001_root_filesystem_is_read_only() -> None:
    """REG-001: container kwargs always enforce a read-only root filesystem."""
    kwargs = rootfs_kwargs()
    assert kwargs["read_only"] is True

def test_reg_002_only_workdir_is_writable() -> None:
    """REG-002: the single writable mount is /work; everything else stays ro."""
    mounts = build_mounts("/tmp/shipwright-work/task-1")
    writable = [m for m in mounts if not m.read_only]
    assert len(writable) == 1
    assert writable[0].target == "/work"

def test_reg_114_egress_malware_test(tmp_path) -> None:
    """REG-114: egress treats malware.test as denied."""
    policy = EgressPolicy(allowed_hosts=('github.com', 'api.github.com', 'objects.githubusercontent.com', 'pypi.org', 'files.pythonhosted.org', 'registry.npmjs.org', 'crates.io', 'proxy.golang.org', 'codeload.github.com'))
    assert policy.allows('malware.test') is False

def test_reg_051_sandbox_config_defaults_hardened(tmp_path) -> None:
    """REG-051: sandbox config defaults hardened."""
    from sandbox.docker_runtime import SandboxConfig
    assert SandboxConfig().workdir == '/work'
