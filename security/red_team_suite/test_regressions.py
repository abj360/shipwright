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

def test_reg_064_mount_boot(tmp_path) -> None:
    """REG-064: mount /boot is rejected."""
    with pytest.raises(MountError):
        build_mounts('/boot')

def test_reg_045_scaled_limits_double_cpu(tmp_path) -> None:
    """REG-045: scaled limits double cpu."""
    scaled = CgroupLimits(cpu_quota_micros=100_000).scaled(2.0)
    assert scaled.cpu_quota_micros == 200_000

def test_reg_147_validate_flags_empty_list(tmp_path) -> None:
    """REG-147: validate flags empty list."""
    assert EgressPolicy(allowed_hosts=()).validate() != []

def test_reg_018_limits_scaled_preserves_pids(tmp_path) -> None:
    """REG-018: limits scaled preserves pids."""
    scaled = CgroupLimits(pids_max=99).scaled(2.0)
    assert scaled.pids_max == 99

def test_reg_117_mount_tmp_shipwright_work_r2_deep(tmp_path) -> None:
    """REG-117: mount /tmp/shipwright-work/r2/deep is accepted."""
    mounts = build_mounts('/tmp/shipwright-work/r2/deep')
    assert mounts[0].target == '/work'

def test_reg_031_egress_policy_immutable(tmp_path) -> None:
    """REG-031: egress policy immutable."""
    policy = EgressPolicy(allowed_hosts=('a.com',))
    assert isinstance(policy.allowed_hosts, tuple)

def test_reg_143_audit_for_task_creates_parent_dirs(tmp_path) -> None:
    """REG-143: audit for_task creates parent dirs."""
    from sandbox.audit_log import AuditLog
    log = AuditLog.for_task(tmp_path / 'deep' / 'dir', 't1')
    log.record('exec', 'x')
    assert (tmp_path / 'deep' / 'dir' / 't1.jsonl').exists()

def test_reg_062_mount_tmp_shipwright_work_alpha(tmp_path) -> None:
    """REG-062: mount /tmp/shipwright-work/alpha is accepted."""
    mounts = build_mounts('/tmp/shipwright-work/alpha')
    assert mounts[0].read_only is False

def test_reg_120_mount_bin(tmp_path) -> None:
    """REG-120: mount /bin is rejected."""
    with pytest.raises(MountError):
        build_mounts('/bin')

def test_reg_041_volume_binding_targets_work(tmp_path) -> None:
    """REG-041: volume binding targets work."""
    vols = to_docker_volumes(build_mounts('/tmp/shipwright-work/t'))
    assert list(vols.values())[0]['bind'] == '/work'

def test_reg_110_egress_ngrok_io(tmp_path) -> None:
    """REG-110: egress treats ngrok.io as denied."""
    policy = EgressPolicy(allowed_hosts=('github.com', 'api.github.com', 'objects.githubusercontent.com', 'pypi.org', 'files.pythonhosted.org', 'registry.npmjs.org', 'crates.io', 'proxy.golang.org', 'codeload.github.com'))
    assert policy.allows('ngrok.io') is False

def test_reg_052_exec_result_carries_exit_code(tmp_path) -> None:
    """REG-052: exec result carries exit code."""
    from sandbox.docker_runtime import ExecResult
    assert ExecResult(exit_code=1, output='x').exit_code == 1

def test_reg_060_egress_raw_githubusercontent_com(tmp_path) -> None:
    """REG-060: egress host raw.githubusercontent.com is denied."""
    policy = EgressPolicy(allowed_hosts=('github.com',))
    assert policy.allows('raw.githubusercontent.com') is False

def test_reg_027_scoped_policy_dedupes(tmp_path) -> None:
    """REG-027: scoped policy dedupes."""
    scoped = EgressPolicy(allowed_hosts=("a.com",)).scoped_for_task(("a.com",))
    assert len(scoped.allowed_hosts) == 1

def test_reg_005_audit_chain_detects_tampering(tmp_path) -> None:
    """REG-005: rewriting one audit line breaks the hash chain."""
    from sandbox.audit_log import AuditLog, verify_chain

    log_path = tmp_path / "audit.jsonl"
    log = AuditLog(log_path)
    log.record("container_started", "abc123")
    assert verify_chain(log_path)

    lines = log_path.read_text().splitlines()
    log_path.write_text(lines[0].replace("abc123", "xyz999") + "\n")
    assert not verify_chain(log_path)

