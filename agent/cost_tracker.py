#!/usr/bin/env python3
"""
cost_tracker.py --- tracks model spend per agent run

Contains:
    Usage: token usage of one completion
    CostTracker: accumulates per-run model spend
    CostTracker.record(): adds usage and returns the running total
    CostTracker.total_usd(): computes total spend in USD
    CostTracker.totals_by_model(): aggregates spend per model
    CostTracker.report(): renders a per-completion breakdown
    CostTracker.export_report(): writes the breakdown to JSON
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-5": (3.5, 16.0),
    "claude-opus-4-1": (15.0, 75.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "scripted": (0.0, 0.0),
}
FALLBACK_PRICE_PER_MTOK = (3.0, 15.0)
DEFAULT_BUDGET_USD = 5.0
WARN_THRESHOLD = 0.8

@dataclass(frozen=True)
class Usage:
    """Records token usage of one completion.

    Attributes:
        model: Model that produced the completion.
        input_tokens: Prompt tokens consumed.
        output_tokens: Completion tokens produced.
    """

    model: str
    input_tokens: int
    output_tokens: int

class CostTracker:
    """Accumulates per-run model spend.

    Attributes:
        budget_usd: Soft budget used for warning thresholds.
    """

    def __init__(self, budget_usd: float = DEFAULT_BUDGET_USD) -> None:
        """Starts an empty tracker with a soft budget.

        Args:
            budget_usd: Soft budget used for warning thresholds.
        """
        self.budget_usd = budget_usd
        self._entries: list[Usage] = []

    def record(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Adds one completion's usage and returns the running total.

        Args:
            model: Model that produced the completion.
            input_tokens: Prompt tokens consumed.
            output_tokens: Completion tokens produced.

        Returns:
            total_usd: Running total spend in USD.
        """
        self._entries.append(
            Usage(model=model, input_tokens=input_tokens, output_tokens=output_tokens)
        )
        total = self.total_usd()
        if total > self.budget_usd * WARN_THRESHOLD:
            logger.warning("run cost $%.2f exceeds %.0f%% of budget", total, WARN_THRESHOLD * 100)
        return total

    def total_usd(self) -> float:
        """Computes total spend in USD across all recorded usage.

        Returns:
            total_usd: Spend so far, priced per million tokens.
        """
        total = 0.0
        for entry in self._entries:
            price_in, price_out = PRICE_PER_MTOK.get(entry.model, FALLBACK_PRICE_PER_MTOK)
            total += (entry.input_tokens * price_in + entry.output_tokens * price_out) / 1_000_000
        return total

    def totals_by_model(self) -> dict[str, float]:
        """Aggregates spend per model.

        Returns:
            totals: Mapping of model identifier to USD spent.
        """
        totals: dict[str, float] = {}
        for entry in self._entries:
            price_in, price_out = PRICE_PER_MTOK.get(entry.model, FALLBACK_PRICE_PER_MTOK)
            cost = (entry.input_tokens * price_in + entry.output_tokens * price_out) / 1_000_000
            totals[entry.model] = totals.get(entry.model, 0.0) + cost
        return totals

    def report(self) -> str:
        """Renders a per-completion spend breakdown as text.

        Returns:
            report: One line per completion plus a total line.
        """
        lines = []
        for index, entry in enumerate(self._entries):
            price_in, price_out = PRICE_PER_MTOK.get(entry.model, FALLBACK_PRICE_PER_MTOK)
            cost = (entry.input_tokens * price_in + entry.output_tokens * price_out) / 1_000_000
            lines.append(f"  [{index}] {entry.model}: {entry.input_tokens}+{entry.output_tokens} tok = ${cost:.4f}")
        lines.append(f"total: ${self.total_usd():.4f}")
        return "\n".join(lines)

    def export_report(self, dest: Path) -> None:
        """Writes the spend breakdown to a JSON file.

        Args:
            dest: Path the report is written to.
        """
        payload = {
            "budget_usd": self.budget_usd,
            "total_usd": self.total_usd(),
            "entries": [
                {"model": e.model, "input_tokens": e.input_tokens, "output_tokens": e.output_tokens}
                for e in self._entries
            ],
        }
        dest.write_text(json.dumps(payload, indent=2))
