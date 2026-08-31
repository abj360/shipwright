#!/usr/bin/env python3
"""
test_header_cost.py --- covers the header's live cost and token readout

Contains:
    test_no_tracker_shows_zero(): a header without a tracker shows no spend
    test_spend_comes_from_the_tracker(): the figure matches the cost tracker
    test_tokens_are_shown_when_present(): the token count appears beside spend
    test_pricing_is_per_model(): two models are priced by their own rates
    test_header_line_carries_the_cost(): the rendered bar includes the spend
    test_over_budget_spend_is_marked(): passing the warn threshold is visible
"""

from pathlib import Path

from agent.cost_tracker import CostTracker
from tui.screens.header import NO_SPEND_LABEL, OVER_BUDGET_MARKER, HeaderBar, format_cost


def test_no_tracker_shows_zero() -> None:
    """Asserts a header with no cost tracker shows a zero spend rather than blank."""
    assert format_cost(None) == NO_SPEND_LABEL


def test_spend_comes_from_the_tracker() -> None:
    """Asserts the readout is the tracker's own total, not a separate sum."""
    tracker = CostTracker(budget_usd=5.0)
    tracker.record("claude-haiku-4-5", 1_000_000, 0)

    assert format_cost(tracker) == f"${tracker.total_usd():.4f}"


def test_tokens_are_shown_when_present() -> None:
    """Asserts a non-zero token count is shown next to the spend."""
    tracker = CostTracker(budget_usd=5.0)
    tracker.record("claude-haiku-4-5", 10, 5)

    assert "15 tok" in format_cost(tracker, 15)


def test_pricing_is_per_model() -> None:
    """Asserts two different models are priced by their own per-model rates."""
    haiku = CostTracker(budget_usd=5.0)
    haiku.record("claude-haiku-4-5", 1_000_000, 0)
    opus = CostTracker(budget_usd=5.0)
    opus.record("claude-opus-4-1", 1_000_000, 0)

    assert opus.total_usd() > haiku.total_usd()
    assert format_cost(haiku) != format_cost(opus)


def test_header_line_carries_the_cost(tmp_path: Path) -> None:
    """Asserts the rendered header line includes the live spend figure."""
    tracker = CostTracker(budget_usd=5.0)
    tracker.record("claude-haiku-4-5", 2_000, 1_000)
    bar = HeaderBar(tmp_path, "anthropic", tracker)

    assert f"${tracker.total_usd():.4f}" in bar.render_line_text()


def test_over_budget_spend_is_marked() -> None:
    """Asserts spend past the tracker's warn threshold is flagged on the bar."""
    tracker = CostTracker(budget_usd=0.01)
    tracker.record("claude-opus-4-1", 1_000_000, 0)

    assert OVER_BUDGET_MARKER in format_cost(tracker)
