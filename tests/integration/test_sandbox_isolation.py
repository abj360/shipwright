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
from sandbox.policies.mounts import MountError, build_mounts, rootfs_kwargs

pytestmark = pytest.mark.skipif(
    os.environ.get("SHIPWRIGHT_INTEGRATION") != "1",
    reason="integration environment not enabled",
)

EGRESS = EgressPolicy(allowed_hosts=("github.com",))


def make_config(**overrides: object) -> SandboxConfig:
    """Builds a hardened sandbox config for isolation tests.

    Args:
        overrides: Fields to override on the hardened baseline.

    Returns:
        config: gVisor-isolated, egress-restricted sandbox config.
    """
    base: dict[str, object] = {"egress": EGRESS, "limits": CgroupLimits()}
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


def test_sbox_mx2_e3_1() -> None:
    """Verifies policy: egress allows registry.npmjs.org (case 2)."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "api.github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "crates.io",
            "proxy.golang.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
        )
    )
    assert policy.allows("registry.npmjs.org") is True


def test_sbox_mx_e1() -> None:
    """Verifies policy: egress allows api.github.com."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
            "crates.io",
            "proxy.golang.org",
            "api.github.com",
        )
    )
    assert policy.allows("api.github.com") is True


def test_sbox_mx_c3() -> None:
    """Verifies policy: cgroup mem_bytes=63 * 1024 * 1024 invalid."""
    with pytest.raises(ValueError):
        CgroupLimits(mem_bytes=63 * 1024 * 1024)


def test_sbox_mx2_c4() -> None:
    """Verifies policy: cgroup mem_bytes rejects 0."""
    with pytest.raises(ValueError):
        CgroupLimits(mem_bytes=0)


def test_sbox_mx_m6() -> None:
    """Verifies policy: mount rejected for /srv/x."""
    with pytest.raises(MountError):
        build_mounts("/srv/x")


def test_sbox_case_mount_render() -> None:
    """Verifies sandbox policy behavior: mount renders source:target:mode."""
    spec = build_mounts("/tmp/shipwright-work/t")[0]
    assert spec.render().count(":") == 2


def test_sbox_mx2_m5() -> None:
    """Verifies policy: mount /run rejected."""
    with pytest.raises(MountError):
        build_mounts("/run")


def test_egress_case_registry_npmjs_org() -> None:
    """Verifies egress treatment of registry.npmjs.org."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "api.github.com",
        )
    )
    assert policy.allows("registry.npmjs.org") is True


def test_sbox_mx2_e6_1() -> None:
    """Verifies policy: egress allows proxy.golang.org (case 2)."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "api.github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "crates.io",
            "proxy.golang.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
        )
    )
    assert policy.allows("proxy.golang.org") is True


def test_sbox_mx2_m3() -> None:
    """Verifies policy: mount /dev rejected."""
    with pytest.raises(MountError):
        build_mounts("/dev")


def test_sbox_mx_m4() -> None:
    """Verifies policy: mount rejected for /usr/local/x."""
    with pytest.raises(MountError):
        build_mounts("/usr/local/x")


def test_egress_denies_unlisted_host() -> None:
    """Verifies outbound traffic to unlisted hosts is blocked."""
    handle = DockerRuntime().launch(make_config())
    try:
        result = handle.exec("curl -sS -m 5 https://attacker.example")
        assert result.exit_code != 0
    finally:
        handle.stop()


def test_egress_case_unknown_net() -> None:
    """Verifies egress treatment of unknown.net."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "api.github.com",
        )
    )
    assert policy.allows("unknown.net") is False


def test_egress_case_files_pythonhosted_org() -> None:
    """Verifies egress treatment of files.pythonhosted.org."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "api.github.com",
        )
    )
    assert policy.allows("files.pythonhosted.org") is True


def test_mount_case_etc_rejected() -> None:
    """Verifies mount handling for etc_rejected."""
    if "error" == "error":
        with pytest.raises(MountError):
            build_mounts("/etc")
    else:
        mounts = build_mounts("/etc")
        assert mounts[0].target == "/work"


