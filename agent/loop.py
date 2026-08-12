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
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from agent.circuit_breaker import CircuitBreaker, RunawayRunError
from agent.cost_tracker import CostTracker
from agent.llm_client import Completion, LLMClient, Message
from agent.planner import Plan, RepoPlanner
from agent.tool_dispatcher import ToolDispatcher

logger = logging.getLogger(__name__)

MAX_TOOL_OUTPUT_CHARS = 6000
TRANSCRIPT_TOKEN_BUDGET = 28000
CHARS_PER_TOKEN_ESTIMATE = 4
STEP_BUDGET_TOKENS = 6000
FINAL_ANSWER_PREFIX = "FINAL:"
TOOL_USAGE_INSTRUCTIONS = (
    "Think step by step. Reply with your reasoning, then either one tool call as "
    "'Action: <name>' followed by 'key=value; ...' arguments, or 'FINAL: <answer>'."
)
TRUNCATED_OBSERVATION_NOTE = "[older observation trimmed to fit the context budget]"
PARSE_RETRY_HINT = (
    "Your last reply had no Action: and no FINAL:. "
    "Respond with exactly one Action: or one FINAL: and nothing else."
)

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
    """

    final_answer: str | None
    steps: list[Step] = field(default_factory=list)
    total_cost_usd: float = 0.0
    started_at: float = 0.0
    ended_at: float = 0.0

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

    def run(self) -> RunResult:
        """Executes the loop until the model produces a final answer.

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

    def _think(self) -> Step:
        """Asks the model for the next thought and action.

        Returns:
            step: Parsed step, with an empty tool name when the model is done.
        """
        self._trim_transcript()
        messages = self._build_messages()
        completion = self._client.complete(messages, self._build_system_prompt(), STEP_BUDGET_TOKENS)
        self._record_cost(completion)
        step = self._parse_step(completion.text)
        if not step.tool_name and FINAL_ANSWER_PREFIX not in completion.text:
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
        if FINAL_ANSWER_PREFIX in text:
            return Step(index=index, thought=text)
        thought, _, rest = text.partition("Action:")
        tool_name, _, arg_text = rest.partition("\n")
        args = dict(pair.split("=", 1) for pair in arg_text.strip().split(";") if "=" in pair)
        return Step(
            index=index, thought=thought.strip(), tool_name=tool_name.strip(), tool_args=args
        )

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

    def _observe(self, step: Step, output: str) -> None:  # mutates step in place
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
        _, _, answer = step.thought.partition(FINAL_ANSWER_PREFIX)
        return answer.strip()

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
        return RunResult(final_answer=self._extract_final(final), steps=self._transcript)

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
        return f"{base}\n\n{TOOL_USAGE_INSTRUCTIONS}"
