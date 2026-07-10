#!/usr/bin/env python3
"""
audit_log.py --- tamper-evident audit trail for every sandbox lifecycle event

Contains:
    AuditEvent: one tamper-evident audit record
    AuditLog: appends events to a hash-chained JSONL log
    AuditLog.record(): appends one event to the chain
"""

import hashlib
import json
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
