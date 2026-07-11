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
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from agent.cost_tracker import CostTracker
from agent.llm_client import Completion, LLMClient, Message
from agent.tool_dispatcher import ToolDispatcher

logger = logging.getLogger(__name__)

MAX_TOOL_OUTPUT_CHARS = 6000
STEP_BUDGET_TOKENS = 6000
FINAL_ANSWER_PREFIX = "FINAL:"

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
        self._cost_usd = 0.0
        self._dispatcher = ToolDispatcher(Path(config.repo_path))
        logger.debug("agent loop initialised for %s", config.repo_path)

    def run(self) -> RunResult:
        """Executes the loop until the model produces a final answer.

        Returns:
            result: Finished run with its final answer and full transcript.
        """
        while True:
            step = self._think()
            self._transcript.append(step)
            if not step.tool_name:
                return RunResult(
                    final_answer=self._extract_final(step),
                    steps=self._transcript,
                    total_cost_usd=self._cost_usd,
                )
            output = self._act(step)
            self._observe(step, output)

    def _think(self) -> Step:
        """Asks the model for the next thought and action.

        Returns:
            step: Parsed step, with an empty tool name when the model is done.
        """
        messages = self._build_messages()
        completion = self._client.complete(messages, self.config.system_prompt, STEP_BUDGET_TOKENS)
        self._record_cost(completion)
        logger.debug("thought %d received", len(self._transcript))
        return self._parse_step(completion.text)

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