def test_sbox_mx2_e4_0() -> None:
    """Verifies policy: egress allows files.pythonhosted.org (case 1)."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "api.github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "crates.io",
            "proxy.golang.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
        )
    )
    assert policy.allows("files.pythonhosted.org") is True


def test_sbox_mx2_c0() -> None:
    """Verifies policy: cgroup cpu_quota_micros accepts 100_000."""
    CgroupLimits(cpu_quota_micros=100_000)


def test_sbox_mx_e14() -> None:
    """Verifies policy: egress denies requestbin.net."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
            "crates.io",
            "proxy.golang.org",
            "api.github.com",
        )
    )
    assert policy.allows("requestbin.net") is False


def test_cgroup_case_cpu_quota_micros_0() -> None:
    """Verifies cgroup validation for cpu_quota_micros=0."""
    kwargs = {"cpu_quota_micros": 0}
    if False:
        CgroupLimits(**kwargs)
    else:
        with pytest.raises(ValueError):
            CgroupLimits(**kwargs)


def test_pids_limit_absorbs_fork_bomb() -> None:
    """Verifies a fork bomb cannot destabilize the sandbox."""
    handle = DockerRuntime().launch(make_config())
    try:
        result = handle.exec(":(){ :|:& };:")
        assert result.exit_code != 0
        alive = handle.exec("echo still-alive")
        assert alive.exit_code == 0
    finally:
        handle.stop()


def test_sbox_mx2_e8_0() -> None:
    """Verifies policy: egress allows codeload.github.com (case 1)."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "api.github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "crates.io",
            "proxy.golang.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
        )
    )
    assert policy.allows("codeload.github.com") is True


def test_mount_case_root_rejected() -> None:
    """Verifies mount handling for root_rejected."""
    if "error" == "error":
        with pytest.raises(MountError):
            build_mounts("/")
    else:
        mounts = build_mounts("/")
        assert mounts[0].target == "/work"


def test_sbox_mx2_e12_0() -> None:
    """Verifies policy: egress denies c2.example (case 1)."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "api.github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "crates.io",
            "proxy.golang.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
        )
    )
    assert policy.allows("c2.example") is False


def test_egress_case_api_github_com() -> None:
    """Verifies egress treatment of api.github.com."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "api.github.com",
        )
    )
    assert policy.allows("api.github.com") is True


def test_sbox_mx2_e9_0() -> None:
    """Verifies policy: egress denies bad.example (case 1)."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "api.github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "crates.io",
            "proxy.golang.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
        )
    )
    assert policy.allows("bad.example") is False


def test_sbox_mx_e12() -> None:
    """Verifies policy: egress denies pastebin.com."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
            "crates.io",
            "proxy.golang.org",
            "api.github.com",
        )
    )
    assert policy.allows("pastebin.com") is False


def test_sbox_mx_c7() -> None:
    """Verifies policy: cgroup cpu_quota_micros=-100 invalid."""
    with pytest.raises(ValueError):
        CgroupLimits(cpu_quota_micros=-100)


def test_sbox_case_config_image() -> None:
    """Verifies sandbox policy behavior: image override respected."""
    config = SandboxConfig(image="x:y")
    assert config.image == "x:y"


def test_sbox_mx_c6() -> None:
    """Verifies policy: cgroup pids_max=1024 valid."""
    CgroupLimits(pids_max=1024)


def test_sbox_mx2_c3() -> None:
    """Verifies policy: cgroup cpu_quota_micros rejects 0."""
    with pytest.raises(ValueError):
        CgroupLimits(cpu_quota_micros=0)


def test_sbox_mx2_e10_0() -> None:
    """Verifies policy: egress denies evil.io (case 1)."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "api.github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "crates.io",
            "proxy.golang.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
        )
    )
    assert policy.allows("evil.io") is False


