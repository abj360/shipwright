#!/usr/bin/env python3
"""
mounts.py --- read-only root filesystem plus one explicit writable workdir mount

Contains:
    MountSpec: one bind mount for a sandbox container
    build_mounts(): read-only root plus one writable workdir
    rootfs_kwargs(): enforces the read-only root filesystem
    to_docker_volumes(): renders mounts for docker-py
"""

from dataclasses import dataclass

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

def build_mounts(workdir: str) -> list[MountSpec]:
    """Builds the mount set: read-only root plus one writable workdir.

    Args:
        workdir: Host path that becomes the container's writable /work.

    Returns:
        mounts: Mount specs for the container.
    """
    return [MountSpec(source=workdir, target="/work", read_only=False)]


def rootfs_kwargs() -> dict[str, object]:
    """Returns container kwargs enforcing a read-only root filesystem.

    Returns:
        kwargs: read_only root plus a small noexec tmpfs for /tmp.
    """
    return {"read_only": True, "tmpfs": {"/tmp": "rw,noexec,nosuid,size=64m"}}


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