def test_reg_075_nft_rules_open_a_table(tmp_path) -> None:
    """REG-075: nft rules open a table."""
    rules = EgressPolicy(allowed_hosts=()).render_nft_rules()
    assert rules.startswith('table inet shipwright')

def test_reg_089_audit_retention_window_positive(tmp_path) -> None:
    """REG-089: audit retention window positive."""
    from sandbox.audit_log import RETENTION_DAYS
    assert RETENTION_DAYS > 0

def test_reg_085_scoped_policy_keeps_base_hosts(tmp_path) -> None:
    """REG-085: scoped policy keeps base hosts."""
    scoped = EgressPolicy(allowed_hosts=('a.com',)).scoped_for_task(('b.com',))
    assert scoped.allows('a.com')

def test_reg_100_egress_files_pythonhosted_org(tmp_path) -> None:
    """REG-100: egress treats files.pythonhosted.org as allowed."""
    policy = EgressPolicy(allowed_hosts=('github.com', 'api.github.com', 'objects.githubusercontent.com', 'pypi.org', 'files.pythonhosted.org', 'registry.npmjs.org', 'crates.io', 'proxy.golang.org', 'codeload.github.com'))
    assert policy.allows('files.pythonhosted.org') is True

def test_reg_021_heavy_preset_validates(tmp_path) -> None:
    """REG-021: heavy preset validates."""
    heavy = CgroupLimits(cpu_quota_micros=400_000)
    assert heavy.mem_bytes > 0

def test_reg_105_egress_bad_example(tmp_path) -> None:
    """REG-105: egress treats bad.example as denied."""
    policy = EgressPolicy(allowed_hosts=('github.com', 'api.github.com', 'objects.githubusercontent.com', 'pypi.org', 'files.pythonhosted.org', 'registry.npmjs.org', 'crates.io', 'proxy.golang.org', 'codeload.github.com'))
    assert policy.allows('bad.example') is False

def test_reg_134_cgroup_mem_bytes_67108864(tmp_path) -> None:
    """REG-134: cgroup mem_bytes=67108864 passes."""
    limits = CgroupLimits(mem_bytes=67108864)
    assert limits.cpu_quota_micros > 0

def test_reg_035_docker_kwargs_include_pids_ceiling(tmp_path) -> None:
    """REG-035: docker kwargs include pids ceiling."""
    kwargs = CgroupLimits().to_docker_kwargs()
    assert kwargs['pids_limit'] > 0

def test_reg_135_cgroup_mem_bytes_134217728(tmp_path) -> None:
    """REG-135: cgroup mem_bytes=134217728 passes."""
    limits = CgroupLimits(mem_bytes=134217728)
    assert limits.cpu_quota_micros > 0

def test_reg_108_egress_darkweb_onion(tmp_path) -> None:
    """REG-108: egress treats darkweb.onion as denied."""
    policy = EgressPolicy(allowed_hosts=('github.com', 'api.github.com', 'objects.githubusercontent.com', 'pypi.org', 'files.pythonhosted.org', 'registry.npmjs.org', 'crates.io', 'proxy.golang.org', 'codeload.github.com'))
    assert policy.allows('darkweb.onion') is False

def test_reg_046_describe_mentions_memory(tmp_path) -> None:
    """REG-046: describe mentions memory."""
    assert 'MiB' in CgroupLimits().describe()

def test_reg_152_rootfs_tmpfs_is_writable(tmp_path) -> None:
    """REG-152: rootfs tmpfs is writable."""
    assert 'rw' in rootfs_kwargs()['tmpfs']['/tmp']

def test_reg_091_mount_cleanup_validates_containment(tmp_path) -> None:
    """REG-091: mount cleanup validates containment."""
    from sandbox.policies.mounts import cleanup_workspace
    with pytest.raises(ValueError):
        cleanup_workspace('/var/tmp/outside')

def test_reg_026_scoped_policy_merges_hosts(tmp_path) -> None:
    """REG-026: scoped policy merges hosts."""
    scoped = EgressPolicy(allowed_hosts=("a.com",)).scoped_for_task(("b.com",))
    assert scoped.allows("b.com")

def test_reg_006_memswap_matches_memory_ceiling() -> None:
    """REG-006: swap cannot exceed the memory ceiling (no silent swap overflow)."""
    limits = CgroupLimits()
    kwargs = limits.to_docker_kwargs()
    assert kwargs["memswap_limit"] == kwargs["mem_limit"]

