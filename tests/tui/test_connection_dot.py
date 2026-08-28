#!/usr/bin/env python3
"""
test_connection_dot.py --- covers the gateway connection indicator

Contains:
    test_healthy_gateway_reads_healthy(): a 200 answer turns the dot green
    test_non_200_is_unreachable(): a 503 answer never reads as healthy
    test_transport_error_is_unreachable(): a refused connection fails closed
    test_blank_base_url_is_unreachable(): no configured gateway fails closed
    test_colours_are_distinct(): the three states are visually distinguishable
    test_health_url_is_built_once(): a trailing slash does not double up
    test_timeout_is_unreachable(): a slow gateway is not shown as healthy
"""

import httpx

from tui.theme import DARK
from tui.widgets.connection_dot import (
    ConnectionDot,
    ConnectionState,
    health_url,
    probe_health,
)


def test_healthy_gateway_reads_healthy() -> None:
    """Asserts a gateway answering 200 is reported as healthy."""
    state = probe_health("http://localhost:4000", lambda url: 200)

    assert state is ConnectionState.HEALTHY


def test_non_200_is_unreachable() -> None:
    """Asserts a degraded gateway is never presented as healthy."""
    assert probe_health("http://localhost:4000", lambda url: 503) is ConnectionState.UNREACHABLE


def test_transport_error_is_unreachable() -> None:
    """Asserts a refused connection fails closed rather than raising."""

    def refuse(url: str) -> int:
        raise httpx.ConnectError("connection refused")

    assert probe_health("http://localhost:4000", refuse) is ConnectionState.UNREACHABLE


def test_blank_base_url_is_unreachable() -> None:
    """Asserts an unconfigured gateway URL reports unreachable, not healthy."""
    assert probe_health("   ", lambda url: 200) is ConnectionState.UNREACHABLE


def test_colours_are_distinct() -> None:
    """Asserts the three connection states each draw in their own colour."""
    dot = ConnectionDot(palette=DARK)

    colors = {dot.color_for(state) for state in ConnectionState}

    assert len(colors) == 3


def test_health_url_is_built_once() -> None:
    """Asserts a gateway URL with a trailing slash does not produce a double slash."""
    assert health_url("http://localhost:4000/") == "http://localhost:4000/health"
    assert health_url("http://localhost:4000") == "http://localhost:4000/health"


def test_timeout_is_unreachable() -> None:
    """Asserts a gateway that times out is reported unreachable, not healthy."""

    def stall(url: str) -> int:
        raise httpx.ReadTimeout("too slow")

    assert probe_health("http://localhost:4000", stall) is ConnectionState.UNREACHABLE