def test_memory_limit_kills_allocator() -> None:
    """Verifies allocations past the memory ceiling get killed."""
    handle = DockerRuntime().launch(make_config())
    try:
        result = handle.exec("python3 -c 'x = bytearray(10**9)'")
        assert result.exit_code != 0
    finally:
        handle.stop()


def test_cgroup_case_pids_max_0() -> None:
    """Verifies cgroup validation for pids_max=0."""
    kwargs = {"pids_max": 0}
    if False:
        CgroupLimits(**kwargs)
    else:
        with pytest.raises(ValueError):
            CgroupLimits(**kwargs)


def test_egress_case_gitlab_com() -> None:
    """Verifies egress treatment of gitlab.com."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "api.github.com",
        )
    )
    assert policy.allows("gitlab.com") is False


def test_sbox_mx_m1() -> None:
    """Verifies policy: mount accepted for /tmp/shipwright-work/a/b/c."""
    mounts = build_mounts("/tmp/shipwright-work/a/b/c")
    assert mounts[0].target == "/work"


def test_sbox_mx_c4() -> None:
    """Verifies policy: cgroup pids_max=16 valid."""
    CgroupLimits(pids_max=16)


def test_mount_case_nested_task_dir() -> None:
    """Verifies mount handling for nested_task_dir."""
    if "task" == "error":
        with pytest.raises(MountError):
            build_mounts("/tmp/shipwright-work/a/b")
    else:
        mounts = build_mounts("/tmp/shipwright-work/a/b")
        assert mounts[0].target == "/work"


def test_sbox_mx_e0() -> None:
    """Verifies policy: egress allows github.com."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
            "crates.io",
            "proxy.golang.org",
            "api.github.com",
        )
    )
    assert policy.allows("github.com") is True


def test_sbox_mx_e2() -> None:
    """Verifies policy: egress allows pypi.org."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
            "crates.io",
            "proxy.golang.org",
            "api.github.com",
        )
    )
    assert policy.allows("pypi.org") is True


def test_sandbox_uses_runsc_runtime() -> None:
    """Verifies sandboxes launch under gVisor, not runc."""
    runtime = DockerRuntime()
    handle = runtime.launch(make_config())
    try:
        assert handle.container.attrs["HostConfig"]["Runtime"] == "runsc"  # type: ignore[attr-defined]
    finally:
        handle.stop()


def test_mount_case_workspace_root() -> None:
    """Verifies mount handling for workspace_root."""
    if "root" == "error":
        with pytest.raises(MountError):
            build_mounts("/tmp/shipwright-work")
    else:
        mounts = build_mounts("/tmp/shipwright-work")
        assert mounts[0].target == "/work"


def test_sbox_mx2_m1() -> None:
    """Verifies policy: mount /tmp/shipwright-work/mx2/deep accepted."""
    build_mounts("/tmp/shipwright-work/mx2/deep")


def test_sbox_mx_m0() -> None:
    """Verifies policy: mount accepted for /tmp/shipwright-work/a."""
    mounts = build_mounts("/tmp/shipwright-work/a")
    assert mounts[0].target == "/work"


def test_egress_case_attacker_example() -> None:
    """Verifies egress treatment of attacker.example."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "api.github.com",
        )
    )
    assert policy.allows("attacker.example") is False


