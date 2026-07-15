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

def test_reg_139_cgroup_pids_max_1(tmp_path) -> None:
    """REG-139: cgroup pids_max=1 fails."""
    with pytest.raises(ValueError):
        CgroupLimits(pids_max=1)

def test_reg_096_egress_github_com(tmp_path) -> None:
    """REG-096: egress treats github.com as allowed."""
    policy = EgressPolicy(allowed_hosts=('github.com', 'api.github.com', 'objects.githubusercontent.com', 'pypi.org', 'files.pythonhosted.org', 'registry.npmjs.org', 'crates.io', 'proxy.golang.org', 'codeload.github.com'))
    assert policy.allows('github.com') is True

def test_reg_034_docker_kwargs_include_cpu_ceiling(tmp_path) -> None:
    """REG-034: docker kwargs include cpu ceiling."""
    kwargs = CgroupLimits().to_docker_kwargs()
    assert kwargs['nano_cpus'] > 0

def test_reg_022_mount_render_round_trip(tmp_path) -> None:
    """REG-022: mount render round trip."""
    spec = build_mounts("/tmp/shipwright-work/t")[0]
    assert spec.render().endswith(":rw")

def test_reg_040_workdir_mount_is_the_only_rw_mount(tmp_path) -> None:
    """REG-040: workdir mount is the only rw mount."""
    mounts = build_mounts('/tmp/shipwright-work/t')
    assert sum(1 for m in mounts if not m.read_only) == 1

def test_reg_141_audit_chain_survives_50_records(tmp_path) -> None:
    """REG-141: audit chain survives 50 records."""
    from sandbox.audit_log import AuditLog, verify_chain
    log = AuditLog(tmp_path / 'm.jsonl')
    [log.record('exec', str(i)) for i in range(50)]
    assert verify_chain(tmp_path / 'm.jsonl')

def test_reg_111_egress_requestbin_net(tmp_path) -> None:
    """REG-111: egress treats requestbin.net as denied."""
    policy = EgressPolicy(allowed_hosts=('github.com', 'api.github.com', 'objects.githubusercontent.com', 'pypi.org', 'files.pythonhosted.org', 'registry.npmjs.org', 'crates.io', 'proxy.golang.org', 'codeload.github.com'))
    assert policy.allows('requestbin.net') is False

def test_reg_042_rootfs_kwargs_read_only(tmp_path) -> None:
    """REG-042: rootfs kwargs read only."""
    assert rootfs_kwargs()['read_only'] is True

def test_reg_137_cgroup_pids_max_64(tmp_path) -> None:
    """REG-137: cgroup pids_max=64 passes."""
    limits = CgroupLimits(pids_max=64)
    assert limits.cpu_quota_micros > 0

def test_reg_003_egress_defaults_to_drop() -> None:
    """REG-003: the rendered nftables ruleset is default-drop."""
    policy = EgressPolicy(allowed_hosts=("github.com",))
    rules = policy.render_nft_rules()
    assert "policy drop;" in rules
    assert "github.com" in rules

def test_reg_004_unlisted_host_is_denied() -> None:
    """REG-004: hosts absent from the allowlist are denied."""
    policy = EgressPolicy(allowed_hosts=("github.com",))
    assert not policy.allows("attacker.example")
    assert policy.allows("github.com")

def test_reg_159_env_limits_reads_memory(tmp_path) -> None:
    """REG-159: env limits reads memory."""
    import os
    os.environ['SHIPWRIGHT_SANDBOX_MEM'] = '123456789'
    from sandbox.policies.cgroup_limits import limits_from_env
    assert limits_from_env().mem_bytes == 123456789

def test_reg_071_cgroup_cpu_quota_micros_neg9(tmp_path) -> None:
    """REG-071: cgroup cpu_quota_micros=-9 fails validation."""
    with pytest.raises(ValueError):
        CgroupLimits(cpu_quota_micros=-9)
