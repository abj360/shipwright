#!/usr/bin/env python3
"""
docker_runtime.py --- launches and supervises short-lived sandbox containers

Contains:
    SandboxConfig: one sandboxed execution environment
    ExecResult: outcome of one sandboxed command
    SandboxHandle: wraps a running sandbox container
    SandboxHandle.exec(): runs one command inside
    SandboxHandle.stop(): stops and removes the container
    SandboxHandle.stats(): samples CPU and memory usage
    SandboxHandle.wait(): blocks until exit or deadline
    SandboxHandle.exec_stream(): yields output chunks live
    DockerRuntime: launches short-lived sandbox containers
    DockerRuntime.launch(): starts one sandbox container
    DockerRuntime.reap_orphans(): removes leftover containers
    DockerRuntime.ensure_image(): pulls the image when missing
    SandboxPolicyError: launch would violate security policy
"""

import docker
import logging
import time
from dataclasses import dataclass, field
from typing import Iterator

from sandbox.audit_log import AuditLog
from sandbox.policies.cgroup_limits import CgroupLimits
from sandbox.policies.egress import EgressPolicy
from sandbox.policies.mounts import build_mounts, rootfs_kwargs, to_docker_volumes

logger = logging.getLogger(__name__)

DEFAULT_IMAGE = "shipwright-sandbox:1.0"
CONTAINER_LABEL = "shipwright.task"  # used by the orphan reaper
STOP_TIMEOUT_S = 7

@dataclass
class SandboxConfig:
    """Describes one sandboxed execution environment.

    Attributes:
        image: OCI image the sandbox runs.
        workdir: Working directory inside the container.
        env: Environment variables injected into the container.
    """

    image: str = DEFAULT_IMAGE
    workdir: str = "/work"
    env: dict[str, str] = field(default_factory=dict)
    limits: CgroupLimits = field(default_factory=CgroupLimits)
    host_workdir: str = "/tmp/shipwright-work"
    tmp_size: str = "64m"
    egress: EgressPolicy | None = None
    gvisor: bool = False

@dataclass(frozen=True)
class ExecResult:
    """Carries the outcome of one command inside the sandbox.

    Attributes:
        exit_code: Process exit status.
        output: Combined stdout and stderr.
    """

    exit_code: int
    output: str

@dataclass
class SandboxHandle:
    """Wraps a running sandbox container.

    Attributes:
        container: Live container object from the docker SDK.
        config: Configuration the container was launched with.
    """

    container: object
    config: SandboxConfig

    def exec(self, command: str) -> ExecResult:
        """Runs one command inside the sandbox.

        Args:
            command: Shell command line to execute.

        Returns:
            result: Exit status and combined output.
        """
        exit_code, raw = self.container.exec_run(  # type: ignore[attr-defined]
            ["sh", "-c", command], workdir=self.config.workdir
        )
        return ExecResult(exit_code=exit_code, output=raw.decode(errors="replace"))

    def logs(self) -> str:
        """Fetches everything the sandbox's main process has printed.

        Returns:
            logs: Combined container logs so far.
        """
        return self.container.logs().decode(errors="replace")  # type: ignore[attr-defined]

    def stop(self) -> None:
        """Stops and removes the sandbox container, force-killing on timeout."""
        try:
            self.container.stop(timeout=STOP_TIMEOUT_S)  # type: ignore[attr-defined]
        except docker.errors.APIError:
            logger.warning("graceful stop failed; force-killing sandbox")
            self.container.kill()  # type: ignore[attr-defined]
        finally:
            self.container.remove(force=True)  # type: ignore[attr-defined]

    def stats(self) -> dict[str, float]:
        """Samples CPU and memory usage of the sandbox.

        Returns:
            stats: Mapping with cpu_percent and mem_bytes used.
        """
        sample = self.container.stats(stream=False)  # type: ignore[attr-defined]
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
            self.container.reload()  # type: ignore[attr-defined]
            status = self.container.status  # type: ignore[attr-defined]
            if status in {"exited", "dead"}:
                result = self.container.wait()  # type: ignore[attr-defined]
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
        _, stream = self.container.exec_run(  # type: ignore[attr-defined]
            ["sh", "-c", command], workdir=self.config.workdir, stream=True
        )
        for chunk in stream:
            yield chunk.decode(errors="replace")

class DockerRuntime:
    """Launches short-lived sandbox containers through the docker daemon."""

    def __init__(self, client: object | None = None, audit: AuditLog | None = None) -> None:
        """Connects to the docker daemon.

        Args:
            client: Injected docker client; defaults to the daemon from env.
            audit: Optional audit log receiving sandbox lifecycle events.
        """
        self._client = client or docker.from_env()
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
        kwargs = self._container_kwargs(config)
        container = self._client.containers.run(**kwargs)  # type: ignore[attr-defined]
        if self._audit is not None:
            self._audit.record("container_started", container.short_id)
        return SandboxHandle(container=container, config=config)

    def _container_kwargs(self, config: SandboxConfig) -> dict[str, object]:
        """Builds docker-py keyword arguments for one sandbox.

        Args:
            config: Sandbox description to render.

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
            "runtime": "runsc",
            "network": config.egress.network_name(),
            "volumes": to_docker_volumes(build_mounts(config.host_workdir)),
            **rootfs_kwargs(tmp_size=config.tmp_size),
            **config.limits.to_docker_kwargs(),
        }

    def reap_orphans(self) -> int:
        """Removes sandbox containers left behind by crashed tasks.

        Returns:
            removed: Number of orphaned containers removed.
        """
        orphans = self._client.containers.list(  # type: ignore[attr-defined]
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
            self._client.images.get(image)  # type: ignore[attr-defined]
        except docker.errors.ImageNotFound:
            logger.info("pulling sandbox image %s", image)
            self._client.images.pull(image)  # type: ignore[attr-defined]

class SandboxPolicyError(Exception):
    """Raised when a launch would violate the sandbox security policy."""
