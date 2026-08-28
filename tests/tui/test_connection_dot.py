#!/usr/bin/env python3
"""
test_connection_dot.py --- covers the gateway connection indicator

Contains:
    test_healthy_gateway_reads_healthy(): a 200 answer turns the dot green
    test_non_200_is_unreachable(): a 503 answer never reads as healthy
    test_transport_error_is_unreachable(): a refused connection fails closed
    test_blank_base_url_is_unreachable(): no configured gateway fails closed
    test_colours_are_distinct(): the three states are visually distinguishable
"""

import httpx

from tui.theme import DARK
from tui.widgets.connection_dot import ConnectionDot, ConnectionState, probe_health


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
