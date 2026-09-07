#!/usr/bin/env python3
"""
app.py --- Textual application composing the four regions of the interface

Contains:
    DEFAULT_GATEWAY_URL: gateway the connection indicator polls by default
    REGION_IDS: element ids for the four regions, in composition order
    ShipwrightApp: the terminal interface for one checkout
    ShipwrightApp.get_css_variables(): feeds the palette into Textual's tokens
    ShipwrightApp.compose(): lays out wordmark, header, timeline, composer, footer
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
from tui.theme import Palette, css_variables, palette_for
from tui.transcript import resume
from tui.widgets.connection_dot import ConnectionDot
from tui.widgets.setup_panel import SetupPanel, detect_missing
from tui.widgets.wordmark import Wordmark

DEFAULT_GATEWAY_URL = "http://localhost:4000"
# The four regions, in the order they are composed down the screen.
REGION_IDS = ("region-header", "region-timeline", "region-composer", "region-footer")


class ShipwrightApp(App[None]):
    """Drives the terminal interface for one checkout.

    Attributes:
        repo_path: Checkout the agent is pointed at.
        provider: Provider answering the run's steps.
        gateway_url: Gateway the connection indicator polls.
        cost_tracker: Tracker the header's cost readout is drawn from.
        palette: Colours the interface renders with.
        breaker: Ceilings the live /max-cost and /max-steps commands adjust.
        router: Slash-command router for the composer.
    """

    CSS = """
    Screen {
        layout: vertical;
        overflow: hidden;
    }
    #region-wordmark {
        height: 5;
    }
    #region-header {
        height: 1;
    }
    #region-connection {
        height: 1;
    }
    #region-setup {
        height: auto;
        max-height: 10;
    }
    #region-timeline {
        height: 1fr;
    }
    #region-composer {
        height: 3;
    }
    #region-footer {
        height: 1;
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
        palette: Palette | None = None,
    ) -> None:
        """Builds the interface for one checkout.

        Args:
            repo_path: Checkout the agent is pointed at.
            provider: Provider answering the run's steps.
            gateway_url: Gateway the connection indicator polls.
            cost_tracker: Tracker the header's cost readout is drawn from.
            palette: Colours to render with; detected from the terminal when None.
        """
        # Textual resolves CSS variables inside App.__init__, so the palette has
        # to exist before the base class is initialised.
        self.palette: Palette = palette_for() if palette is None else palette
        super().__init__()
        self.repo_path: Path = repo_path
        self.provider: str = provider
        self.gateway_url: str = gateway_url
        self.cost_tracker = cost_tracker if cost_tracker is not None else CostTracker()
        self.breaker = CircuitBreaker()
        self.router = CommandRouter()

    def get_css_variables(self) -> dict[str, str]:
        """Feeds the project palette into Textual's own design tokens.

        The palette is resolved once when the app is built, not read from the
        environment here: a test, or a CI run with no TERM, would otherwise get
        a different theme than the one it asked for.

        Returns:
            variables: Textual's defaults overlaid with the project palette.
        """
        return {**super().get_css_variables(), **css_variables(self.palette)}

    def needs_setup(self) -> bool:
        """Reports whether any provider credential is still missing.

        Returns:
            needs_setup: True when the setup panel should be shown first.
        """
        return len(detect_missing()) == len(list(Provider))

    def compose(self) -> ComposeResult:
        """Lays out the header, timeline, composer, and footer."""
        wordmark = Wordmark()
        wordmark.id = "region-wordmark"
        yield wordmark

        header = HeaderBar(self.repo_path, self.provider, self.cost_tracker)
        header.id = REGION_IDS[0]
        yield header

        dot = ConnectionDot()
        dot.id = "region-connection"
        yield dot

        if self.needs_setup():
            setup = SetupPanel(self.repo_path)
            setup.id = "region-setup"
            yield setup

        timeline = Timeline()
        timeline.id = REGION_IDS[1]
        yield timeline

        composer = Composer()
        composer.id = REGION_IDS[2]
        yield composer

        bindings = [binding for binding in self.BINDINGS if isinstance(binding, Binding)]
        footer = FooterBar(bindings)
        footer.id = REGION_IDS[3]
        yield footer

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
        if not text.strip():
            return ""
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
