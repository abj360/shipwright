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
    ShipwrightApp.remember_turn(): keeps a finished turn for later reasoning
    ShipwrightApp.run_task(): runs one instruction off the UI thread
    ShipwrightApp.append_step(): mounts one activity row as a step completes
    ShipwrightApp.finish_run(): closes the turn and starts any queued work
    ShipwrightApp.switch_provider(): points later runs at another provider or model
    ShipwrightApp.describe_models(): lists the models the provider serves
    ShipwrightApp.model_label(): the provider and model shown under the composer
    ShipwrightApp.refresh_context_bar(): updates fullness and model readout
    ShipwrightApp.toggle_plan_mode(): turns plan-then-execute on and off
    ShipwrightApp.approve_plan(): shows a proposed plan and waits for an answer
    ShipwrightApp.show_plan_panel(): mounts a plan panel and focuses it
    ShipwrightApp.on_setup_panel_saved(): dismisses onboarding once a key is stored
    ShipwrightApp.on_setup_panel_skipped(): dismisses onboarding when declined
"""

from collections.abc import Callable
from pathlib import Path

import httpx
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.widgets import Label

from agent.circuit_breaker import CircuitBreaker, RunawayRunError
from agent.cost_tracker import CostTracker
from agent.llm_client import (
    DEFAULT_MODELS,
    MissingCredentialError,
    Provider,
    build_client,
    models_for,
    provider_for_model,
)
from agent.llm_client import Message as LoopMessage
from agent.loop import AgentConfig, AgentLoop, Step
from agent.planner import Plan, RepoPlanner, RepoReader, build_outline
from agent.repo_map import RepoMap
from tui.commands import (
    USAGE_MODEL,
    CommandRouter,
    UnknownCommandError,
    parse_provider,
    set_max_cost,
    set_max_steps,
    switch_model,
)
from tui.screens.composer import Composer
from tui.screens.footer import FooterBar
from tui.screens.timeline import Timeline
from tui.theme import Palette, css_variables, palette_for
from tui.transcript import resume
from tui.widgets.context_bar import ContextBar
from tui.widgets.diff_panel import DiffPanel
from tui.widgets.plan_panel import PlanPanel
from tui.widgets.robot import Phase, Robot, StatusLine, phase_for_tool
from tui.widgets.setup_panel import SetupPanel, Verification, detect_missing
from tui.widgets.step_row import StepRow
from tui.widgets.wordmark import Wordmark

DEFAULT_GATEWAY_URL = "http://localhost:4000"
INSTRUCTION_PREFIX = "● "
ANSWER_PREFIX = "● "
NO_ANSWER_NOTICE = "(the run ended without an answer)"
# Earlier turns replayed into each new run. Capped so a long session cannot
# crowd out the transcript the loop still has to fit in its own budget.
HISTORY_TURN_LIMIT = 12
HERO_TAGLINE = "describe a change and press enter"
PLAN_DECISION_TIMEOUT_S = 300.0
PLAN_ON_NOTICE = "plan mode on — runs propose steps and wait for [a] to accept"
PLAN_OFF_NOTICE = "plan mode off — runs execute directly"
SETUP_DONE_TEMPLATE = "{env_var} saved — you are ready to go"
SETUP_SKIPPED_NOTICE = "setup skipped — set a provider key before starting a run"
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
    #region-hero {
        height: 1fr;
        align: center middle;
    }
    #region-hero.compact {
        height: auto;
        padding-top: 1;
    }
    #region-hero.compact #hero-robot,
    #region-hero.compact #hero-tagline {
        display: none;
    }
    #hero-mark {
        width: auto;
        color: $accent;
    }
    #hero-robot {
        width: auto;
        color: $accent;
    }
    #hero-tagline {
        width: auto;
        color: $text-muted;
    }
    #region-setup {
        height: auto;
    }
    #region-timeline {
        height: 1fr;
        padding: 0 2;
    }
    #region-status {
        height: 1;
        padding: 0 2;
        color: $accent;
    }
    #region-composer {
        height: 3;
    }
    #region-context {
        height: 1;
        padding: 0 2;
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
        self.model: str | None = None
        self.plan_mode = False
        self.active_loop: AgentLoop | None = None
        self.credential_verifier: Callable[[Provider, str], Verification] | None = None
        self.conversation: list[LoopMessage] = []
        self.active_instruction = ""

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
        """Lays out the hero, the timeline, the status line, and the composer."""
        hero = Vertical(
            Wordmark(id="hero-mark"),
            Robot(id="hero-robot"),
            Label(HERO_TAGLINE, id="hero-tagline"),
            id="region-hero",
        )
        if self.needs_setup():
            hero.add_class("compact")
        yield hero

        if self.needs_setup():
            setup = SetupPanel(self.repo_path, verifier=self.credential_verifier)
            setup.id = "region-setup"
            yield setup

        timeline = Timeline()
        timeline.id = REGION_IDS[1]
        timeline.display = False
        yield timeline

        status = StatusLine()
        status.id = "region-status"
        status.display = False
        yield status

        composer = Composer()
        composer.id = REGION_IDS[2]
        yield composer

        context = ContextBar(self.model_label(), palette=self.palette)
        context.id = "region-context"
        yield context

        bindings = [binding for binding in self.BINDINGS if isinstance(binding, Binding)]
        footer = FooterBar(bindings)
        footer.id = REGION_IDS[3]
        yield footer

    def enter_working_view(self) -> None:
        """Swaps the idle hero for the transcript once work begins."""
        self.query_one("#region-hero").display = False
        self.query_one(Timeline).display = True
        self.query_one(StatusLine).display = True

    def register_commands(self) -> None:
        """Binds each slash command the composer can route to its handler."""
        self.router.register("max-cost", lambda arg: set_max_cost(self.breaker, arg))
        self.router.register("max-steps", lambda arg: set_max_steps(self.breaker, arg))
        self.router.register("resume", resume)
        self.router.register("model", self.switch_provider)
        self.router.register("plan", self.toggle_plan_mode)

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
        self.enter_working_view()
        self.active_instruction = instruction
        timeline = self.query_one(Timeline)
        timeline.start_turn(instruction)
        timeline.mount(Label(f"{INSTRUCTION_PREFIX}{instruction}"))
        status = self.query_one(StatusLine)
        status.display = True
        status.set_phase(Phase.PLANNING)
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
        config.history = list(self.conversation)
        client = build_client(Provider(self.provider), self.model)
        if self.plan_mode:
            config.mode = "plan_execute"
            outline = build_outline(RepoReader(self.repo_path).read(), RepoMap(self.repo_path))
            config.planner = RepoPlanner(client, outline)
            config.plan_gate = self.approve_plan
        return AgentLoop(client, config)

    @work(thread=True, exclusive=True)
    def run_task(self, instruction: str) -> None:
        """Runs one instruction through the agent loop, off the UI thread.

        Args:
            instruction: What the operator asked the agent to do.
        """
        try:
            composer = self.query_one(Composer)
        except NoMatches:
            # The interface was torn down while this run was starting; there is
            # nothing left to report progress to.
            return
        self.call_from_thread(composer.mark_busy)
        try:
            loop = self.build_loop(instruction)
            self.active_loop = loop
            result = loop.run(on_step=lambda step: self.call_from_thread(self.append_step, step))
            answer = result.final_answer or NO_ANSWER_NOTICE
        except MissingCredentialError as exc:
            answer = str(exc)
        except RunawayRunError as exc:
            answer = f"halted: {exc}"
        except httpx.HTTPError as exc:
            answer = f"provider unreachable: {exc}"
        if self.is_running:
            self.call_from_thread(self.finish_run, answer)
        self.active_loop = None

    def switch_provider(self, argument: str) -> str:
        """Points later runs, and any run in flight, at another provider.

        Args:
            argument: Provider name, optionally followed by a model identifier.

        Returns:
            line: Confirmation of the new provider, or a usage hint.
        """
        parts = argument.split()
        if not parts:
            return self.describe_models()

        model: str | None = None
        provider = parse_provider(parts[0])
        if provider is None:
            # A bare model identifier switches models without naming the provider,
            # which is what you actually want mid-task.
            owner = provider_for_model(parts[0])
            if owner is None:
                return USAGE_MODEL
            provider = owner
            model = parts[0]
        elif len(parts) > 1:
            model = parts[1]
        try:
            build_client(provider, model)
        except MissingCredentialError as exc:
            return str(exc)

        self.provider = provider.value
        self.model = model
        if self.active_loop is not None:
            switch_model(self.active_loop, argument)
        self.query_one(ContextBar).set_model(self.model_label())
        return f"now using {provider.value}" + (f" / {model}" if model else "")

    def describe_models(self) -> str:
        """Lists the models available on the current provider.

        Returns:
            listing: One line naming each model, marking the active one.
        """
        active = self.model or DEFAULT_MODELS[Provider(self.provider)]
        names = [
            f"{'*' if name == active else ' '} {name}"
            for name in models_for(Provider(self.provider))
        ]
        return f"{self.provider}:  " + "   ".join(names)

    def toggle_plan_mode(self, argument: str) -> str:
        """Turns plan-then-execute on and off for later runs.

        Args:
            argument: Ignored; the command is a toggle.

        Returns:
            line: Which mode later runs will use.
        """
        del argument
        self.plan_mode = not self.plan_mode
        return PLAN_ON_NOTICE if self.plan_mode else PLAN_OFF_NOTICE

    def approve_plan(self, plan: Plan) -> bool:
        """Shows a proposed plan and blocks the run until it is answered.

        Runs on the worker thread, so the panel is mounted through the UI
        thread and the worker parks on the panel's own decision event.

        Args:
            plan: Plan the planner produced for this run.

        Returns:
            is_approved: True only when the operator explicitly accepted.
        """
        panel = PlanPanel(plan)
        self.call_from_thread(self.show_plan_panel, panel)
        return panel.wait_for_decision(PLAN_DECISION_TIMEOUT_S)

    def show_plan_panel(self, panel: PlanPanel) -> None:
        """Mounts a proposed-plan panel and puts the keyboard on it.

        Args:
            panel: Panel awaiting the operator's decision.
        """
        self.query_one(Timeline).mount(panel)
        panel.focus()

    def on_setup_panel_saved(self, event: SetupPanel.Saved) -> None:
        """Dismisses onboarding once a provider key has been stored.

        Args:
            event: Message naming the variable that was written.
        """
        event.stop()
        self.query_one(SetupPanel).remove()
        self.query_one(Timeline).mount(Label(SETUP_DONE_TEMPLATE.format(env_var=event.env_var)))
        self.query_one(Composer).focus_input()

    def on_setup_panel_skipped(self, event: SetupPanel.Skipped) -> None:
        """Dismisses onboarding when the operator declines to enter a key.

        Args:
            event: Message reporting that setup was dismissed.
        """
        event.stop()
        self.query_one(SetupPanel).remove()
        self.query_one("#region-hero").remove_class("compact")
        self.query_one(Composer).focus_input()

    def remember_turn(self, instruction: str, answer: str) -> None:
        """Keeps a finished turn so later runs reason against the whole session.

        Args:
            instruction: What the operator asked for.
            answer: What the agent reported back.
        """
        if not instruction:
            return
        self.conversation.append(LoopMessage(role="user", content=instruction))
        self.conversation.append(LoopMessage(role="assistant", content=answer))
        excess = len(self.conversation) - HISTORY_TURN_LIMIT * 2
        if excess > 0:
            del self.conversation[:excess]

    def model_label(self) -> str:
        """Renders the provider and model currently answering.

        Returns:
            label: Provider and model, as the bar under the composer shows it.
        """
        return f"{self.provider}/{self.model or DEFAULT_MODELS[Provider(self.provider)]}"

    def refresh_context_bar(self) -> None:
        """Updates the context readout from the run currently in flight."""
        bar = self.query_one(ContextBar)
        bar.set_model(self.model_label())
        if self.active_loop is not None:
            bar.set_usage(self.active_loop.context_usage())

    def append_step(self, step: Step) -> None:
        """Mounts one activity row as its step completes.

        Args:
            step: Step the agent loop just observed.
        """
        timeline = self.query_one(Timeline)
        self.query_one(StatusLine).set_phase(phase_for_tool(step.tool_name))
        row = StepRow(step.tool_name, step.tool_args, step.observation, palette=self.palette)
        timeline.record_step(row)
        timeline.mount(row)
        if step.diff:
            timeline.mount(DiffPanel(step.diff, palette=self.palette))
        timeline.scroll_end(animate=False)
        self.refresh_context_bar()

    def finish_run(self, answer: str) -> None:
        """Closes the open turn and starts whatever was queued behind it.

        Args:
            answer: Final answer, or the reason the run produced none.
        """
        self.remember_turn(self.active_instruction, answer)
        timeline = self.query_one(Timeline)
        timeline.finish_turn(answer)
        timeline.mount(Label(f"{ANSWER_PREFIX}{answer}"))
        timeline.scroll_end(animate=False)
        self.query_one(StatusLine).stop()
        self.refresh_context_bar()
        composer = self.query_one(Composer)
        composer.mark_idle()
        queued = composer.take_next()
        if queued is not None:
            self.start_turn_for(queued)

    def on_composer_submitted(self, event: Composer.Submitted) -> None:
        """Routes a line the composer submitted.

        Args:
            event: Message carrying the submitted instruction.
        """
        self.handle_line(event.instruction)
