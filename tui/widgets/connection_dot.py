#!/usr/bin/env python3
"""
connection_dot.py --- gateway connection indicator driven by GET /health

Contains:
    ConnectionState: whether the gateway is reachable and healthy
    DOT_GLYPH: the character the indicator draws
    HEALTH_PATH: gateway endpoint the indicator polls
    STREAM_PATH_TEMPLATE: websocket path carrying one run's live output
    WS_SCHEMES: how an http gateway root maps onto a websocket root
    HEALTH_TIMEOUT_S: how long a probe waits before giving up
    POLL_INTERVAL_S: how often the indicator re-checks the gateway
    HealthProbe: returns the status code GET /health answered with
    health_url(): builds the health endpoint for one gateway root
    probe_health(): resolves one health probe into a connection state
    stream_url(): builds the run-output websocket URL for one run
    state_for_stream(): maps a stream lifecycle event onto a connection state
    ConnectionDot: indicator widget reflecting the gateway's health
    ConnectionDot.on_mount(): starts polling once the indicator is attached
    ConnectionDot.poll_now(): schedules one probe off the UI thread
    ConnectionDot.apply_state(): records the state one probe resolved to
    ConnectionDot.color_for(): the colour one state draws in
    ConnectionDot.watch_state(): repaints the dot when the state changes
"""

import logging
from collections.abc import Callable
from enum import StrEnum

import httpx
from textual.reactive import reactive
from textual.widgets import Static

from tui.theme import Palette, palette_for

logger = logging.getLogger(__name__)

DOT_GLYPH = "●"
HEALTH_PATH = "/health"
STREAM_PATH_TEMPLATE = "/runs/{run_id}/stream"
WS_SCHEMES = {"http": "ws", "https": "wss"}
HEALTH_TIMEOUT_S = 2.0
POLL_INTERVAL_S = 5.0
HEALTHY_STATUS = 200

type HealthProbe = Callable[[str], int]


class ConnectionState(StrEnum):
    """Describes whether the gateway is reachable and healthy."""

    CONNECTING = "connecting"
    HEALTHY = "healthy"
    UNREACHABLE = "unreachable"


def _http_probe(url: str) -> int:
    """Asks the gateway for its health, returning the status code.

    Args:
        url: Fully-qualified health endpoint to call.

    Returns:
        status: HTTP status code the gateway answered with.
    """
    return httpx.get(url, timeout=HEALTH_TIMEOUT_S).status_code


def health_url(base_url: str) -> str:
    """Builds the health endpoint for one gateway root.

    Args:
        base_url: Root URL of the gateway.

    Returns:
        url: Fully-qualified health endpoint.
    """
    return f"{base_url.rstrip('/')}{HEALTH_PATH}"


def probe_health(base_url: str, probe: HealthProbe | None = None) -> ConnectionState:
    """Resolves one health probe into a connection state.

    Fails closed: a transport error, a timeout, or any non-200 answer reports
    the gateway as unreachable rather than leaving a stale green dot up.

    Args:
        base_url: Root URL of the gateway.
        probe: Performs the request; injected so tests need no server.

    Returns:
        state: Connection state the indicator should show.
    """
    if not base_url.strip():
        logger.warning("no gateway URL configured; reporting unreachable")
        return ConnectionState.UNREACHABLE
    caller: HealthProbe = _http_probe if probe is None else probe
    try:
        status = caller(health_url(base_url))
    except httpx.HTTPError as exc:
        logger.warning("gateway unreachable at %s: %s", health_url(base_url), exc)
        return ConnectionState.UNREACHABLE
    return ConnectionState.HEALTHY if status == HEALTHY_STATUS else ConnectionState.UNREACHABLE


class ConnectionDot(Static):
    """Draws a coloured dot reflecting whether the gateway is reachable.

    Attributes:
        state: Connection state currently displayed.
        palette: Colours the dot is drawn from.
    """

    state: reactive[ConnectionState] = reactive(ConnectionState.CONNECTING)

    def __init__(
        self,
        gateway_url: str = "",
        palette: Palette | None = None,
        probe: HealthProbe | None = None,
    ) -> None:
        """Builds the indicator in its connecting state.

        Args:
            gateway_url: Root URL of the gateway to poll.
            palette: Colours to draw from; detected from the terminal when None.
            probe: Performs the request; injected so tests need no server.
        """
        super().__init__(DOT_GLYPH)
        self.gateway_url = gateway_url
        self.palette: Palette = palette_for() if palette is None else palette
        self._probe = probe

    def on_mount(self) -> None:
        """Starts polling the gateway once the indicator is attached."""
        self.poll_now()
        self.set_interval(POLL_INTERVAL_S, self.poll_now)

    def poll_now(self) -> None:
        """Schedules one health probe off the UI thread.

        The probe is a blocking HTTP call, so it must not run on the UI thread:
        a gateway that is down would otherwise freeze the interface for as long
        as the timeout.
        """
        self.run_worker(self._poll_once, thread=True, exclusive=True)

    def _poll_once(self) -> None:
        """Probes the gateway and hands the result back to the UI thread."""
        state = probe_health(self.gateway_url, self._probe)
        self.app.call_from_thread(self.apply_state, state)

    def apply_state(self, state: ConnectionState) -> None:
        """Records the state one probe resolved to.

        Args:
            state: Connection state the probe reported.
        """
        self.state = state

    def color_for(self, state: ConnectionState) -> str:
        """Returns the colour one connection state draws in.

        Args:
            state: Connection state being drawn.

        Returns:
            color: Blue while connecting, green when healthy, red when not.
        """
        if state is ConnectionState.HEALTHY:
            return self.palette.add
        if state is ConnectionState.CONNECTING:
            return self.palette.accent
        return self.palette.status_error

    def watch_state(self, state: ConnectionState) -> None:
        """Repaints only this dot when the connection state changes.

        Args:
            state: Connection state the indicator moved to.
        """
        # An empty token means a monochrome terminal: leave the colour unset
        # rather than writing an empty string Textual cannot parse.
        self.styles.color = self.color_for(state) or None


def stream_url(base_url: str, run_id: str) -> str:
    """Builds the websocket URL carrying one run's live output.

    The gateway serves the stream on the same host and port as the REST API,
    so the root is reused and only the scheme is swapped.

    Args:
        base_url: Root URL of the gateway, as an http or https address.
        run_id: Run whose output stream is wanted.

    Returns:
        url: Websocket URL for that run's output stream.
    """
    root = base_url.strip().rstrip("/")
    if not root:
        return STREAM_PATH_TEMPLATE.format(run_id=run_id)
    scheme, separator, remainder = root.partition("://")
    if separator:
        root = f"{WS_SCHEMES.get(scheme, scheme)}://{remainder}"
    return root + STREAM_PATH_TEMPLATE.format(run_id=run_id)


def state_for_stream(is_open: bool, had_error: bool) -> ConnectionState:
    """Maps a stream's lifecycle onto the state the indicator should show.

    Args:
        is_open: Whether the websocket is currently connected.
        had_error: Whether the stream reported an error or dropped.

    Returns:
        state: Red on error, green while open, blue while still connecting.
    """
    if had_error:
        return ConnectionState.UNREACHABLE
    return ConnectionState.HEALTHY if is_open else ConnectionState.CONNECTING