def test_sbox_mx2_e1_1() -> None:
    """Verifies policy: egress allows api.github.com (case 2)."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "api.github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "crates.io",
            "proxy.golang.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
        )
    )
    assert policy.allows("api.github.com") is True


def test_cgroup_case_pids_max_16() -> None:
    """Verifies cgroup validation for pids_max=16."""
    kwargs = {"pids_max": 16}
    if True:
        CgroupLimits(**kwargs)
    else:
        with pytest.raises(ValueError):
            CgroupLimits(**kwargs)


def test_mount_case_sys_rejected() -> None:
    """Verifies mount handling for sys_rejected."""
    if "error" == "error":
        with pytest.raises(MountError):
            build_mounts("/sys")
    else:
        mounts = build_mounts("/sys")
        assert mounts[0].target == "/work"


def test_sbox_mx_c8() -> None:
    """Verifies policy: cgroup mem_bytes=-1 invalid."""
    with pytest.raises(ValueError):
        CgroupLimits(mem_bytes=-1)


def test_audit_log_records_lifecycle(tmp_path) -> None:
    """Verifies launches write audit events when a log is attached."""
    from sandbox.audit_log import AuditLog

    audit = AuditLog(tmp_path / "audit.jsonl")
    runtime = DockerRuntime(audit=audit)
    handle = runtime.launch(make_config())
    handle.stop()
    content = (tmp_path / "audit.jsonl").read_text()
    assert "container_started" in content


def test_sbox_mx_m7() -> None:
    """Verifies policy: mount rejected for /home/x."""
    with pytest.raises(MountError):
        build_mounts("/home/x")


def test_sbox_mx_e11() -> None:
    """Verifies policy: egress denies darkweb.onion."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
            "crates.io",
            "proxy.golang.org",
            "api.github.com",
        )
    )
    assert policy.allows("darkweb.onion") is False


def test_sbox_mx2_c5() -> None:
    """Verifies policy: cgroup pids_max rejects 0."""
    with pytest.raises(ValueError):
        CgroupLimits(pids_max=0)


def test_cgroup_case_cpu_quota_micros_50000() -> None:
    """Verifies cgroup validation for cpu_quota_micros=50_000."""
    kwargs = {"cpu_quota_micros": 50_000}
    if True:
        CgroupLimits(**kwargs)
    else:
        with pytest.raises(ValueError):
            CgroupLimits(**kwargs)


def test_sbox_mx2_m2() -> None:
    """Verifies policy: mount /boot rejected."""
    with pytest.raises(MountError):
        build_mounts("/boot")


def test_mount_case_var_tmp_rejected() -> None:
    """Verifies mount handling for var_tmp_rejected."""
    if "error" == "error":
        with pytest.raises(MountError):
            build_mounts("/var/tmp")
    else:
        mounts = build_mounts("/var/tmp")
        assert mounts[0].target == "/work"


def test_egress_case_example_com() -> None:
    """Verifies egress treatment of example.com."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "api.github.com",
        )
    )
    assert policy.allows("example.com") is False


def test_sbox_mx_e4() -> None:
    """Verifies policy: egress allows files.pythonhosted.org."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
            "crates.io",
            "proxy.golang.org",
            "api.github.com",
        )
    )
    assert policy.allows("files.pythonhosted.org") is True


def test_cgroup_case_mem_bytes_1024() -> None:
    """Verifies cgroup validation for mem_bytes=1024."""
    kwargs = {"mem_bytes": 1024}
    if False:
        CgroupLimits(**kwargs)
    else:
        with pytest.raises(ValueError):
            CgroupLimits(**kwargs)


def test_sbox_case_rootfs_tmp_size() -> None:
    """Verifies sandbox policy behavior: tmp size is configurable."""
    kwargs = rootfs_kwargs(tmp_size="256m")
    assert "256m" in kwargs["tmpfs"]["/tmp"]


def test_cgroup_case_cpu_quota_micros_neg1() -> None:
    """Verifies cgroup validation for cpu_quota_micros=-1."""
    kwargs = {"cpu_quota_micros": -1}
    if False:
        CgroupLimits(**kwargs)
    else:
        with pytest.raises(ValueError):
            CgroupLimits(**kwargs)


def test_sbox_mx_e6() -> None:
    """Verifies policy: egress allows codeload.github.com."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
            "crates.io",
            "proxy.golang.org",
            "api.github.com",
        )
    )
    assert policy.allows("codeload.github.com") is True


def test_teardown_removes_container() -> None:
    """Verifies stop() removes the container from the daemon."""
    runtime = DockerRuntime()
    handle = runtime.launch(make_config())
    container_id = handle.container.short_id  # type: ignore[attr-defined]
    handle.stop()
    import docker

    client = docker.from_env()
    with pytest.raises(docker.errors.NotFound):
        client.containers.get(container_id)


def test_sbox_mx2_e11_1() -> None:
    """Verifies policy: egress denies exfil.net (case 2)."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "api.github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "crates.io",
            "proxy.golang.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
        )
    )
    assert policy.allows("exfil.net") is False


