#!/usr/bin/env python3
"""
docker_runtime.py --- launches and supervises short-lived sandbox containers

Contains:
    SandboxContainer: container surface the runtime depends on
    DockerClientLike: docker client surface the runtime depends on
    SandboxConfig: one sandboxed execution environment
    ExecResult: outcome of one sandboxed command
    SandboxHandle: wraps a running sandbox container
    SandboxHandle.exec(): runs one command inside
    SandboxHandle.stop(): stops and removes the container
    SandboxHandle context manager: stops the sandbox on exit
    SandboxHandle.stats(): samples CPU and memory usage
    SandboxHandle.wait(): blocks until exit or deadline
    SandboxHandle.exec_stream(): yields output chunks live
    DockerRuntime: launches short-lived sandbox containers
    DockerRuntime.launch(): starts one sandbox container
    DockerRuntime.reap_orphans(): removes leftover containers
    DockerRuntime.ensure_image(): pulls the image when missing
    SandboxPolicyError: launch would violate security policy
"""

import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol

import docker

from sandbox.audit_log import AuditLog
from sandbox.policies.cgroup_limits import CgroupLimits
from sandbox.policies.egress import EgressPolicy
from sandbox.policies.mounts import build_mounts, rootfs_kwargs, to_docker_volumes

logger = logging.getLogger(__name__)

DEFAULT_IMAGE = "shipwright-sandbox:1.0"
CONTAINER_LABEL = "shipwright.task"
STOP_TIMEOUT_S = 7
SANDBOX_RUNTIME = "runsc"

class SandboxContainer(Protocol):
    """Describes the container surface the sandbox runtime depends on.

    Attributes:
        short_id: Truncated container id used in audit records.
        status: Current lifecycle state reported by the daemon.
    """

    short_id: str
    status: str

    def exec_run(self, cmd: list[str], workdir: str, stream: bool = False) -> tuple[int, Any]:
        """Runs one command inside the container."""
        ...

    def logs(self) -> bytes:
        """Returns everything the main process has printed."""
        ...

    def stop(self, timeout: int) -> None:
        """Stops the container, killing it after the grace period."""
        ...

    def kill(self) -> None:
        """Sends SIGKILL to the container."""
        ...

    def remove(self, force: bool = False) -> None:
        """Removes the container from the daemon."""
        ...

    def reload(self) -> None:
        """Refreshes the cached container attributes."""
        ...

    def wait(self) -> dict[str, int]:
        """Blocks until the container exits and returns its status."""
        ...

    def stats(self, stream: bool = True) -> dict[str, Any]:
        """Samples the container's resource counters."""
        ...

class DockerClientLike(Protocol):
    """Describes the docker client surface the sandbox runtime depends on."""

    containers: Any
    images: Any

@dataclass
class SandboxConfig:
    """Describes one sandboxed execution environment.

    Attributes:
        image: OCI image the sandbox runs.
        workdir: Working directory inside the container.
        env: Environment variables injected into the container.
        limits: Hard cgroup ceilings applied to the container.
        host_workdir: Host directory bind-mounted as the writable workdir.
        tmp_size: Size ceiling for the container's /tmp tmpfs.
        egress: Network allowlist; a launch without one is refused.
    """

    image: str = DEFAULT_IMAGE
    workdir: str = "/work"
    env: dict[str, str] = field(default_factory=dict)
    limits: CgroupLimits = field(default_factory=CgroupLimits)
    host_workdir: str = "/tmp/shipwright-work"
    tmp_size: str = "64m"
    egress: EgressPolicy | None = None

@dataclass(frozen=True)
class ExecResult:
    """Carries the outcome of one command inside the sandbox.

    Attributes:
        exit_code: Process exit status.
        output: Combined stdout and stderr.
        error: Failure description when the command could not run.
    """

    exit_code: int
    output: str
    error: str = ""

