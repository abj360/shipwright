#!/usr/bin/env python3
"""
app.py --- Textual application composing the regions of the interface

Contains:
    DEFAULT_GATEWAY_URL: gateway the connection indicator polls by default
    REGION_IDS: element ids for the main regions, in composition order
    ShipwrightApp: the terminal interface for one checkout
    ShipwrightApp.get_css_variables(): feeds the palette into Textual's tokens
    ShipwrightApp.compose(): lays out wordmark, timeline, status, composer and context
    ShipwrightApp.needs_setup(): whether onboarding should run at startup
    ShipwrightApp.is_onboarded(): whether this install has been through onboarding
    ShipwrightApp.mark_onboarded(): records that onboarding was completed
    ShipwrightApp.open_setup(): re-runs provider setup on demand
    ShipwrightApp.onboarding(): builds the onboarding screen for this checkout
    ShipwrightApp.close_onboarding(): returns from onboarding to the home page
    ShipwrightApp.register_commands(): binds each slash command to its handler
    ShipwrightApp.on_mount(): wires the slash commands once mounted
    ShipwrightApp.offer_update(): shows the update the launcher found
    ShipwrightApp.on_update_panel_answered(): takes the update, or leaves it
    ShipwrightApp.start_or_queue(): starts a turn, or queues it behind the one running
    ShipwrightApp.on_unmount(): releases a waiting run as the interface closes
    ShipwrightApp.action_stop_run(): stops the run in flight from the keyboard
    ShipwrightApp.request_stop(): asks the run to stop and drops the queue
    ShipwrightApp.on_composer_stop_requested(): stops the run from the composer control
    ShipwrightApp.show_queued(): shows a queued message above the composer
    ShipwrightApp.on_composer_queued(): shows what the composer queued
    ShipwrightApp.show_notice(): writes a slash command's reply into the transcript
    ShipwrightApp.on_composer_submitted(): routes a submitted line
    ShipwrightApp.handle_line(): runs a command or starts a turn
    ShipwrightApp.start_turn_for(): opens a turn and dispatches it to the agent
    ShipwrightApp.build_loop(): builds the agent loop for one instruction
    ShipwrightApp.remember_turn(): keeps and saves a finished turn for later reasoning
    ShipwrightApp.report_save_failure(): says once that the session is not being saved
    ShipwrightApp.replay_conversation(): redraws a resumed session's turns in full
    ShipwrightApp.run_task(): runs one instruction off the UI thread
    ShipwrightApp.append_step(): mounts one activity row as a step completes
    ShipwrightApp.finish_run(): closes the turn and starts any queued work
    ShipwrightApp.switch_provider(): points later runs at another provider or model
    ShipwrightApp.describe_models(): lists the models the provider serves
    ShipwrightApp.mode_label(): the permission mode shown under the composer
    ShipwrightApp.set_permission_mode(): switches mode and shows it
    ShipwrightApp.mode_command(): lists the modes, or switches to the one named
    ShipwrightApp.action_cycle_mode(): moves to the next mode on shift+tab
    ShipwrightApp.model_label(): the model shown under the composer
    ShipwrightApp.refresh_context_bar(): updates fullness and model readout
    ShipwrightApp.toggle_plan_mode(): turns plan-then-execute on and off
    ShipwrightApp.approve_plan(): shows a proposed plan and waits for an answer
    ShipwrightApp.tool_gate(): the gate a run asks before each tool call
    ShipwrightApp.approve_tool(): asks about one tool call and waits for an answer
    ShipwrightApp.approve_escape(): asks before a command leaves the working directory
    ShipwrightApp.show_approval_panel(): mounts an approval panel and focuses it
    ShipwrightApp.on_approval_panel_decided(): returns the keyboard to the composer
    ShipwrightApp.show_plan_panel(): mounts a plan panel and focuses it
    ShipwrightApp.on_setup_panel_saved(): dismisses onboarding once a key is stored
    ShipwrightApp.on_setup_panel_skipped(): dismisses onboarding when declined
"""

import os
import threading
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path

import httpx
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.widgets import Static