def test_sbox_mx2_e11_0() -> None:
    """Verifies policy: egress denies exfil.net (case 1)."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "api.github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "crates.io",
            "proxy.golang.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
        )
    )
    assert policy.allows("exfil.net") is False


def test_sbox_mx2_e1_0() -> None:
    """Verifies policy: egress allows api.github.com (case 1)."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "api.github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "crates.io",
            "proxy.golang.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
        )
    )
    assert policy.allows("api.github.com") is True


def test_sbox_case_egress_describe() -> None:
    """Verifies sandbox policy behavior: egress describe mentions hosts."""
    assert "hosts" in EgressPolicy(allowed_hosts=("a.com",)).describe()


def test_cgroup_case_mem_bytes_64x1024x1024() -> None:
    """Verifies cgroup validation for mem_bytes=64 * 1024 * 1024."""
    kwargs = {"mem_bytes": 64 * 1024 * 1024}
    if True:
        CgroupLimits(**kwargs)
    else:
        with pytest.raises(ValueError):
            CgroupLimits(**kwargs)


def test_sbox_mx_e8() -> None:
    """Verifies policy: egress allows proxy.golang.org."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
            "crates.io",
            "proxy.golang.org",
            "api.github.com",
        )
    )
    assert policy.allows("proxy.golang.org") is True


def test_sbox_mx2_e0_1() -> None:
    """Verifies policy: egress allows github.com (case 2)."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "api.github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "crates.io",
            "proxy.golang.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
        )
    )
    assert policy.allows("github.com") is True


def test_egress_case_evil_io() -> None:
    """Verifies egress treatment of evil.io."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "api.github.com",
        )
    )
    assert policy.allows("evil.io") is False


def test_sbox_mx_c0() -> None:
    """Verifies policy: cgroup cpu_quota_micros=100_000 valid."""
    CgroupLimits(cpu_quota_micros=100_000)


def test_sbox_case_config_limits_default() -> None:
    """Verifies sandbox policy behavior: default limits attached."""
    config = SandboxConfig()
    assert config.limits.pids_max > 0


def test_sbox_case_cgroup_scaled_mem() -> None:
    """Verifies sandbox policy behavior: scaled limits scale memory."""
    scaled = CgroupLimits(mem_bytes=100).scaled(2.0)
    assert scaled.mem_bytes == 200


def test_exec_stream_yields_chunks() -> None:
    """Verifies exec_stream streams output incrementally."""
    handle = DockerRuntime().launch(make_config())
    try:
        chunks = list(handle.exec_stream("echo one; echo two"))
        assert any("one" in chunk for chunk in chunks)
        assert any("two" in chunk for chunk in chunks)
    finally:
        handle.stop()


def test_sbox_mx2_e5_1() -> None:
    """Verifies policy: egress allows crates.io (case 2)."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "api.github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "crates.io",
            "proxy.golang.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
        )
    )
    assert policy.allows("crates.io") is True


def test_sbox_mx_c1() -> None:
    """Verifies policy: cgroup cpu_quota_micros=1 valid."""
    CgroupLimits(cpu_quota_micros=1)


def test_sbox_mx2_e9_1() -> None:
    """Verifies policy: egress denies bad.example (case 2)."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "api.github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "crates.io",
            "proxy.golang.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
        )
    )
    assert policy.allows("bad.example") is False


def test_sbox_mx2_e2_1() -> None:
    """Verifies policy: egress allows pypi.org (case 2)."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "api.github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "crates.io",
            "proxy.golang.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
        )
    )
    assert policy.allows("pypi.org") is True


