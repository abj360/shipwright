#!/usr/bin/env python3
"""
composer.py --- live instruction input that queues while a run is in flight

Contains:
    QUEUED_NOTICE / SENT_NOTICE: what the composer reports back on submit
    IDLE_PROMPT / BUSY_PROMPT: placeholder text per run state
    Composer: input that sends when idle and queues while a run is running
    Composer.prompt_text(): the placeholder matching the current run state
    Composer.compose(): builds the input line
    Composer.submit(): sends or queues one typed instruction
    Composer.take_next(): pops the next queued instruction
    Composer.mark_busy(): records that a run has started
    Composer.mark_idle(): records that the run finished
    Composer.Submitted: carries an instruction that is ready to run
"""

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Input, Static

from agent.repo_map import RepoMap

INPUT_ID = "composer-input"
QUEUED_NOTICE = "queued"
SENT_NOTICE = "sent"
IDLE_PROMPT = "what should the agent do?"
BUSY_PROMPT = "run in flight — this will queue"


class Composer(Static):
    """Accepts instructions, sending them when idle and queueing them when not.

    Attributes:
        repo_map: Outline cache consulted before an instruction is handed on.
        is_busy: True while a run is in flight.
        pending: Instructions typed while the run was busy, oldest first.
    """

    class Submitted(Message):
        """Carries one instruction that is ready to be run.

        Attributes:
            instruction: Text the operator submitted.
        """

        def __init__(self, instruction: str) -> None:
            """Records the instruction being sent.

            Args:
                instruction: Text the operator submitted.
            """
            super().__init__()
            self.instruction = instruction

    def __init__(self, repo_map: RepoMap | None = None) -> None:
        """Builds the composer, optionally sharing an outline cache.

        Args:
            repo_map: Outline cache to refresh before handing on an instruction.
        """
        super().__init__()
        self.repo_map = repo_map
        self.is_busy = False
        self.pending: list[str] = []

    def prompt_text(self) -> str:
        """Returns the placeholder matching the current run state.

        Returns:
            prompt: Placeholder telling the operator whether input will queue.
        """
        return BUSY_PROMPT if self.is_busy else IDLE_PROMPT

    def compose(self) -> ComposeResult:
        """Builds the single-line instruction input."""
        yield Input(placeholder=self.prompt_text(), id=INPUT_ID)

    def mark_busy(self) -> None:
        """Records that a run has started, so later input is queued."""
        self.is_busy = True

    def mark_idle(self) -> None:
        """Records that the run finished, so the next instruction sends directly."""
        self.is_busy = False

    def submit(self, text: str) -> str:
        """Sends the instruction, or queues it when a run is already in flight.

        Args:
            text: Raw text the operator typed.

        Returns:
            notice: Whether the instruction was sent or queued; empty when blank.
        """
        instruction = text.strip()
        if not instruction:
            return ""
        self._refresh_outlines()
        if self.is_busy:
            self.pending.append(instruction)
            return QUEUED_NOTICE
        self.post_message(self.Submitted(instruction))
        return SENT_NOTICE

    def take_next(self) -> str | None:
        """Pops the next queued instruction, oldest first.

        Returns:
            instruction: Next queued instruction, or None when the queue is empty.
        """
        if not self.pending:
            return None
        return self.pending.pop(0)

    def _refresh_outlines(self) -> None:
        """Drops outline cache entries for files that changed on disk."""
        if self.repo_map is None:
            return
        self.repo_map.refresh(self.repo_map.detect_changes())