from agent import __version__
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
from agent.permissions import (
    MODE_DESCRIPTIONS,
    MODE_ORDER,
    PermissionMode,
    ToolGate,
    gate_for,
    next_mode,
    parse_mode,
)
from agent.planner import Plan, RepoPlanner, RepoReader, build_outline
from agent.repo_map import RepoMap
from tui.commands import (
    INFERENCE_NOT_CONFIGURED,
    USAGE_MODEL,
    CommandRouter,
    UnknownCommandError,
    parse_provider,
    set_max_cost,
    set_max_steps,
    switch_model,
)
from tui.screens.composer import Composer
from tui.screens.onboarding import OnboardingScreen
from tui.screens.timeline import Timeline
from tui.sessions import (
    STATE_DIR_ENV,
    SavedStep,
    SavedTurn,
    new_session_id,
    request_update,
    save_session,
    sessions_dir,
    state_dir,
)
from tui.theme import TOKEN_FALLBACKS, Palette, css_variables, palette_for
from tui.transcript import resume
from tui.widgets.approval_panel import ESCAPE_TOOL, ApprovalPanel
from tui.widgets.context_bar import ContextBar
from tui.widgets.plan_panel import PlanPanel
from tui.widgets.robot import Phase, Robot, StatusLine, phase_for_tool
from tui.widgets.setup_panel import (
    CredentialStatus,
    SetupPanel,
    Verification,
    all_providers,
    detect_missing,
)
from tui.widgets.step_row import StepRow
from tui.widgets.update_panel import UpdatePanel
from tui.widgets.wordmark import Wordmark

