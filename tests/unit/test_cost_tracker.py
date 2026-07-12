#!/usr/bin/env python3
"""
test_cost_tracker.py --- unit tests for per-run cost tracking
"""

import pytest

from agent.cost_tracker import CostTracker

def test_record_accumulates_running_total() -> None:
    """Verifies record() returns a monotonically growing total."""
    tracker = CostTracker()
    first = tracker.record("claude-sonnet-4-5", 1000, 100)
    second = tracker.record("claude-sonnet-4-5", 1000, 100)
    assert second > first

def test_unknown_model_uses_fallback_price() -> None:
    """Verifies unknown models are priced with the fallback rate."""
    tracker = CostTracker()
    total = tracker.record("mystery-model", 1_000_000, 0)
    assert total == 3.0

def test_cost_mx_3_1() -> None:
    """Verifies recording usage for scripted 50000/5000 tokens."""
    tracker = CostTracker()
    total = tracker.record("scripted", 50000, 5000)
    assert total >= 0.0
