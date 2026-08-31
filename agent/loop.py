#!/usr/bin/env python3
"""
loop.py --- ReAct-style agent loop that thinks, acts, and observes

Contains:
    Step: one think-act-observe iteration of the loop
    RunResult: summarizes a finished agent run
    AgentConfig: static per-run configuration
    AgentLoop: drives the think-act-observe loop
    AgentLoop.run(): executes the loop until a final answer
    AgentLoop._think(): asks the model for the next step
    AgentLoop._parse_step(): splits model output into a step
    AgentLoop._act(): runs the chosen tool and captures output
    AgentLoop._record_cost(): accumulates one completion's spend
    AgentLoop._run_plan_mode(): executes planner steps directly
    AgentLoop.transcript(): read-only view of steps taken
    AgentLoop._trim_transcript(): drops oldest observations over budget
    AgentLoop._build_system_prompt(): composes the steering prompt
    AgentLoop.resume(): seeds steps from an interrupted run
"""

import logging
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from agent.circuit_breaker import CircuitBreaker
from agent.cost_tracker import CostTracker
from agent.llm_client import Completion, LLMClient, Message
from agent.planner import RepoPlanner
from agent.tool_dispatcher import ToolDispatcher

logger = logging.getLogger(__name__)

MAX_TOOL_OUTPUT_CHARS = 6000
TRANSCRIPT_TOKEN_BUDGET = 28000
CHARS_PER_TOKEN_ESTIMATE = 4
STEP_BUDGET_TOKENS = 6000
FINAL_ANSWER_PREFIX = "FINAL:"
ACTION_PREFIX = "Action:"
# Models wrap the markers in markdown ("**Action:**", "### FINAL:") and vary the
# case, so the markers are matched through the decoration rather than literally.
_MARKER_DECORATION = r"[ \t>*_`#-]*"
_MARKER_TRAILER = r"[ \t]*[*_`]*[ \t]*"
ACTION_PATTERN = re.compile(_MARKER_DECORATION + r"action[ \t]*:" + _MARKER_TRAILER, re.IGNORECASE)
FINAL_PATTERN = re.compile(_MARKER_DECORATION + r"final[ \t]*:" + _MARKER_TRAILER, re.IGNORECASE)
MARKUP_CHARS = "*_` "
TOOL_NAME_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")
# Arguments whose value may run past the end of the line.
MULTILINE_ARGS = frozenset({"content", "patch"})
TOOL_USAGE_INSTRUCTIONS = (
    "Work in small steps. Each reply is your reasoning followed by EITHER one "
    "tool call OR a final answer, never both.\n\n"
    "To call a tool, end your reply with the tool name on an Action line and "
    "its arguments on the next line, separated by semicolons:\n\n"
    "Action: read_file\n"
    "path=calc.py\n\n"
    "Action: write_file\n"
    "path=calc.py; content=def add(a, b):\n"
    "    return a + b\n\n"
    "Reading a file does not change it. Every edit must go through write_file "
    "or apply_patch, and write_file replaces the whole file, so include the "
    "complete new contents.\n\n"
    "Never answer FINAL before you have used a tool: inspect the checkout "
    "first, make the change, then finish with\n\n"
    "FINAL: <one sentence describing the change you made>\n\n"
    "Only the tool names listed above exist; anything else is rejected."
)
TRUNCATED_OBSERVATION_NOTE = "[older observation trimmed to fit the context budget]"
PARSE_RETRY_HINT = (
    "Your last reply had no Action: and no FINAL:. "
    "Respond with exactly one Action: or one FINAL: and nothing else."
)


def _name_from_next_line(text: str) -> tuple[str, str]:
    """Recovers a tool name that the model put below its Action marker.

    Only a bare identifier is accepted, so a code fence or a sentence is left
    alone rather than being dispatched as a tool.

    Args:
        text: Everything following the Action line.

    Returns:
        name: Tool name, empty when the next line does not hold one.
        remainder: The text left to parse as arguments.
    """
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "":
            continue
        if stripped.startswith("```"):
            return "", text
        candidate = stripped.strip(MARKUP_CHARS)
        if TOOL_NAME_PATTERN.match(candidate) is None:
            return "", text
        return candidate, "\n".join(lines[index + 1 :])
    return "", text


