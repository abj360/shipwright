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
    ShipwrightApp.start_turn_for(): opens a turn and dispatches it to the agent
    ShipwrightApp.build_loop(): builds the agent loop for one instruction
    ShipwrightApp.run_task(): runs one instruction off the UI thread
    ShipwrightApp.append_step(): mounts one activity row as a step completes
    ShipwrightApp.finish_run(): closes the turn and starts any queued work
"""

from pathlib import Path

import httpx
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Label

from agent.circuit_breaker import CircuitBreaker, RunawayRunError
from agent.cost_tracker import CostTracker
from agent.llm_client import MissingCredentialError, Provider, build_client
from agent.loop import AgentConfig, AgentLoop, Step
from tui.commands import CommandRouter, UnknownCommandError, set_max_cost, set_max_steps
from tui.screens.composer import Composer
from tui.screens.footer import FooterBar
from tui.screens.header import HeaderBar
from tui.screens.timeline import Timeline
from tui.theme import Palette, css_variables, palette_for
from tui.transcript import resume
from tui.widgets.connection_dot import ConnectionDot
from tui.widgets.setup_panel import SetupPanel, detect_missing
from tui.widgets.step_row import StepRow
from tui.widgets.wordmark import Wordmark

DEFAULT_GATEWAY_URL = "http://localhost:4000"
INSTRUCTION_PREFIX = "› "
ANSWER_PREFIX = "✓ "
NO_ANSWER_NOTICE = "(the run ended without an answer)"
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

        dot = ConnectionDot(self.gateway_url, palette=self.palette)
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
        """Registers the slash commands and puts the caret in the composer."""
        self.register_commands()
        self.query_one(Composer).focus_input()

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
        self.start_turn_for(text)
        return text

    def start_turn_for(self, instruction: str) -> None:
        """Opens a turn for one instruction and hands it to the agent.

        Args:
            instruction: What the operator asked the agent to do.
        """
        timeline = self.query_one(Timeline)
        timeline.start_turn(instruction)
        timeline.mount(Label(f"{INSTRUCTION_PREFIX}{instruction}"))
        self.run_task(instruction)

    def build_loop(self, instruction: str) -> AgentLoop:
        """Builds the agent loop that will carry out one instruction.

        The loop is given the app's own cost tracker and breaker, so the header
        readout and the live /max-cost and /max-steps commands govern the run
        that is actually executing.

        Args:
            instruction: What the operator asked the agent to do.

        Returns:
            loop: Loop ready to run against the configured checkout.
        """
        config = AgentConfig(
            repo_path=str(self.repo_path),
            task=instruction,
            cost_tracker=self.cost_tracker,
        )
        config.breaker = self.breaker
        return AgentLoop(build_client(Provider(self.provider)), config)

    @work(thread=True, exclusive=True)
    def run_task(self, instruction: str) -> None:
        """Runs one instruction through the agent loop, off the UI thread.

        Args:
            instruction: What the operator asked the agent to do.
        """
        composer = self.query_one(Composer)
        self.call_from_thread(composer.mark_busy)
        try:
            loop = self.build_loop(instruction)
            result = loop.run(on_step=lambda step: self.call_from_thread(self.append_step, step))
            answer = result.final_answer or NO_ANSWER_NOTICE
        except MissingCredentialError as exc:
            answer = str(exc)
        except RunawayRunError as exc:
            answer = f"halted: {exc}"
        except httpx.HTTPError as exc:
            answer = f"provider unreachable: {exc}"
        self.call_from_thread(self.finish_run, answer)

    def append_step(self, step: Step) -> None:
        """Mounts one activity row as its step completes.

        Args:
            step: Step the agent loop just observed.
        """
        timeline = self.query_one(Timeline)
        row = StepRow(step.tool_name, step.tool_args, step.observation, palette=self.palette)
        timeline.record_step(row)
        timeline.mount(row)
        timeline.scroll_end(animate=False)
        self.query_one(HeaderBar).refresh_line()

    def finish_run(self, answer: str) -> None:
        """Closes the open turn and starts whatever was queued behind it.

        Args:
            answer: Final answer, or the reason the run produced none.
        """
        timeline = self.query_one(Timeline)
        timeline.finish_turn(answer)
        timeline.mount(Label(f"{ANSWER_PREFIX}{answer}"))
        timeline.scroll_end(animate=False)
        composer = self.query_one(Composer)
        composer.mark_idle()
        self.query_one(HeaderBar).refresh_line()
        queued = composer.take_next()
        if queued is not None:
            self.start_turn_for(queued)

    def on_composer_submitted(self, event: Composer.Submitted) -> None:
        """Routes a line the composer submitted.

        Args:
            event: Message carrying the submitted instruction.
        """
        self.handle_line(event.instruction)
