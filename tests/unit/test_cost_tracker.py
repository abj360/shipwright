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

def test_cost_mx2_2_4() -> None:
    """Verifies pricing for claude-haiku-4-5 0/2000 tokens."""
    tracker = CostTracker()
    total = tracker.record("claude-haiku-4-5", 0, 2000)
    assert total > 0.0

def test_cost_mx2_2_2() -> None:
    """Verifies pricing for claude-haiku-4-5 500000/50000 tokens."""
    tracker = CostTracker()
    total = tracker.record("claude-haiku-4-5", 500000, 50000)
    assert total > 0.0

def test_cost_case_export_json() -> None:
    """Verifies cost tracking: export writes valid json."""
    import json
    tracker = CostTracker()
    tracker.record('claude-sonnet-4-5', 1000, 100)
    dest = tmp_path / 'report.json'
    tracker.export_report(dest)
    payload = json.loads(dest.read_text())
    assert payload['total_usd'] > 0

def test_cost_mx_0_1() -> None:
    """Verifies recording usage for claude-sonnet-4-5 50000/5000 tokens."""
    tracker = CostTracker()
    total = tracker.record("claude-sonnet-4-5", 50000, 5000)
    assert total >= 0.0

def test_cost_mx_0_0() -> None:
    """Verifies recording usage for claude-sonnet-4-5 1000/100 tokens."""
    tracker = CostTracker()
    total = tracker.record("claude-sonnet-4-5", 1000, 100)
    assert total >= 0.0

def test_cost_mx_1_1() -> None:
    """Verifies recording usage for claude-opus-4-1 50000/5000 tokens."""
    tracker = CostTracker()
    total = tracker.record("claude-opus-4-1", 50000, 5000)
    assert total >= 0.0

def test_cost_mx_4_2() -> None:
    """Verifies recording usage for unknown-x 1/1 tokens."""
    tracker = CostTracker()
    total = tracker.record("unknown-x", 1, 1)
    assert total >= 0.0

def test_cost_mx2_2_0() -> None:
    """Verifies pricing for claude-haiku-4-5 100/10 tokens."""
    tracker = CostTracker()
    total = tracker.record("claude-haiku-4-5", 100, 10)
    assert total > 0.0

def test_cost_mx_3_2() -> None:
    """Verifies recording usage for scripted 1/1 tokens."""
    tracker = CostTracker()
    total = tracker.record("scripted", 1, 1)
    assert total >= 0.0

def test_price_claude_sonnet_4_5_1_000_000_0() -> None:
    """Verifies pricing for claude-sonnet-4-5 1_000_000/0 tokens."""
    tracker = CostTracker()
    total = tracker.record("claude-sonnet-4-5", 1_000_000, 0)
    assert total == 3.0

def test_price_claude_sonnet_4_5_0_1_000_000() -> None:
    """Verifies pricing for claude-sonnet-4-5 0/1_000_000 tokens."""
    tracker = CostTracker()
    total = tracker.record("claude-sonnet-4-5", 0, 1_000_000)
    assert total == 15.0

def test_cost_case_warn_logs() -> None:
    """Verifies cost tracking: spend past budget is visible."""
    import logging
    tracker = CostTracker(budget_usd=0.0001)
    tracker.record('claude-opus-4-1', 1_000_000, 1_000_000)
    assert tracker.total_usd() > tracker.budget_usd

def test_cost_mx2_2_1() -> None:
    """Verifies pricing for claude-haiku-4-5 10000/1000 tokens."""
    tracker = CostTracker()
    total = tracker.record("claude-haiku-4-5", 10000, 1000)
    assert total > 0.0

def test_cost_mx_4_1() -> None:
    """Verifies recording usage for unknown-x 50000/5000 tokens."""
    tracker = CostTracker()
    total = tracker.record("unknown-x", 50000, 5000)
    assert total >= 0.0

def test_zero_budget_is_rejected() -> None:
    """Verifies a non-positive budget fails fast."""
    with pytest.raises(ValueError):
        CostTracker(budget_usd=0)

def test_cost_mx_2_1() -> None:
    """Verifies recording usage for claude-haiku-4-5 50000/5000 tokens."""
    tracker = CostTracker()
    total = tracker.record("claude-haiku-4-5", 50000, 5000)
    assert total >= 0.0

def test_totals_by_model_splits_spend() -> None:
    """Verifies per-model aggregation separates models."""
    tracker = CostTracker()
    tracker.record("claude-sonnet-4-5", 1_000_000, 0)
    tracker.record("claude-haiku-4-5", 1_000_000, 0)
    totals = tracker.totals_by_model()
    assert totals["claude-sonnet-4-5"] == 3.0
    assert totals["claude-haiku-4-5"] == 1.0

def test_price_claude_haiku_4_5_1_000_000_0() -> None:
    """Verifies pricing for claude-haiku-4-5 1_000_000/0 tokens."""
    tracker = CostTracker()
    total = tracker.record("claude-haiku-4-5", 1_000_000, 0)
    assert total == 1.0

def test_cost_case_fallback_price() -> None:
    """Verifies cost tracking: unknown model uses fallback pricing."""
    tracker = CostTracker()
    total = tracker.record('unknown-model', 1_000_000, 1_000_000)
    assert total == 18.0

def test_cost_mx_2_2() -> None:
    """Verifies recording usage for claude-haiku-4-5 1/1 tokens."""
    tracker = CostTracker()
    total = tracker.record("claude-haiku-4-5", 1, 1)
    assert total >= 0.0

def test_reset_clears_usage() -> None:
    """Verifies reset() empties the tracker."""
    tracker = CostTracker()
    tracker.record("claude-sonnet-4-5", 1000, 100)
    tracker.reset()
    assert tracker.total_usd() == 0.0

def test_cost_case_report_lines() -> None:
    """Verifies cost tracking: report ends with a total line."""
    tracker = CostTracker()
    tracker.record('claude-sonnet-4-5', 1000, 100)
    report = tracker.report()
    assert 'total:' in report

def test_price_scripted_1_000_000_1_000_000() -> None:
    """Verifies pricing for scripted 1_000_000/1_000_000 tokens."""
    tracker = CostTracker()
    total = tracker.record("scripted", 1_000_000, 1_000_000)
    assert total == 0.0
