#!/usr/bin/env python3
"""
step_row.py --- one Read/Edited/Ran activity row, collapsed or expanded

Contains:
    COLLAPSED_MARKER / EXPANDED_MARKER: the disclosure glyphs
    TARGET_ARGS: tool arguments that name what a step acted on
    step_target(): picks the argument naming what a step acted on
    StepRow: one activity row that opens to reveal its output
    StepRow.summary_line(): renders the collapsed one-line summary
    StepRow.detail_lines(): renders the output revealed when expanded
    StepRow.action_toggle(): opens or closes the row
"""

from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import Static

from tui.labels import label_for

COLLAPSED_MARKER = "▸"
EXPANDED_MARKER = "▾"
TARGET_ARGS = ("path", "command", "selector")


def step_target(tool_args: dict[str, str]) -> str:
    """Picks the argument that names what a step acted on.

    Args:
        tool_args: Arguments the step was dispatched with.

    Returns:
        target: First recognized target argument, or an empty string.
    """
    for name in TARGET_ARGS:
        value = tool_args.get(name, "")
        if value:
            return value
    return ""


class StepRow(Static):
    """Renders one activity row that opens to reveal that step's output.

    Attributes:
        tool_name: Tool the agent dispatched for this step.
        tool_args: Arguments the step was dispatched with.
        observation: Output the tool returned.
        is_expanded: True while the row is showing its output.
    """

    BINDINGS = [Binding("enter", "toggle", "Expand step")]

    is_expanded: reactive[bool] = reactive(False)

    def __init__(self, tool_name: str, tool_args: dict[str, str], observation: str) -> None:
        """Builds one activity row from a completed step.

        Args:
            tool_name: Tool the agent dispatched for this step.
            tool_args: Arguments the step was dispatched with.
            observation: Output the tool returned.
        """
        super().__init__()
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.observation = observation

    def summary_line(self) -> str:
        """Renders the collapsed one-line summary of the step.

        Returns:
            line: Disclosure marker, activity label, and what it acted on.
        """
        marker = EXPANDED_MARKER if self.is_expanded else COLLAPSED_MARKER
        target = step_target(self.tool_args)
        label = label_for(self.tool_name)
        return f"{marker} {label} {target}".rstrip()

    def detail_lines(self) -> list[str]:
        """Renders the output revealed when the row is expanded.

        Returns:
            lines: Observation split into lines, empty while collapsed.
        """
        if not self.is_expanded or not self.observation:
            return []
        return self.observation.splitlines()

    def action_toggle(self) -> None:
        """Opens the row when it is closed, and closes it when it is open."""
        self.is_expanded = not self.is_expanded
