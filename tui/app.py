#!/usr/bin/env python3
"""
app.py --- Textual application composing the four regions of the interface

Contains:
    DEFAULT_GATEWAY_URL: gateway the connection indicator polls by default
    REGION_IDS: element ids for the four regions, in composition order
    ShipwrightApp: the terminal interface for one checkout
    ShipwrightApp.get_css_variables(): feeds the palette into Textual's tokens
    ShipwrightApp.compose(): lays out header, timeline, composer, and footer
    ShipwrightApp.needs_setup(): whether a provider credential is missing
    ShipwrightApp.register_commands(): binds each slash command to its handler
    ShipwrightApp.on_mount(): wires the slash commands once mounted
    ShipwrightApp.on_composer_submitted(): routes a submitted line
    ShipwrightApp.handle_line(): runs a command or starts a turn
"""

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding

from agent.circuit_breaker import CircuitBreaker
from agent.cost_tracker import CostTracker
from agent.llm_client import Provider
from tui.commands import CommandRouter, UnknownCommandError, set_max_cost, set_max_steps
from tui.screens.composer import Composer
from tui.screens.footer import FooterBar
from tui.screens.header import HeaderBar
from tui.screens.timeline import Timeline
from tui.theme import css_variables, palette_for
from tui.transcript import resume
from tui.widgets.connection_dot import ConnectionDot
from tui.widgets.setup_panel import SetupPanel, detect_missing

DEFAULT_GATEWAY_URL = "http://localhost:4000"
REGION_IDS = ("region-header", "region-timeline", "region-composer", "region-footer")


class ShipwrightApp(App[None]):
    """Drives the terminal interface for one checkout.

    Attributes:
        repo_path: Checkout the agent is pointed at.
        provider: Provider answering the run's steps.
        gateway_url: Gateway the connection indicator polls.
        cost_tracker: Tracker the header's cost readout is drawn from.
        breaker: Ceilings the live /max-cost and /max-steps commands adjust.
        router: Slash-command router for the composer.
    """

    CSS = """
    #region-timeline {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+l", "screenshot", "Screenshot"),
    ]

    def __init__(
        self,
        repo_path: Path,
        provider: str = Provider.ANTHROPIC.value,
        gateway_url: str = DEFAULT_GATEWAY_URL,
        cost_tracker: CostTracker | None = None,
    ) -> None:
        """Builds the interface for one checkout.

        Args:
            repo_path: Checkout the agent is pointed at.
            provider: Provider answering the run's steps.
            gateway_url: Gateway the connection indicator polls.
            cost_tracker: Tracker the header's cost readout is drawn from.
        """
        super().__init__()
        self.repo_path: Path = repo_path
        self.provider: str = provider
        self.gateway_url: str = gateway_url
        self.cost_tracker = cost_tracker if cost_tracker is not None else CostTracker()
        self.breaker = CircuitBreaker()
        self.router = CommandRouter()

    def get_css_variables(self) -> dict[str, str]:
        """Feeds the project palette into Textual's own design tokens.

        Returns:
            variables: Textual's defaults overlaid with the project palette.
        """
        return {**super().get_css_variables(), **css_variables(palette_for())}

    def needs_setup(self) -> bool:
        """Reports whether any provider credential is still missing.

        Returns:
            needs_setup: True when the setup panel should be shown first.
        """
        return len(detect_missing()) == len(list(Provider))

    def compose(self) -> ComposeResult:
        """Lays out the header, timeline, composer, and footer."""
        yield HeaderBar(self.repo_path, self.provider, self.cost_tracker)
        yield ConnectionDot()
        if self.needs_setup():
            yield SetupPanel(self.repo_path)
        timeline = Timeline()
        timeline.id = REGION_IDS[1]
        yield timeline
        yield Composer()
        yield FooterBar(self.BINDINGS)

    def register_commands(self) -> None:
        """Binds each slash command the composer can route to its handler."""
        self.router.register("max-cost", lambda arg: set_max_cost(self.breaker, arg))
        self.router.register("max-steps", lambda arg: set_max_steps(self.breaker, arg))
        self.router.register("resume", resume)

    def on_mount(self) -> None:
        """Registers the slash commands once the interface is mounted."""
        self.register_commands()

    def handle_line(self, text: str) -> str:
        """Runs a slash command, or reports that a turn should start.

        Args:
            text: Raw line the operator submitted.

        Returns:
            notice: What to show the operator in response.
        """
        try:
            routed = self.router.dispatch(text)
        except UnknownCommandError as exc:
            return f"unknown command: /{exc}"
        if routed is not None:
            return routed
        self.query_one(Timeline).start_turn(text)
        return text

    def on_composer_submitted(self, event: Composer.Submitted) -> None:
        """Routes a line the composer submitted.

        Args:
            event: Message carrying the submitted instruction.
        """
        self.handle_line(event.instruction)