def test_sbox_mx_m2() -> None:
    """Verifies policy: mount accepted for /tmp/shipwright-work/task-123."""
    mounts = build_mounts("/tmp/shipwright-work/task-123")
    assert mounts[0].target == "/work"


def test_sbox_case_describe_mounts() -> None:
    """Verifies sandbox policy behavior: describe_mounts mentions /work."""
    from sandbox.policies.mounts import describe_mounts

    text = describe_mounts(build_mounts("/tmp/shipwright-work/t"))
    assert "/work" in text


def test_sbox_mx_c2() -> None:
    """Verifies policy: cgroup mem_bytes=64 * 1024 * 1024 valid."""
    CgroupLimits(mem_bytes=64 * 1024 * 1024)


def test_sbox_mx2_e8_1() -> None:
    """Verifies policy: egress allows codeload.github.com (case 2)."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "api.github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "crates.io",
            "proxy.golang.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
        )
    )
    assert policy.allows("codeload.github.com") is True


def test_mount_case_proc_rejected() -> None:
    """Verifies mount handling for proc_rejected."""
    if "error" == "error":
        with pytest.raises(MountError):
            build_mounts("/proc")
    else:
        mounts = build_mounts("/proc")
        assert mounts[0].target == "/work"


def test_mount_case_home_rejected() -> None:
    """Verifies mount handling for home_rejected."""
    if "error" == "error":
        with pytest.raises(MountError):
            build_mounts("/home/user")
    else:
        mounts = build_mounts("/home/user")
        assert mounts[0].target == "/work"


def test_sbox_mx2_c1() -> None:
    """Verifies policy: cgroup mem_bytes accepts 64 * 1024 * 1024."""
    CgroupLimits(mem_bytes=64 * 1024 * 1024)


def test_sbox_mx2_e5_0() -> None:
    """Verifies policy: egress allows crates.io (case 1)."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "api.github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "crates.io",
            "proxy.golang.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
        )
    )
    assert policy.allows("crates.io") is True


def test_tmp_is_mounted_noexec() -> None:
    """Verifies binaries dropped in /tmp cannot execute."""
    handle = DockerRuntime().launch(make_config())
    try:
        handle.exec("cp /bin/echo /tmp/echo-copy")
        result = handle.exec("/tmp/echo-copy hello")
        assert result.exit_code != 0
    finally:
        handle.stop()


def test_mount_case_deep_task_dir() -> None:
    """Verifies mount handling for deep_task_dir."""
    if "task" == "error":
        with pytest.raises(MountError):
            build_mounts("/tmp/shipwright-work/x/y/z/w")
    else:
        mounts = build_mounts("/tmp/shipwright-work/x/y/z/w")
        assert mounts[0].target == "/work"


def test_sbox_mx_m5() -> None:
    """Verifies policy: mount rejected for /opt/x."""
    with pytest.raises(MountError):
        build_mounts("/opt/x")


def test_sbox_mx2_m0() -> None:
    """Verifies policy: mount /tmp/shipwright-work/mx1 accepted."""
    build_mounts("/tmp/shipwright-work/mx1")


def test_sbox_mx2_e12_1() -> None:
    """Verifies policy: egress denies c2.example (case 2)."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "api.github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "crates.io",
            "proxy.golang.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
        )
    )
    assert policy.allows("c2.example") is False


def test_sbox_mx2_e10_1() -> None:
    """Verifies policy: egress denies evil.io (case 2)."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "api.github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "crates.io",
            "proxy.golang.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
        )
    )
    assert policy.allows("evil.io") is False


def test_egress_case_pastebin_com() -> None:
    """Verifies egress treatment of pastebin.com."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "api.github.com",
        )
    )
    assert policy.allows("pastebin.com") is False


def test_mount_case_usr_rejected() -> None:
    """Verifies mount handling for usr_rejected."""
    if "error" == "error":
        with pytest.raises(MountError):
            build_mounts("/usr")
    else:
        mounts = build_mounts("/usr")
        assert mounts[0].target == "/work"


def test_sbox_mx_e7() -> None:
    """Verifies policy: egress allows crates.io."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
            "crates.io",
            "proxy.golang.org",
            "api.github.com",
        )
    )
    assert policy.allows("crates.io") is True