DEFAULT_GATEWAY_URL = "http://localhost:4000"
ANSWER_PREFIX = "● "
STOPPED_NOTICE = "stopped"
# Set by the launcher, which is where the version check and the update happen.
UPDATE_AVAILABLE_ENV = "SHIPWRIGHT_UPDATE_AVAILABLE"
VERSION_ENV = "SHIPWRIGHT_VERSION"
SAVE_FAILED_TEMPLATE = (
    "this session is not being saved to {path} ({reason}), so --resume will not find it"
)
NO_ANSWER_NOTICE = "(the run ended without an answer)"
SETUP_ALREADY_OPEN = "setup is already open"
# Earlier turns replayed into each new run. Capped so a long session cannot
# crowd out the transcript the loop still has to fit in its own budget.
HISTORY_TURN_LIMIT = 12
ONBOARDED_MARKER = "onboarded"
PLAN_DECISION_TIMEOUT_S = 300.0
QUEUED_TITLE = "queued"
USAGE_MODE = "usage: /mode [manual|edit|plan|bypass]"
# Glyphs common terminal fonts actually carry: the pause and play triangles
# are missing from DejaVu and its relatives, and show as boxes.
MODE_MARKERS: dict[PermissionMode, str] = {
    PermissionMode.MANUAL: "·",
    PermissionMode.EDIT_AUTOMATICALLY: "»",
    PermissionMode.PLAN: "▸",
    PermissionMode.BYPASS: "»»",
}
PLAN_ON_NOTICE = "plan mode on — runs propose steps and wait for [a] to accept"
PLAN_OFF_NOTICE = "plan mode off — manual"
# The regions, in the order they are composed down the screen.
REGION_IDS = ("region-header", "region-timeline", "region-composer")


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
    #hero-mark {
        width: 100%;
        content-align: center middle;
        color: $accent;
    }
    #hero-robot {
        margin-bottom: 1;
        width: 100%;
        content-align: center middle;
        color: $accent;
    }
    #region-timeline {
        height: 1fr;
        padding: 0 2;
    }
    .notice {
        height: auto;
        margin-top: 1;
        color: $text-muted;
    }
    .instruction {
        height: auto;
        margin-top: 1;
        padding: 0 1;
        border: round $accent;
    }
    #region-status {
        height: 1;
        padding: 0 2;
        color: $activity;
    }
    #region-queue {
        height: auto;
        max-height: 12;
        padding: 0 2;
    }
    #region-queue .queued {
        height: auto;
        padding: 0 1;
        border: round $border-subtle;
        border-title-color: $text-muted;
        color: $text-muted;
    }
    #region-composer {
        height: 3;
    }
    /* The chat box is drawn in the wordmark blue, focused or not. */
    #region-composer Input,
    #region-composer Input:focus {
        border: tall $accent;
    }
    #region-context {
        height: 1;
        padding: 0 2;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+l", "screenshot", "Screenshot"),
        # Priority, so the composer's own focus handling never swallows it.
        Binding("shift+tab", "cycle_mode", "Mode", priority=True),
        Binding("escape", "stop_run", "Stop the run"),
    ]

    def __init__(
        self,
        repo_path: Path,
        provider: str = Provider.ANTHROPIC.value,
        gateway_url: str = DEFAULT_GATEWAY_URL,
        cost_tracker: CostTracker | None = None,
        palette: Palette | None = None,
        force_setup: bool = False,
        permission_mode: PermissionMode = PermissionMode.MANUAL,
        session_id: str | None = None,
        turns: list[SavedTurn] | None = None,
    ) -> None:
        """Builds the interface for one checkout.

        Args:
            repo_path: Checkout the agent is pointed at.
            provider: Provider answering the run's steps.
            gateway_url: Gateway the connection indicator polls.
            cost_tracker: Tracker the header's cost readout is drawn from.
            palette: Colours to render with; detected from the terminal when None.
            force_setup: Show onboarding even when a credential is already set.
            permission_mode: How much the agent may do before it asks.
            session_id: Id of a session being resumed; a new one is made when None.
            turns: Turns of the session being resumed, oldest first.
        """
        # Textual resolves CSS variables inside App.__init__, so the palette has
        # to exist before the base class is initialised.
        self.palette: Palette = palette_for() if palette is None else palette
        self.force_setup = force_setup
        super().__init__()
        self.repo_path: Path = repo_path
        self.provider: str = provider
        self.gateway_url: str = gateway_url
        self.cost_tracker = cost_tracker if cost_tracker is not None else CostTracker()
        self.breaker = CircuitBreaker()
        self.router = CommandRouter()
        self.model: str | None = None
        self.permission_mode = permission_mode
        self.active_loop: AgentLoop | None = None
        self.credential_verifier: Callable[[Provider, str], Verification] | None = None
        self.session_id = session_id or new_session_id()
        self.version = os.environ.get(VERSION_ENV, "").strip() or __version__
        self.turns: list[SavedTurn] = list(turns or [])
        self.conversation: list[LoopMessage] = [
            message for turn in self.turns for message in turn.messages()
        ]
        self.live_steps: list[SavedStep] = []
        self.stop_flag = threading.Event()
        self.save_failure_reported = False
        self.active_instruction = ""

    def get_css_variables(self) -> dict[str, str]:
        """Feeds the project palette into Textual's own design tokens.

        The palette is resolved once when the app is built, not read from the
        environment here: a test, or a CI run with no TERM, would otherwise get
        a different theme than the one it asked for.

        Returns:
            variables: Textual's defaults overlaid with the project palette.
        """
        variables = {**super().get_css_variables(), **css_variables(self.palette)}
        for token, fallback in TOKEN_FALLBACKS.items():
            variables.setdefault(token, variables[fallback])
        return variables

    def needs_setup(self) -> bool:
        """Reports whether any provider credential is still missing.

        Returns:
            needs_setup: True when the setup panel should be shown first.
        """
        if self.force_setup:
            return True
        return len(detect_missing()) == len(list(Provider))

    def is_onboarded(self) -> bool:
        """Reports whether this install has already been through onboarding.

        The installed launcher mounts a state directory that lives inside the
        install, so uninstalling removes the record and the next install
        starts from the welcome screen, even if a key is still set somewhere.
        A run with no state directory (from a checkout) goes by keys alone.

        Returns:
            is_onboarded: False only when a state directory exists without the marker.
        """
        state_dir = os.environ.get(STATE_DIR_ENV, "").strip()
        if not state_dir:
            return True
        return (Path(state_dir) / ONBOARDED_MARKER).exists()

    def mark_onboarded(self) -> None:
        """Records in the state directory that onboarding has been completed."""
        state_dir = os.environ.get(STATE_DIR_ENV, "").strip()
        if state_dir:
            with suppress(OSError):
                (Path(state_dir) / ONBOARDED_MARKER).touch()

    def compose(self) -> ComposeResult:
        """Lays out the hero, the timeline, the status line, and the composer."""
        hero = Vertical(
            Robot(id="hero-robot"),
            Wordmark(id="hero-mark"),
            id="region-hero",
        )
        yield hero

        timeline = Timeline()
        timeline.id = REGION_IDS[1]
        timeline.display = False
        yield timeline

        status = StatusLine()
        status.id = "region-status"
        status.display = False
        yield status

        yield Vertical(id="region-queue")

        composer = Composer()
        composer.id = REGION_IDS[2]
        yield composer

        context = ContextBar(self.model_label(), palette=self.palette, mode_label=self.mode_label())
        context.id = "region-context"
        yield context

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
        self.router.register("mode", self.mode_command)
        self.router.register("setup", self.open_setup)

    def on_mount(self) -> None:
        """Registers the slash commands, then opens onboarding or places the caret.

        A first run gets the whole welcome, terms included. A forced re-run is
        for changing a key, so it goes straight to provider setup and offers
        the providers already configured too.
        """
        self.register_commands()
        self.replay_conversation()
        self.query_one(Composer).focus_input()
        onboarded = self.is_onboarded()
        self.offer_update()
        first_run = not self.force_setup and (not onboarded or self.needs_setup())
        if first_run or self.needs_setup():
            offered = all_providers() if (self.force_setup or not onboarded) else None
            self.push_screen(self.onboarding(offered, show_terms=first_run))

    def offer_update(self) -> None:
        """Shows the update the launcher found, if it found one."""
        latest = os.environ.get(UPDATE_AVAILABLE_ENV, "").strip()
        if not latest or latest == self.version:
            return
        panel = UpdatePanel(latest, self.version, palette=self.palette)
        self.query_one("#region-queue").mount(panel)
        panel.focus()

    def on_update_panel_answered(self, event: UpdatePanel.Answered) -> None:
        """Takes the update and closes, or dismisses the offer.

        The update runs in the launcher once this closes, and reopens the
        session where it left off.

        Args:
            event: Which the operator chose.
        """
        event.stop()
        panel = self.query_one(UpdatePanel)
        directory = state_dir()
        if event.is_accepted and directory is not None:
            request_update(self.session_id, directory)
            self.exit()
            return
        panel.remove()
        self.query_one(Composer).focus_input()

    def onboarding(
        self, offered: list[CredentialStatus] | None, show_terms: bool
    ) -> OnboardingScreen:
        """Builds the onboarding screen for this checkout.

        Args:
            offered: Providers to list; the ones missing a key when None.
            show_terms: Whether the terms come before provider setup.

        Returns:
            screen: Screen ready to push.
        """
        return OnboardingScreen(
            self.repo_path,
            offered=offered,
            verifier=self.credential_verifier,
            show_terms=show_terms,
        )

    def close_onboarding(self) -> None:
        """Returns from onboarding to the home page with the caret in the composer."""
        if isinstance(self.screen, OnboardingScreen):
            self.pop_screen()
        self.call_after_refresh(self.query_one(Composer).focus_input)

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
            self.show_notice(routed)
            return routed
        self.start_or_queue(text)
        return text

    def start_or_queue(self, instruction: str) -> None:
        """Starts a turn, or queues the instruction when a run is already going.

        The composer queues what it sees typed while busy, but two submissions
        can both be on their way before the first turn starts, so the app makes
        the final call. Only one run ever works on the checkout at a time.

        Args:
            instruction: What the operator asked the agent to do.
        """
        composer = self.query_one(Composer)
        if composer.is_busy:
            composer.pending.append(instruction)
            self.show_queued(instruction)
            return
        self.start_turn_for(instruction)

    def show_queued(self, instruction: str) -> None:
        """Shows a queued message above the composer until its turn starts.

        Args:
            instruction: Message waiting for the current run to finish.
        """
        box = Static(Text(instruction), classes="queued")
        box.border_title = QUEUED_TITLE
        self.query_one("#region-queue").mount(box)

    def on_composer_queued(self, event: Composer.Queued) -> None:
        """Shows a message the composer queued because a run was in flight.

        Args:
            event: Message carrying the queued instruction.
        """
        event.stop()
        self.show_queued(event.instruction)

    def show_notice(self, notice: str) -> None:
        """Writes a slash command's reply into the transcript.

        Args:
            notice: Reply to show; nothing is drawn when it is empty.
        """
        if not notice:
            return
        self.query_one("#region-hero").display = False
        timeline = self.query_one(Timeline)
        timeline.display = True
        timeline.mount(Static(Text(notice), classes="notice"))
        timeline.scroll_end(animate=False)

    def start_turn_for(self, instruction: str) -> None:
        """Opens a turn for one instruction and hands it to the agent.

        Args:
            instruction: What the operator asked the agent to do.
        """
        self.enter_working_view()
        self.active_instruction = instruction
        timeline = self.query_one(Timeline)
        timeline.start_turn(instruction)
        # Text, not markup: an instruction may well contain [brackets].
        timeline.mount(Static(Text(instruction), classes="instruction"))
        status = self.query_one(StatusLine)
        status.display = True
        status.set_phase(Phase.PLANNING)
        # Busy from this moment, not from when the worker thread gets going: a
        # message sent in between would otherwise start a second run. The stop
        # flag is cleared here too, for the same reason: a stop pressed after
        # this point belongs to this run.
        self.stop_flag.clear()
        self.query_one(Composer).mark_busy()
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
            # A chat window gets greetings and questions, not only tasks.
            conversational=True,
            # Nobody is watching the steps go by, so the run checks its own work.
            verify_before_final=True,
        )
        config.breaker = self.breaker
        config.history = list(self.conversation)
        config.stop_requested = self.stop_flag.is_set
        config.tool_gate = self.tool_gate()
        config.escape_gate = self.approve_escape
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
            self.query_one(Composer)
        except NoMatches:
            # The interface was torn down while this run was starting; there is
            # nothing left to report progress to.
            return
        try:
            loop = self.build_loop(instruction)
            self.active_loop = loop
            result = loop.run(on_step=lambda step: self.call_from_thread(self.append_step, step))
            if result.final_answer:
                answer = result.final_answer
            else:
                answer = STOPPED_NOTICE if self.stop_flag.is_set() else NO_ANSWER_NOTICE
        except MissingCredentialError:
            answer = INFERENCE_NOT_CONFIGURED
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
        except MissingCredentialError:
            return INFERENCE_NOT_CONFIGURED

        self.provider = provider.value
        self.model = model
        if self.active_loop is not None:
            switch_model(self.active_loop, argument)
        self.query_one(ContextBar).set_model(self.model_label())
        return f"now using {model or DEFAULT_MODELS[provider]}"

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
        return "   ".join(names)

    @property
    def plan_mode(self) -> bool:
        """Reports whether runs propose a plan before executing.

        Returns:
            plan_mode: True while the permission mode is plan.
        """
        return self.permission_mode is PermissionMode.PLAN

    def tool_gate(self) -> ToolGate:
        """Builds the gate a run asks before each tool call.

        Returns:
            gate: Checks the mode in force at call time and asks when it must.
        """
        return gate_for(lambda: self.permission_mode, self.approve_tool)

    def approve_tool(self, tool_name: str, tool_args: dict[str, str]) -> bool | str:
        """Asks the operator about one tool call and blocks the run until answered.

        Runs on the worker thread, so the panel is mounted through the UI
        thread and the worker parks on the panel's own decision event.

        Args:
            tool_name: Tool the agent wants to call.
            tool_args: Arguments it would be called with.

        Returns:
            decision: True when approved, the operator's suggestion, or False.
        """
        panel = ApprovalPanel(tool_name, tool_args, palette=self.palette)
        self.call_from_thread(self.show_approval_panel, panel)
        return panel.wait_for_decision(PLAN_DECISION_TIMEOUT_S)

    def approve_escape(self, command: str, reason: str) -> bool:
        """Asks before a command reaches outside the working directory.

        Asked in every mode, bypass included: the directory ship was opened
        on is the boundary, and only the operator moves it.

        Args:
            command: Shell command the agent wants to run.
            reason: Which path leaves the directory, and why.

        Returns:
            is_approved: True only for an explicit approval; a suggestion declines.
        """
        return self.approve_tool(ESCAPE_TOOL, {"command": command, "reason": reason}) is True

    def show_approval_panel(self, panel: ApprovalPanel) -> None:
        """Mounts an approval panel at the end of the transcript and focuses it.

        Args:
            panel: Panel awaiting the operator's decision.
        """
        timeline = self.query_one(Timeline)
        timeline.mount(panel)
        timeline.scroll_end(animate=False)
        panel.focus()

    def on_unmount(self) -> None:
        """Releases anything still waiting on the interface as it goes away.

        A run parked on an approval, or between steps, would otherwise keep the
        process alive after the window has closed.
        """
        self.stop_flag.set()
        for panel in self.query(ApprovalPanel):
            panel.action_deny()

    def action_stop_run(self) -> None:
        """Stops the run in flight, leaving what it has already done in place."""
        self.request_stop()

    def request_stop(self) -> None:
        """Asks the run in flight to stop at its next step.

        Anything already queued behind it is dropped: stopping is for taking
        back control, not for working through the rest of the queue.
        """
        composer = self.query_one(Composer)
        if not composer.is_busy:
            return
        self.stop_flag.set()
        composer.pending.clear()
        self.query("#region-queue .queued").remove()
        self.query_one(StatusLine).set_phase(Phase.DONE)

    def on_composer_stop_requested(self, event: Composer.StopRequested) -> None:
        """Stops the run when the composer's stop control is used.

        Args:
            event: Notice that the stop control was clicked.
        """
        event.stop()
        self.request_stop()

    def on_approval_panel_decided(self, event: ApprovalPanel.Decided) -> None:
        """Hands the keyboard back to the composer once a call is answered.

        Args:
            event: Message carrying the decision.
        """
        event.stop()
        self.query_one(Composer).focus_input()

    def toggle_plan_mode(self, argument: str) -> str:
        """Turns plan-then-execute on and off for later runs.

        Args:
            argument: Ignored; the command is a toggle.

        Returns:
            line: Which mode later runs will use.
        """
        del argument
        self.set_permission_mode(PermissionMode.MANUAL if self.plan_mode else PermissionMode.PLAN)
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
        self.mark_onboarded()
        self.close_onboarding()

    def on_setup_panel_skipped(self, event: SetupPanel.Skipped) -> None:
        """Dismisses onboarding when the operator declines to enter a key.

        Args:
            event: Message reporting that setup was dismissed.
        """
        event.stop()
        self.close_onboarding()

    def remember_turn(self, instruction: str, answer: str) -> None:
        """Keeps a finished turn so later runs reason against the whole session.

        Args:
            instruction: What the operator asked for.
            answer: What the agent reported back.
        """
        if not instruction:
            return
        self.turns.append(SavedTurn(instruction, answer, list(self.live_steps)))
        self.live_steps.clear()
        self.conversation.append(LoopMessage(role="user", content=instruction))
        self.conversation.append(LoopMessage(role="assistant", content=answer))
        excess = len(self.conversation) - HISTORY_TURN_LIMIT * 2
        if excess > 0:
            del self.conversation[:excess]
        # Saved after every turn, so quitting at any point leaves it resumable.
        # A failure here is said out loud: a session silently not saved is one
        # the operator only finds out about when --resume cannot find it.
        try:
            save_session(self.session_id, self.repo_path, self.turns, sessions_dir())
        except OSError as exc:
            self.report_save_failure(exc)

    def report_save_failure(self, exc: OSError) -> None:
        """Says once that this session is not being saved, and why.

        Args:
            exc: What went wrong writing the session.
        """
        if self.save_failure_reported:
            return
        self.save_failure_reported = True
        reason = exc.strerror or str(exc)
        self.show_notice(SAVE_FAILED_TEMPLATE.format(path=sessions_dir(), reason=reason))

    def replay_conversation(self) -> None:
        """Redraws a resumed session exactly as it was left.

        Each turn comes back whole: the message, the activity cards with their
        input, diff and output, and the answer that closed it.
        """
        if not self.turns:
            return
        self.query_one("#region-hero").display = False
        timeline = self.query_one(Timeline)
        timeline.display = True
        for turn in self.turns:
            timeline.mount(Static(Text(turn.instruction), classes="instruction"))
            timeline.start_turn(turn.instruction)
            for step in turn.steps:
                row = StepRow(
                    step.tool_name,
                    step.tool_args,
                    step.observation,
                    palette=self.palette,
                    diff=step.diff,
                )
                timeline.record_step(row)
                timeline.mount(row)
            timeline.finish_turn(turn.answer)
            timeline.mount(Static(Text(f"{ANSWER_PREFIX}{turn.answer}")))
        timeline.scroll_end(animate=False)

    def open_setup(self, argument: str) -> str:
        """Re-runs onboarding so a key or provider can be changed.

        The key lives in the checkout's .env, not in the install, so
        reinstalling never brings onboarding back by itself.

        Args:
            argument: Ignored; the command takes none.

        Returns:
            line: Empty once setup is open, since it takes over the screen.
        """
        del argument
        if isinstance(self.screen, OnboardingScreen):
            return SETUP_ALREADY_OPEN
        self.push_screen(self.onboarding(all_providers(), show_terms=False))
        return ""

    def mode_label(self) -> str:
        """Renders the permission mode as the bar under the composer shows it.

        Returns:
            label: A marker and the mode's name.
        """
        return f"{MODE_MARKERS[self.permission_mode]} {self.permission_mode.value}"

    def set_permission_mode(self, mode: PermissionMode) -> None:
        """Switches the permission mode and shows it under the composer.

        A run in flight picks the new mode up at its next tool call.

        Args:
            mode: Mode to switch to.
        """
        self.permission_mode = mode
        self.query_one(ContextBar).set_mode(self.mode_label())

    def mode_command(self, argument: str) -> str:
        """Lists the permission modes, or switches to the one named.

        Args:
            argument: Mode name or alias; empty to list the modes.

        Returns:
            line: The modes with the active one marked, the new mode, or usage.
        """
        if not argument.strip():
            return "\n".join(
                f"{'*' if mode is self.permission_mode else ' '} {mode.value:<20} "
                f"{MODE_DESCRIPTIONS[mode]}"
                for mode in MODE_ORDER
            )
        mode = parse_mode(argument)
        if mode is None:
            return USAGE_MODE
        self.set_permission_mode(mode)
        return f"{mode.value}: {MODE_DESCRIPTIONS[mode]}"

    def action_cycle_mode(self) -> None:
        """Moves to the next permission mode, as shift+tab does in the composer."""
        self.set_permission_mode(next_mode(self.permission_mode))

    def model_label(self) -> str:
        """Renders the model currently answering.

        Returns:
            label: The model, as the bar under the composer shows it.
        """
        return self.model or DEFAULT_MODELS[Provider(self.provider)]

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
        row = StepRow(
            step.tool_name,
            step.tool_args,
            step.observation,
            palette=self.palette,
            diff=step.diff,
        )
        timeline.record_step(row)
        timeline.mount(row)
        self.live_steps.append(
            SavedStep(step.tool_name, dict(step.tool_args), step.observation, step.diff)
        )
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
        # Text, not markup: a summary may hold brackets, and it may run to
        # several lines.
        timeline.mount(Static(Text(f"{ANSWER_PREFIX}{answer}")))
        timeline.scroll_end(animate=False)
        self.query_one(StatusLine).stop()
        self.refresh_context_bar()
        composer = self.query_one(Composer)
        composer.mark_idle()
        queued = composer.take_next()
        if queued is not None:
            boxes = self.query("#region-queue .queued")
            if boxes:
                boxes.first().remove()
            self.start_turn_for(queued)

    def on_composer_submitted(self, event: Composer.Submitted) -> None:
        """Routes a line the composer submitted.

        Args:
            event: Message carrying the submitted instruction.
        """
        self.handle_line(event.instruction)
