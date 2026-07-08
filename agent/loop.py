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
    AgentLoop._tool_read_file(): reads one file from the checkout
"""

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from agent.llm_client import LLMClient, Message

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
        self._tools: dict[str, Callable[[dict[str, str]], str]] = {
            "read_file": self._tool_read_file,
            "list_dir": self._tool_list_dir,
            "run_shell": self._tool_run_shell,
        }
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
                return RunResult(final_answer=self._extract_final(step), steps=self._transcript)
            output = self._act(step)
            self._observe(step, output)

    def _think(self) -> Step:
        """Asks the model for the next thought and action.

        Returns:
            step: Parsed step, with an empty tool name when the model is done.
        """
        messages = self._build_messages()
        completion = self._client.complete(messages, self.config.system_prompt, STEP_BUDGET_TOKENS)
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
        tool = self._tools.get(step.tool_name)
        if tool is None:
            return f"error: unknown tool {step.tool_name!r}"
        try:
            output = tool(step.tool_args)
        except (OSError, subprocess.SubprocessError) as exc:
            return f"error: {exc}"
        return output[:MAX_TOOL_OUTPUT_CHARS]

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

    def _tool_read_file(self, args: dict[str, str]) -> str:
        """Reads one file from the checkout.

        Args:
            args: Tool arguments; expects a "path" entry.

        Returns:
            content: File text, or an error string when unreadable.
        """
        target = Path(self.config.repo_path, args["path"])
        return target.read_text(errors="replace")

    def _tool_list_dir(self, args: dict[str, str]) -> str:
        """Lists one directory of the checkout.

        Args:
            args: Tool arguments; expects a "path" entry.

        Returns:
            listing: Newline-separated entry names.
        """
        target = Path(self.config.repo_path, args.get("path", "."))
        return "\n".join(sorted(child.name for child in target.iterdir()))

    def _tool_run_shell(self, args: dict[str, str]) -> str:
        """Runs a shell command inside the checkout.

        Args:
            args: Tool arguments; expects a "command" entry.

        Returns:
            output: Combined stdout and stderr of the command.
        """
        proc = subprocess.run(
            args["command"],
            shell=True,
            cwd=self.config.repo_path,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return proc.stdout + proc.stderr