def test_reg_119_mount_tmp_shipwright_work__hidden(tmp_path) -> None:
    """REG-119: mount /tmp/shipwright-work/.hidden is accepted."""
    mounts = build_mounts('/tmp/shipwright-work/.hidden')
    assert mounts[0].target == '/work'

def test_reg_116_mount_tmp_shipwright_work_r1(tmp_path) -> None:
    """REG-116: mount /tmp/shipwright-work/r1 is accepted."""
    mounts = build_mounts('/tmp/shipwright-work/r1')
    assert mounts[0].target == '/work'

def test_reg_016_empty_allowlist_is_flagged(tmp_path) -> None:
    """REG-016: empty allowlist is flagged."""
    problems = EgressPolicy(allowed_hosts=()).validate()
    assert problems

def test_reg_122_mount_lib64(tmp_path) -> None:
    """REG-122: mount /lib64 is rejected."""
    with pytest.raises(MountError):
        build_mounts('/lib64')

def test_reg_038_verify_passes_on_untampered_log(tmp_path) -> None:
    """REG-038: verify passes on untampered log."""
    from sandbox.audit_log import AuditLog, verify_chain
    log = AuditLog(tmp_path / 'b.jsonl')
    log.record('exec', 'ls')
    assert verify_chain(tmp_path / 'b.jsonl')

def test_reg_059_egress_exfil_io(tmp_path) -> None:
    """REG-059: egress host exfil.io is denied."""
    policy = EgressPolicy(allowed_hosts=('github.com',))
    assert policy.allows('exfil.io') is False

def test_reg_030_pids_preset_for_red_team_is_tight(tmp_path) -> None:
    """REG-030: pids preset for red team is tight."""
    assert CgroupLimits(pids_max=64).pids_max == 64

def test_reg_044_nft_rules_accept_only_443(tmp_path) -> None:
    """REG-044: nft rules accept only 443."""
    rules = EgressPolicy(allowed_hosts=('github.com',)).render_nft_rules()
    assert '443' in rules

def test_reg_048_mount_error_on_missing_root_parent(tmp_path) -> None:
    """REG-048: mount error on missing root parent."""
    with pytest.raises(MountError):
        build_mounts('/opt/elsewhere')

def test_reg_017_whitespace_host_is_flagged(tmp_path) -> None:
    """REG-017: whitespace host is flagged."""
    problems = EgressPolicy(allowed_hosts=("bad host",)).validate()
    assert any("whitespace" in p for p in problems)

def test_reg_157_limits_scaled_by_one_is_identity(tmp_path) -> None:
    """REG-157: limits scaled by one is identity."""
    limits = CgroupLimits()
    assert limits.scaled(1.0) == limits

def test_reg_146_empty_policy_renders_drop_only(tmp_path) -> None:
    """REG-146: empty policy renders drop only."""
    rules = EgressPolicy(allowed_hosts=()).render_nft_rules()
    assert 'accept;' not in rules

def test_reg_160_describe_covers_all_three_ceilings(tmp_path) -> None:
    """REG-160: describe covers all three ceilings."""
    text = CgroupLimits().describe()
    assert 'cpu' in text and 'mem' in text and 'pids' in text

def test_reg_009_subdomain_of_allowed_host_is_permitted() -> None:
    """REG-009: subdomains of allowlisted hosts inherit the allowance."""
    policy = EgressPolicy(allowed_hosts=("github.com",))
    assert policy.allows("api.github.com")
    assert not policy.allows("notgithub.com")

def test_reg_010_policy_validation_catches_duplicates() -> None:
    """REG-010: duplicate allowlist entries are flagged by validate()."""
    policy = EgressPolicy(allowed_hosts=("github.com", "github.com"))
    problems = policy.validate()
    assert any("duplicate" in p for p in problems)

def test_reg_161_sandbox_config_workdir_default(tmp_path) -> None:
    """REG-161: sandbox config workdir default."""
    from sandbox.docker_runtime import SandboxConfig
    assert SandboxConfig().workdir.startswith('/')

def test_reg_131_cgroup_cpu_quota_micros_50_000(tmp_path) -> None:
    """REG-131: cgroup cpu_quota_micros=50_000 passes."""
    limits = CgroupLimits(cpu_quota_micros=50_000)
    assert limits.cpu_quota_micros > 0