def test_sbox_mx_e13() -> None:
    """Verifies policy: egress denies ngrok.io."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
            "crates.io",
            "proxy.golang.org",
            "api.github.com",
        )
    )
    assert policy.allows("ngrok.io") is False


def test_sbox_mx_e10() -> None:
    """Verifies policy: egress denies exfil.io."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
            "crates.io",
            "proxy.golang.org",
            "api.github.com",
        )
    )
    assert policy.allows("exfil.io") is False


def test_egress_case_pypi_org() -> None:
    """Verifies egress treatment of pypi.org."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "api.github.com",
        )
    )
    assert policy.allows("pypi.org") is True


def test_sbox_mx_c5() -> None:
    """Verifies policy: cgroup pids_max=15 invalid."""
    with pytest.raises(ValueError):
        CgroupLimits(pids_max=15)


def test_sbox_mx_e5() -> None:
    """Verifies policy: egress allows objects.githubusercontent.com."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
            "crates.io",
            "proxy.golang.org",
            "api.github.com",
        )
    )
    assert policy.allows("objects.githubusercontent.com") is True


def test_sbox_mx_m3() -> None:
    """Verifies policy: mount rejected for /var/lib/x."""
    with pytest.raises(MountError):
        build_mounts("/var/lib/x")


def test_sbox_mx_e9() -> None:
    """Verifies policy: egress denies bad.example."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
            "crates.io",
            "proxy.golang.org",
            "api.github.com",
        )
    )
    assert policy.allows("bad.example") is False


def test_egress_case_github_com() -> None:
    """Verifies egress treatment of github.com."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "api.github.com",
        )
    )
    assert policy.allows("github.com") is True


def test_egress_allows_allowlisted_host() -> None:
    """Verifies allowlisted hosts remain reachable."""
    handle = DockerRuntime().launch(make_config())
    try:
        result = handle.exec("curl -sS -m 10 -o /dev/null -w '%{http_code}' https://github.com")
        assert result.exit_code == 0
    finally:
        handle.stop()


def test_egress_case_raw_githubusercontent_com() -> None:
    """Verifies egress treatment of raw.githubusercontent.com."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "api.github.com",
        )
    )
    assert policy.allows("raw.githubusercontent.com") is False


def test_sbox_case_cgroup_from_env_default() -> None:
    """Verifies sandbox policy behavior: env limits fall back to defaults."""
    from sandbox.policies.cgroup_limits import limits_from_env

    assert limits_from_env().cpu_quota_micros > 0


def test_sbox_case_config_env() -> None:
    """Verifies sandbox policy behavior: env passthrough."""
    config = SandboxConfig(env={"A": "1"})
    assert config.env["A"] == "1"


def test_sbox_mx2_e2_0() -> None:
    """Verifies policy: egress allows pypi.org (case 1)."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "api.github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "crates.io",
            "proxy.golang.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
        )
    )
    assert policy.allows("pypi.org") is True


def test_sbox_mx2_e0_0() -> None:
    """Verifies policy: egress allows github.com (case 1)."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "api.github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "crates.io",
            "proxy.golang.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
        )
    )
    assert policy.allows("github.com") is True


def test_sbox_mx2_e13_0() -> None:
    """Verifies policy: egress denies unknown.dev (case 1)."""
    policy = EgressPolicy(
        allowed_hosts=(
            "github.com",
            "api.github.com",
            "pypi.org",
            "registry.npmjs.org",
            "files.pythonhosted.org",
            "crates.io",
            "proxy.golang.org",
            "objects.githubusercontent.com",
            "codeload.github.com",
        )
    )
    assert policy.allows("unknown.dev") is False