@dataclass
class Step:
    """Records one think-act-observe iteration of the agent loop.

    Attributes:
        index: Zero-based position of the step in the run.
        thought: Reasoning text the model produced for this step.
        tool_name: Name of the tool the model chose, empty when the run ended.
        tool_args: Arguments passed to the tool.
        observation: Output the tool returned, possibly truncated.
    """

    index: int
    thought: str
    tool_name: str = ""
    tool_args: dict[str, str] = field(default_factory=dict)
    observation: str = ""


@dataclass
class RunResult:
    """Summarizes a finished agent run.

    Attributes:
        final_answer: Answer the agent produced, or None when it stopped early.
        steps: Ordered steps taken during the run.
        started_at: Epoch seconds when the run started.
        ended_at: Epoch seconds when the run stopped.
        total_cost_usd: Model spend accumulated over the run.
    """

    final_answer: str | None
    steps: list[Step] = field(default_factory=list)
    total_cost_usd: float = 0.0
    started_at: float = 0.0
    ended_at: float = 0.0

    def summary(self) -> str:
        """Builds a one-line human-readable summary of the run.

        Returns:
            summary: Step count, duration, and cost in one line.
        """
        return f"{len(self.steps)} steps in {self.duration_s:.1f}s, cost ${self.total_cost_usd:.4f}"

    @property
    def duration_s(self) -> float:
        """Computes wall-clock seconds the run took.

        Returns:
            duration_s: Elapsed seconds between run start and end.
        """
        return self.ended_at - self.started_at


@dataclass
class AgentConfig:
    """Bundles what a run needs beyond the task text itself.

    Attributes:
        repo_path: Checkout the agent is allowed to inspect and modify.
        task: Natural-language description of what to accomplish.
        system_prompt: Steering prompt prepended to every completion.
        mode: Execution mode: "react" for free-form, "plan_execute" for planned runs.
        planner: Planner used when mode is "plan_execute".
        breaker: Iteration and spend ceilings that halt a runaway run.
        cost_tracker: Optional tracker accumulating the run's model spend.
    """

    repo_path: str
    task: str
    system_prompt: str = ""
    mode: str = "react"
    planner: RepoPlanner | None = None
    breaker: CircuitBreaker = field(default_factory=CircuitBreaker)
    cost_tracker: CostTracker | None = None