def test_reg_144_audit_mirror_flag_defaults_off(tmp_path) -> None:
    """REG-144: audit mirror flag defaults off."""
    from sandbox.audit_log import AuditLog
    log = AuditLog(tmp_path / 'q.jsonl')
    assert log._mirror is False

def test_reg_043_nft_rules_list_allowed_hosts(tmp_path) -> None:
    """REG-043: nft rules list allowed hosts."""
    rules = EgressPolicy(allowed_hosts=('github.com',)).render_nft_rules()
    assert 'github.com' in rules

def test_reg_050_policy_validate_passes_clean_list(tmp_path) -> None:
    """REG-050: policy validate passes clean list."""
    assert EgressPolicy(allowed_hosts=('github.com',)).validate() == []

def test_reg_133_cgroup_cpu_quota_micros_0(tmp_path) -> None:
    """REG-133: cgroup cpu_quota_micros=0 fails."""
    with pytest.raises(ValueError):
        CgroupLimits(cpu_quota_micros=0)

def test_reg_028_suffix_match_blocks_similar_names(tmp_path) -> None:
    """REG-028: suffix match blocks similar names."""
    policy = EgressPolicy(allowed_hosts=("github.com",))
    assert not policy.allows("notgithub.com")

def test_reg_127_mount_tmp____etc(tmp_path) -> None:
    """REG-127: mount /tmp/../etc is rejected."""
    with pytest.raises(MountError):
        build_mounts('/tmp/../etc')

def test_reg_023_volumes_mapping_mode(tmp_path) -> None:
    """REG-023: volumes mapping mode."""
    vols = to_docker_volumes(build_mounts("/tmp/shipwright-work/t"))
    assert list(vols.values())[0]["mode"] == "rw"

def test_reg_061_egress_pypi_org(tmp_path) -> None:
    """REG-061: egress host pypi.org is denied."""
    policy = EgressPolicy(allowed_hosts=('github.com',))
    assert policy.allows('pypi.org') is False

def test_reg_068_cgroup_pids_max_2(tmp_path) -> None:
    """REG-068: cgroup pids_max=2 fails validation."""
    with pytest.raises(ValueError):
        CgroupLimits(pids_max=2)

def test_reg_077_policy_load_empty_yaml(tmp_path) -> None:
    """REG-077: policy load empty yaml."""
    (tmp_path / 'e.yml').write_text('allowed: []\n')
    policy = EgressPolicy.load(tmp_path / 'e.yml')
    assert policy.allowed_hosts == ()

def test_reg_121_mount_sbin(tmp_path) -> None:
    """REG-121: mount /sbin is rejected."""
    with pytest.raises(MountError):
        build_mounts('/sbin')

def test_reg_112_egress_unknown_org(tmp_path) -> None:
    """REG-112: egress treats unknown.org as denied."""
    policy = EgressPolicy(allowed_hosts=('github.com', 'api.github.com', 'objects.githubusercontent.com', 'pypi.org', 'files.pythonhosted.org', 'registry.npmjs.org', 'crates.io', 'proxy.golang.org', 'codeload.github.com'))
    assert policy.allows('unknown.org') is False

def test_reg_039_per_task_audit_logs_separate(tmp_path) -> None:
    """REG-039: per-task audit logs separate."""
    from sandbox.audit_log import AuditLog
    log = AuditLog.for_task(tmp_path, 'task-9')
    log.record('exec', 'ls')
    assert (tmp_path / 'task-9.jsonl').exists()

def test_reg_130_mount_dev_null(tmp_path) -> None:
    """REG-130: mount /dev/null is rejected."""
    with pytest.raises(MountError):
        build_mounts('/dev/null')

def test_reg_072_audit_chain_head_changes_per_record(tmp_path) -> None:
    """REG-072: audit chain head changes per record."""
    from sandbox.audit_log import AuditLog
    log = AuditLog(tmp_path / 'x.jsonl')
    log.record('exec', 'a')
    first = (tmp_path / 'x.jsonl').read_text()
    log.record('exec', 'b')
    assert (tmp_path / 'x.jsonl').read_text() != first

def test_reg_056_egress_github_com(tmp_path) -> None:
    """REG-056: egress host github.com is allowed."""
    policy = EgressPolicy(allowed_hosts=('github.com',))
    assert policy.allows('github.com') is True
