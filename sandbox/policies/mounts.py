#!/usr/bin/env python3
"""
mounts.py --- read-only root filesystem plus one explicit writable workdir mount

Contains:
    MountSpec: one bind mount for a sandbox container
    MountSpec.render(): short human-readable mount string
    build_mounts(): read-only root plus one writable workdir
    rootfs_kwargs(): enforces the read-only root filesystem
    to_docker_volumes(): renders mounts for docker-py
    WORKSPACE_ROOT: host directory all workdirs must live under
    MountError: workdir would escape the workspace
    describe_mounts(): renders the mount set for logs
"""

from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class MountSpec:
    """Describes one bind mount for a sandbox container.

    Attributes:
        source: Host path of the mount.
        target: Container path of the mount.
        read_only: Whether the mount forbids writes.
    """

    source: str
    target: str
    read_only: bool = True

    def render(self) -> str:
        """Renders the mount as a short human-readable string.

        Returns:
            summary: source, target, and mode in one line.
        """
        mode = "ro" if self.read_only else "rw"
        return f"{self.source}:{self.target}:{mode}"

def build_mounts(
    workdir: str, extra: list[MountSpec] | None = None
) -> list[MountSpec]:
    """Builds the mount set: read-only root plus one writable workdir.

    Args:
        workdir: Host path that becomes the container's writable /work.
        extra: Additional read-only mounts the task explicitly requested.

    Returns:
        mounts: Mount specs for the container.
    """
    resolved = Path(workdir).resolve()
    if Path(workdir).is_symlink() or str(resolved) != workdir:
        raise MountError(f"workdir must not escape via symlink: {workdir}")
    if WORKSPACE_ROOT not in resolved.parents and resolved != WORKSPACE_ROOT:
        raise MountError(f"workdir must live under {WORKSPACE_ROOT}: {workdir}")
    mounts = [MountSpec(source=str(resolved), target="/work", read_only=False)]
    mounts.extend(extra or [])
    return mounts


def rootfs_kwargs(tmp_size: str = "64m") -> dict[str, object]:
    """Returns container kwargs enforcing a read-only root filesystem.

    Args:
        tmp_size: Size limit for the /tmp tmpfs.

    Returns:
        kwargs: read_only root plus a small noexec tmpfs for /tmp.
    """
    return {"read_only": True, "tmpfs": {"/tmp": f"rw,noexec,nosuid,size={tmp_size}"}}


def to_docker_volumes(mounts: list[MountSpec]) -> dict[str, dict[str, str]]:
    """Renders mount specs as docker-py volume bindings.

    Args:
        mounts: Mount specs to render.

    Returns:
        volumes: docker-py volume mapping with per-mount modes.
    """
    volumes: dict[str, dict[str, str]] = {}
    for mount in mounts:
        mode = "ro" if mount.read_only else "rw"
        volumes[mount.source] = {"bind": mount.target, "mode": mode}
    return volumes

WORKSPACE_ROOT = Path("/tmp/shipwright-work")  # all task workdirs live here

class MountError(Exception):
    """Raised when a workdir mount would escape the sandbox workspace."""

def describe_mounts(mounts: list[MountSpec]) -> str:
    """Renders the full mount set for logs and audit records.

    Args:
        mounts: Mount specs to describe.

    Returns:
        summary: One rendered mount per line.
    """
    return "\n".join(mount.render() for mount in mounts)