class AgentLoop:
    """Drives a ReAct-style loop of thought, tool action, and observation.

    Attributes:
        config: Static configuration for the current run.
    """

    def __init__(self, client: LLMClient, config: AgentConfig) -> None:
        """Wires the loop to its model client and run configuration.

        Args:
            client: Completion backend the loop thinks with.
            config: Static configuration for the current run.
        """
        self.config = config
        self._client = client
        self._transcript: list[Step] = []
        self._run_id = uuid.uuid4().hex[:8]
        self._cost_usd = 0.0
        self._dispatcher = ToolDispatcher(Path(config.repo_path))
        logger.debug("agent loop initialised for %s", config.repo_path)

    def run(self, on_step: Callable[[Step], None] | None = None) -> RunResult:
        """Executes the loop until the model produces a final answer.

        Args:
            on_step: Optional callback invoked after each observed step.

        Returns:
            result: Finished run with its final answer and full transcript.
        """
        if self.config.mode == "plan_execute":
            return self._run_plan_mode()
        started = time.time()
        logger.info("run %s started: %s", self._run_id, self.config.task[:80])
        while True:
            self.config.breaker.check(len(self._transcript), self._cost_usd)
            step = self._think()
            self._transcript.append(step)
            if not step.tool_name:
                ended = time.time()
                logger.info("run %s finished after %d steps", self._run_id, len(self._transcript))
                return RunResult(
                    final_answer=self._extract_final(step),
                    steps=self._transcript,
                    started_at=started,
                    ended_at=ended,
                    total_cost_usd=self._cost_usd,
                )
            output = self._act(step)
            self._observe(step, output)
            logger.info("run %s step %d tool=%s", self._run_id, step.index, step.tool_name)
            if on_step is not None:
                on_step(step)

    def _think(self) -> Step:
        """Asks the model for the next thought and action.

        Returns:
            step: Parsed step, with an empty tool name when the model is done.
        """
        self._trim_transcript()
        messages = self._build_messages()
        completion = self._client.complete(
            messages, self._build_system_prompt(), STEP_BUDGET_TOKENS
        )
        self._record_cost(completion)
        step = self._parse_step(completion.text)
        if not step.tool_name and FINAL_PATTERN.search(completion.text) is None:
            messages.append(Message(role="user", content=PARSE_RETRY_HINT))
            completion = self._client.complete(
                messages, self._build_system_prompt(), STEP_BUDGET_TOKENS
            )
            self._record_cost(completion)
            step = self._parse_step(completion.text)
        logger.debug("thought %d received", len(self._transcript))
        return step

    def _build_messages(self) -> list[Message]:
        """Flattens the transcript into chat messages for the next completion.

        Returns:
            messages: Conversation history starting with the task itself.
        """
        messages = [Message(role="user", content=self.config.task)]
        for step in self._transcript:
            messages.append(Message(role="assistant", content=step.thought))
            if step.observation:
                messages.append(Message(role="user", content=f"Observation: {step.observation}"))
        return messages

    def _parse_step(self, text: str) -> Step:
        """Splits raw model output into thought, tool call, or final answer.

        Args:
            text: Raw completion text to parse.

        Returns:
            step: Parsed step; an empty tool name marks a final answer.
        """
        index = len(self._transcript)
        cleaned = text.replace("<think>", "").replace("</think>", "").strip()
        action = ACTION_PATTERN.search(cleaned)
        final = FINAL_PATTERN.search(cleaned)
        # A reply carrying both markers has not seen the tool result yet, so the
        # answer is premature: run the action and let the next turn conclude.
        if action is None or (final is not None and final.start() < action.start()):
            return Step(index=index, thought=cleaned)
        thought = cleaned[: action.start()]
        head, _, following = cleaned[action.end() :].partition("\n")
        # Models routinely put the arguments on the Action line itself, so the
        # tool name is the first token and everything after it is arguments.
        first_token, separator, inline = head.strip().partition(" ")
        tool_name = first_token.strip().strip(";").strip(MARKUP_CHARS)
        arg_text = f"{inline}\n{following}" if separator else following
        if not tool_name:
            # "**Action:**" alone on its line puts the name on the next one.
            tool_name, arg_text = _name_from_next_line(following)
        args: dict[str, str] = {}
        # Only the first action in a reply is executed, so arguments stop at the
        # next marker rather than swallowing a second call into a value.
        arg_lines: list[str] = []
        for line in arg_text.splitlines():
            if ACTION_PATTERN.match(line) or FINAL_PATTERN.match(line):
                break
            arg_lines.append(line)
        pending = ""
        for line in arg_lines:
            if pending:
                args[pending] += f"\n{line}"
                continue
            for pair in line.split(";"):
                key, sep, value = pair.partition("=")
                name = key.strip()
                # Prose the model added after its arguments has spaces in the
                # "key", which no real argument name does.
                if not sep or not name or " " in name:
                    continue
                args[name] = value.strip()
                if name in MULTILINE_ARGS:
                    pending = name
        return Step(index=index, thought=thought.strip(), tool_name=tool_name, tool_args=args)

    def _act(self, step: Step) -> str:
        """Runs the tool the model asked for and captures its output.

        Args:
            step: Step carrying the chosen tool name and arguments.

        Returns:
            output: Tool output, truncated to the per-step budget.
        """
        result = self._dispatcher.dispatch(step.tool_name, step.tool_args)
        if not result.ok:
            return f"error: {result.error}"
        return result.output[:MAX_TOOL_OUTPUT_CHARS]

    def _observe(self, step: Step, output: str) -> None:
        """Attaches a tool result to its step so the model sees it next turn.

        Args:
            step: Step that produced the output.
            output: Text the tool returned.
        """
        step.observation = output

    def _extract_final(self, step: Step) -> str:
        """Strips the final-answer marker from a closing step.

        Args:
            step: Closing step whose thought holds the answer.

        Returns:
            answer: Answer text without the marker prefix.
        """
        match = FINAL_PATTERN.search(step.thought)
        answer = step.thought[match.end() :].strip() if match else ""
        if not answer:
            return step.thought.strip()
        return answer

    def _record_cost(self, completion: Completion) -> None:
        """Accumulates one completion's spend into the run total.

        Args:
            completion: Model response carrying token usage.
        """
        if self.config.cost_tracker is None:
            return
        self._cost_usd = self.config.cost_tracker.record(
            completion.model, completion.input_tokens, completion.output_tokens
        )

    def _run_plan_mode(self) -> RunResult:
        """Executes the planner's steps directly instead of free-form ReAct.

        Returns:
            result: Finished run after the last plan step.
        """
        if self.config.planner is None:
            logger.warning("plan_execute mode without a planner; falling back to react")
            self.config.mode = "react"
            return self.run()
        started = time.time()
        plan = self.config.planner.build_plan(self.config.task)
        if not plan.steps:
            logger.warning("planner returned no steps; falling back to react")
            self.config.mode = "react"
            return self.run()
        logger.info("run %s executing plan of %d steps", self._run_id, len(plan.steps))
        for plan_step in plan.steps:
            step = Step(
                index=len(self._transcript),
                thought=f"[plan {plan_step.index + 1}/{len(plan.steps)}] {plan_step.description}",
            )
            self._transcript.append(step)
            output = self._act(step)
            self._observe(step, output)
            plan_step.status = "done" if not output.startswith("error:") else "failed"
        final = Step(index=len(self._transcript), thought=f"{FINAL_ANSWER_PREFIX} plan complete")
        self._transcript.append(final)
        return RunResult(
            final_answer=self._extract_final(final),
            steps=self._transcript,
            started_at=started,
            ended_at=time.time(),
            total_cost_usd=self._cost_usd,
        )

    @property
    def transcript(self) -> list[Step]:
        """Exposes a read-only view of the steps taken so far.

        Returns:
            steps: Copy of the current transcript.
        """
        return list(self._transcript)

    def _trim_transcript(self) -> None:
        """Drops oldest observations once the transcript outgrows its token budget.

        Keeps the task message and every thought; only observations are truncated,
        oldest first, because they are the bulkiest and least reusable context.
        """
        budget_chars = TRANSCRIPT_TOKEN_BUDGET * CHARS_PER_TOKEN_ESTIMATE
        total = sum(len(s.thought) + len(s.observation) for s in self._transcript)
        for step in self._transcript:
            if total <= budget_chars:
                return
            total -= len(step.observation) - len(TRUNCATED_OBSERVATION_NOTE)
            step.observation = TRUNCATED_OBSERVATION_NOTE

    def _build_system_prompt(self) -> str:
        """Composes the system prompt from config plus tool usage instructions.

        Returns:
            prompt: System prompt sent with every completion.
        """
        base = self.config.system_prompt or "You are an autonomous coding agent."
        tools = self._dispatcher.describe_tools()
        return f"{base}\n\nAvailable tools:\n{tools}\n\n{TOOL_USAGE_INSTRUCTIONS}"

    def resume(self, prior: list[Step]) -> None:
        """Seeds the transcript with steps from an earlier, interrupted run.

        Args:
            prior: Steps to replay into context before thinking again.
        """
        self._transcript.extend(prior)
        logger.info("run %s resumed with %d prior steps", self._run_id, len(prior))
