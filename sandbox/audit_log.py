#!/usr/bin/env python3
"""
audit_log.py --- tamper-evident audit trail for every sandbox lifecycle event

Contains:
    AuditEvent: one tamper-evident audit record
    AuditLog: appends events to a hash-chained JSONL log
    AuditLog.record(): appends one event to the chain
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

    def __init__(self, path: Path) -> None:
        """Opens (or creates) the audit log file.

        Args:
            path: JSONL file events are appended to.
        """
        self._path = path
        self._prev_hash = "0" * 64

    def record(self, kind: str, detail: str) -> None:
        """Appends one event to the chain.

        Args:
            kind: Event category, e.g. container_started.
            detail: Free-form context for the event.
        """
        event = AuditEvent(kind=kind, detail=detail, ts=time.time())
        payload = json.dumps({"kind": event.kind, "detail": event.detail, "ts": event.ts})
        chain = self._chain_hash(payload)
        with self._path.open("a") as handle:
            handle.write(json.dumps({"event": payload, "chain": chain}) + "\n")
        self._prev_hash = chain

    def _chain_hash(self, payload: str) -> str:
        """Hashes one payload against the previous link in the chain.

        Args:
            payload: Serialized event to chain.

        Returns:
            digest: New head of the hash chain.
        """
        return hashlib.sha256((self._prev_hash + payload).encode()).hexdigest()

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
