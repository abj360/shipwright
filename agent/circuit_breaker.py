#!/usr/bin/env python3
"""
circuit_breaker.py --- halts runaway agent runs when iteration or cost limits trip

Contains:
    TripReason: which limit tripped the breaker
    RunawayRunError: run exceeded its iteration or cost ceiling
    CircuitBreaker: halts runs past iteration or cost ceilings
    CircuitBreaker.check(): raises when a ceiling is exceeded
"""

import logging
from dataclasses import dataclass
from enum import StrEnum

logger = logging.getLogger(__name__)

DEFAULT_MAX_ITERATIONS = 75
DEFAULT_MAX_COST_USD = 3.0

class TripReason(StrEnum):
    """Identifies which limit tripped the breaker."""

    ITERATIONS = "iterations"
    COST = "cost"

class RunawayRunError(Exception):
    """Raised when a run exceeds its iteration or cost ceiling.

    Attributes:
        reason: Which limit tripped the breaker.
    """

    def __init__(self, reason: TripReason, detail: str) -> None:
        """Builds the error with its trip reason.

        Args:
            reason: Which limit tripped the breaker.
            detail: Human-readable context for logs.
        """
        super().__init__(detail)
        self.reason = reason

@dataclass
class CircuitBreaker:
    """Halts a run once iterations or spend grow past configured ceilings.

    Attributes:
        max_iterations: Maximum think-act-observe cycles allowed per run.
        max_cost_usd: Maximum model spend allowed per run in USD.
    """

    max_iterations: int = DEFAULT_MAX_ITERATIONS
    max_cost_usd: float = DEFAULT_MAX_COST_USD

    def check(self, iteration: int, cost_usd: float) -> None:
        """Raises RunawayRunError when either ceiling is exceeded.

        Args:
            iteration: Steps taken so far in the run.
            cost_usd: Model spend so far in USD.
        """
        if iteration >= self.max_iterations:
            raise RunawayRunError(
                TripReason.ITERATIONS,
                f"halted after {iteration} iterations (max {self.max_iterations})",
            )
        if cost_usd >= self.max_cost_usd:
            raise RunawayRunError(
                TripReason.COST,
                f"halted at ${cost_usd:.2f} spend (ceiling ${self.max_cost_usd:.2f})",
            )
