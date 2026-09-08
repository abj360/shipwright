#!/usr/bin/env python3
"""
test_connection_dot.py --- covers the gateway connection indicator

Contains:
    test_healthy_gateway_reads_healthy(): a 200 answer turns the dot green
    test_non_200_is_unreachable(): a 503 answer never reads as healthy
    test_transport_error_is_unreachable(): a refused connection fails closed
    test_blank_base_url_is_unreachable(): no configured gateway fails closed
    test_colours_are_distinct(): the three states are visually distinguishable
    test_mounted_dot_polls_the_gateway(): the indicator actually probes on mount
    test_mounted_dot_reports_an_unreachable_gateway(): a refused probe turns it red
    test_health_url_is_built_once(): a trailing slash does not double up
    test_timeout_is_unreachable(): a slow gateway is not shown as healthy
    test_stream_url_swaps_the_scheme(): http becomes ws, https becomes wss
    test_stream_state_mapping(): open is green, errored is red, neither is blue
    test_stream_url_without_a_root(): a blank gateway yields just the path
"""

import asyncio

import httpx
from textual.app import App, ComposeResult

from tui.theme import DARK
from tui.widgets.connection_dot import (
    ConnectionDot,
    ConnectionState,
    health_url,
    probe_health,
    state_for_stream,
    stream_url,
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


def test_stream_url_swaps_the_scheme() -> None:
    """Asserts the stream URL reuses the gateway host but as a websocket scheme."""
    assert stream_url("http://localhost:4000", "abc") == "ws://localhost:4000/runs/abc/stream"
    assert stream_url("https://gw.example/", "xyz") == "wss://gw.example/runs/xyz/stream"


def test_stream_state_mapping() -> None:
    """Asserts a live stream is green, a dropped one red, and a pending one blue."""
    assert state_for_stream(is_open=True, had_error=False) is ConnectionState.HEALTHY
    assert state_for_stream(is_open=True, had_error=True) is ConnectionState.UNREACHABLE
    assert state_for_stream(is_open=False, had_error=False) is ConnectionState.CONNECTING


def test_stream_url_without_a_root() -> None:
    """Asserts a blank gateway root yields a bare path rather than a broken URL."""
    assert stream_url("  ", "abc") == "/runs/abc/stream"


class _DotHarness(App[None]):
    """Mounts one connection indicator so a pilot can let it poll.

    Attributes:
        dot: The indicator under test.
    """

    def __init__(self, dot: ConnectionDot) -> None:
        """Builds the harness around one indicator.

        Args:
            dot: The indicator under test.
        """
        super().__init__()
        self.dot = dot

    def compose(self) -> ComposeResult:
        """Mounts the indicator under test."""
        yield self.dot


def _settled_state(probe: object) -> ConnectionState:
    """Mounts an indicator and waits for its first probe to land.

    Args:
        probe: Health probe the indicator should call.

    Returns:
        state: The state the indicator settled on.
    """

    async def _run() -> ConnectionState:
        dot = ConnectionDot("http://gateway.test", palette=DARK, probe=probe)  # type: ignore[arg-type]
        app = _DotHarness(dot)
        async with app.run_test() as pilot:
            for _ in range(40):
                await pilot.pause()
                await asyncio.sleep(0.02)
                if dot.state is not ConnectionState.CONNECTING:
                    break
            return dot.state

    return asyncio.run(_run())


def test_mounted_dot_polls_the_gateway() -> None:
    """Asserts the indicator probes on its own once mounted, without being asked."""
    assert _settled_state(lambda url: 200) is ConnectionState.HEALTHY


def test_mounted_dot_reports_an_unreachable_gateway() -> None:
    """Asserts a refused probe leaves the indicator red rather than stuck on blue."""

    def refuse(url: str) -> int:
        raise httpx.ConnectError("refused")

    assert _settled_state(refuse) is ConnectionState.UNREACHABLE
