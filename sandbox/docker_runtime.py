#!/usr/bin/env python3
"""
docker_runtime.py --- launches and supervises short-lived sandbox containers

Contains:
    SandboxConfig: one sandboxed execution environment
    ExecResult: outcome of one sandboxed command
    SandboxHandle: wraps a running sandbox container
    SandboxHandle.exec(): runs one command inside
    SandboxHandle.stop(): stops and removes the container
    DockerRuntime: launches short-lived sandbox containers
    DockerRuntime.launch(): starts one sandbox container
"""

import docker
import logging
from dataclasses import dataclass, field

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
        """Stops and removes the sandbox container."""
        self.container.stop(timeout=STOP_TIMEOUT_S)  # type: ignore[attr-defined]
        self.container.remove(force=True)  # type: ignore[attr-defined]

class DockerRuntime:
    """Launches short-lived sandbox containers through the docker daemon."""

    def __init__(self, client: object | None = None) -> None:
        """Connects to the docker daemon.

        Args:
            client: Injected docker client; defaults to the daemon from env.
        """
        self._client = client or docker.from_env()

    def launch(self, config: SandboxConfig) -> SandboxHandle:
        """Starts one sandbox container and returns its handle.

        Args:
            config: Sandbox description to launch.

        Returns:
            handle: Live sandbox ready for exec calls.
        """
        kwargs = self._container_kwargs(config)
        container = self._client.containers.run(**kwargs)  # type: ignore[attr-defined]
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
            "runtime": "runsc" if config.gvisor else None,
        }