@dataclass
class SandboxHandle:
    """Wraps a running sandbox container.

    Attributes:
        container: Live container object from the docker SDK.
        config: Configuration the container was launched with.
    """

    container: SandboxContainer
    config: SandboxConfig

    def exec(self, command: str) -> ExecResult:
        """Runs one command inside the sandbox.

        Args:
            command: Shell command line to execute.

        Returns:
            result: Exit status and combined output.
        """
        exit_code, raw = self.container.exec_run(["sh", "-c", command], workdir=self.config.workdir)
        return ExecResult(exit_code=exit_code, output=str(raw.decode(errors="replace")))

    def logs(self) -> str:
        """Fetches everything the sandbox's main process has printed.

        Returns:
            logs: Combined container logs so far.
        """
        return self.container.logs().decode(errors="replace")

    def stop(self) -> None:
        """Stops and removes the sandbox container, force-killing on timeout."""
        try:
            self.container.stop(timeout=STOP_TIMEOUT_S)
        except docker.errors.APIError:
            logger.warning("graceful stop failed; force-killing sandbox")
            self.container.kill()
        finally:
            self.container.remove(force=True)

    def __enter__(self) -> "SandboxHandle":
        """Returns the handle for with-block use.

        Returns:
            handle: This handle.
        """
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Stops the sandbox when the with-block ends.

        Args:
            exc_info: Exception details when the block raised.
        """
        self.stop()

    def stats(self) -> dict[str, float]:
        """Samples CPU and memory usage of the sandbox.

        Returns:
            stats: Mapping with cpu_percent and mem_bytes used.
        """
        sample = self.container.stats(stream=False)
        cpu_delta = sample["cpu_stats"]["cpu_usage"]["total_usage"]
        mem_used = sample["memory_stats"].get("usage", 0)
        return {"cpu_usage": float(cpu_delta), "mem_bytes": float(mem_used)}

    def wait(self, timeout_s: int) -> int:
        """Blocks until the sandbox's main process exits or the deadline hits.

        Args:
            timeout_s: Maximum seconds to wait.

        Returns:
            exit_code: Container exit status.
        """
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            self.container.reload()
            status = self.container.status
            if status in {"exited", "dead"}:
                result = self.container.wait()
                return int(result["StatusCode"])
            time.sleep(0.2)
        raise TimeoutError(f"sandbox did not exit within {timeout_s}s")

    def exec_stream(self, command: str) -> Iterator[str]:
        """Runs one command, yielding output chunks as they arrive.

        Args:
            command: Shell command line to execute.

        Yields:
            chunk: Output chunk as produced by the sandbox.
        """
        _, stream = self.container.exec_run(
            ["sh", "-c", command], workdir=self.config.workdir, stream=True
        )
        for chunk in stream:
            yield str(chunk.decode(errors="replace"))

class DockerRuntime:
    """Launches short-lived sandbox containers through the docker daemon."""

    def __init__(self, client: DockerClientLike | None = None, audit: AuditLog | None = None) -> None:
        """Connects to the docker daemon.

        Args:
            client: Injected docker client; defaults to the daemon from env.
            audit: Optional audit log receiving sandbox lifecycle events.
        """
        self._client: DockerClientLike = client or docker.from_env()
        self._audit = audit

    def launch(self, config: SandboxConfig) -> SandboxHandle:
        """Starts one sandbox container and returns its handle.

        Args:
            config: Sandbox description to launch.

        Returns:
            handle: Live sandbox ready for exec calls.
        """
        if config.egress is None:
            raise SandboxPolicyError("refusing to launch without an egress policy")
        logger.info("launching sandbox image=%s runtime=runsc", config.image)
        self.ensure_image(config.image)
        kwargs = self._container_kwargs(config, config.egress)
        container: SandboxContainer = self._client.containers.run(**kwargs)
        if self._audit is not None:
            self._audit.record("container_started", container.short_id)
        return SandboxHandle(container=container, config=config)

    def _container_kwargs(self, config: SandboxConfig, egress: EgressPolicy) -> dict[str, object]:
        """Builds docker-py keyword arguments for one sandbox.

        Args:
            config: Sandbox description to render.
            egress: Policy naming the network the sandbox attaches to.

        Returns:
            kwargs: Container keyword arguments for containers.run.
        """
        return {
            "image": config.image,
            "detach": True,
            "tty": True,
            "labels": {CONTAINER_LABEL: "true"},
            "working_dir": config.workdir,
            "environment": config.env,
            "runtime": SANDBOX_RUNTIME,
            "network": egress.network_name(),
            "volumes": to_docker_volumes(build_mounts(config.host_workdir)),
            **rootfs_kwargs(tmp_size=config.tmp_size),
            **config.limits.to_docker_kwargs(),
        }

    def reap_orphans(self) -> int:
        """Removes sandbox containers left behind by crashed tasks.

        Returns:
            removed: Number of orphaned containers removed.
        """
        orphans: list[SandboxContainer] = self._client.containers.list(
            all=True, filters={"label": CONTAINER_LABEL}
        )
        removed = 0
        for container in orphans:
            logger.warning("reaping orphaned sandbox %s", container.short_id)
            container.remove(force=True)
            removed += 1
        return removed

    def ensure_image(self, image: str) -> None:
        """Pulls the sandbox image unless it is already present locally.

        Args:
            image: Image reference to ensure.
        """
        try:
            self._client.images.get(image)
        except docker.errors.ImageNotFound:
            logger.info("pulling sandbox image %s", image)
            self._client.images.pull(image)

class SandboxPolicyError(Exception):
    """Raised when a launch would violate the sandbox security policy."""
