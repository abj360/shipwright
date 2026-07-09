#!/usr/bin/env python3
"""
cost_tracker.py --- tracks model spend per agent run

Contains:
    Usage: token usage of one completion
    CostTracker: accumulates per-run model spend
    CostTracker.record(): adds usage and returns the running total
    CostTracker.total_usd(): computes total spend in USD
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-opus-4-1": (15.0, 75.0),
    "scripted": (0.0, 0.0),
}
FALLBACK_PRICE_PER_MTOK = (3.0, 15.0)
DEFAULT_BUDGET_USD = 5.0

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
        logger.debug("cost tracker ready")

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
        return self.total_usd()

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
