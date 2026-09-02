#!/usr/bin/env python3
"""
test_breaker_controls.py --- covers live circuit-breaker adjustment commands

Contains:
    test_max_cost_updates_the_breaker(): a valid ceiling reaches the breaker
    test_max_steps_updates_the_breaker(): a valid count reaches the breaker
    test_router_routes_both_commands(): both commands dispatch through the router
    test_new_ceiling_actually_trips(): the adjusted ceiling is enforced
"""

import pytest

from agent.circuit_breaker import CircuitBreaker, RunawayRunError
from tui.commands import CommandRouter, set_max_cost, set_max_steps


def test_max_cost_updates_the_breaker() -> None:
    """Asserts a valid spend ceiling is applied to the live breaker."""
    breaker = CircuitBreaker(max_iterations=10, max_cost_usd=1.0)

    line = set_max_cost(breaker, "2.50")

    assert breaker.max_cost_usd == 2.50
    assert "2.50" in line


def test_max_steps_updates_the_breaker() -> None:
    """Asserts a valid iteration ceiling is applied to the live breaker."""
    breaker = CircuitBreaker(max_iterations=10, max_cost_usd=1.0)

    line = set_max_steps(breaker, "40")

    assert breaker.max_iterations == 40
    assert "40" in line


def test_router_routes_both_commands() -> None:
    """Asserts both breaker commands reach their handlers through the router."""
    breaker = CircuitBreaker(max_iterations=10, max_cost_usd=1.0)
    router = CommandRouter()
    router.register("max-cost", lambda arg: set_max_cost(breaker, arg))
    router.register("max-steps", lambda arg: set_max_steps(breaker, arg))

    router.dispatch("/max-cost 9")
    router.dispatch("/max-steps 99")

    assert breaker.max_cost_usd == 9.0
    assert breaker.max_iterations == 99


def test_new_ceiling_actually_trips() -> None:
    """Asserts the adjusted ceiling is the one the breaker enforces."""
    breaker = CircuitBreaker(max_iterations=100, max_cost_usd=100.0)
    set_max_steps(breaker, "3")

    with pytest.raises(RunawayRunError):
        breaker.check(3, 0.0)
