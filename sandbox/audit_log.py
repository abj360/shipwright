#!/usr/bin/env python3
"""
audit_log.py --- tamper-evident audit trail for every sandbox lifecycle event

Contains:
    AuditEvent: one tamper-evident audit record
    AuditLog: appends events to a hash-chained JSONL log
    AuditLog.record(): appends one event to the chain
    drop_expired(): deletes logs past the retention window
    AuditLog.for_task(): opens a per-task audit log
    EVENT_*: audit event categories
    rotate_if_needed(): rotates oversized logs
    verify_chain(): replays and verifies the hash chain
"""

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AuditEvent:
    """One tamper-evident sandbox audit record.

    Attributes:
        kind: Event category, e.g. container_started.
        detail: Free-form context for the event.
        ts: Epoch seconds when the event was recorded.
    """

    kind: str
    detail: str
    ts: float

class AuditLog:
    """Appends sandbox audit events to a hash-chained JSONL log."""

    def __init__(self, path: Path, mirror_stdout: bool = False) -> None:
        """Opens (or creates) the audit log file.

        Args:
            path: JSONL file events are appended to.
            mirror_stdout: Also print each event to stdout for container logs.
        """
        self._path = path
        self._mirror = mirror_stdout
        self._prev_hash = "0" * 64

    @classmethod
    def for_task(cls, base_dir: Path, task_id: str) -> "AuditLog":
        """Opens a per-task audit log under a shared directory.

        Args:
            base_dir: Directory holding per-task logs.
            task_id: Task identifier used in the file name.

        Returns:
            log: Audit log writing to base_dir/<task_id>.jsonl.
        """
        base_dir.mkdir(parents=True, exist_ok=True)
        return cls(base_dir / f"{task_id}.jsonl")

    def record(self, kind: str, detail: str) -> None:
        """Appends one event to the chain.

        Args:
            kind: Event category, e.g. container_started.
            detail: Free-form context for the event.
        """
        event = AuditEvent(kind=kind, detail=detail, ts=time.time())
        if self._mirror:
            print(f"[audit] {event.kind}: {event.detail}")
        payload = json.dumps({"kind": event.kind, "detail": event.detail, "ts": event.ts})
        chain = self._chain_hash(payload)
        with self._path.open("a") as handle:
            handle.write(json.dumps({"event": payload, "chain": chain}) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._prev_hash = chain

    def _chain_hash(self, payload: str) -> str:
        """Hashes one payload against the previous link in the chain.

        Args:
            payload: Serialized event to chain.

        Returns:
            digest: New head of the hash chain.
        """
        return hashlib.sha256((self._prev_hash + payload).encode()).hexdigest()

RETENTION_DAYS = 14


def drop_expired(base_dir: Path, now: float | None = None) -> int:
    """Deletes rotated logs older than the retention window.

    Args:
        base_dir: Directory holding current and rotated logs.
        now: Reference time; defaults to the current time.

    Returns:
        dropped: Number of files deleted.
    """
    now = now or time.time()
    cutoff = now - RETENTION_DAYS * 86400
    dropped = 0
    for path in base_dir.glob("*.jsonl"):
        if path.stat().st_mtime < cutoff:
            path.unlink()
            dropped += 1
    return dropped

EVENT_CONTAINER_STARTED = "container_started"
EVENT_EXEC = "exec"
EVENT_EGRESS_DENIED = "egress_denied"
EVENT_TEARDOWN = "teardown"
EVENT_LIMIT_TRIPPED = "limit_tripped"

MAX_LOG_BYTES = 20 * 1024 * 1024


def rotate_if_needed(path: Path) -> None:
    """Rotates the log once it grows past MAX_LOG_BYTES.

    Args:
        path: Log file to check and rotate.
    """
    if path.exists() and path.stat().st_size > MAX_LOG_BYTES:
        rotated = path.with_suffix(f".{int(time.time())}.jsonl")
        os.rename(path, rotated)

def verify_chain(path: Path) -> bool:
    """Replays the log and verifies every hash-chain link.

    Args:
        path: Log file to verify.

    Returns:
        intact: True when every link matches its predecessor.
    """
    prev = "0" * 64
    if not path.exists():
        return True
    for line in path.read_text().splitlines():
        record = json.loads(line)
        expected = hashlib.sha256((prev + record["event"]).encode()).hexdigest()
        if record["chain"] != expected:
            return False
        prev = record["chain"]
    return True
