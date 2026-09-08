#!/usr/bin/env python3
"""
step_row.py --- one Read/Edited/Ran activity row, collapsed or expanded

Contains:
    COLLAPSED_MARKER / EXPANDED_MARKER: the disclosure glyphs
    WARNING_PREFIX: marker put in front of a failed step's summary
    PREVIEW_LINES: how much of a long observation is shown before the toggle
    MORE_OUTPUT_TEMPLATE: the hint offering the rest of a long observation
    TARGET_ARGS: tool arguments that name what a step acted on
    step_target(): picks the argument naming what a step acted on
    shorten_target(): trims a target through the CLI's own truncation helper
    StepRow: one activity row that opens to reveal its output
    StepRow.has_failed(): whether the step reported an error
    StepRow.summary_line(): renders the collapsed one-line summary
    StepRow.input_line(): renders the arguments the step was dispatched with
    StepRow.highlight_color(): the colour a failed row is drawn in
    StepRow.detail_lines(): renders the output revealed when expanded
    StepRow.observation_lines(): the observation split into lines
    StepRow.is_truncated(): whether the observation is longer than the preview
    StepRow.action_show_full_output(): reveals the rest of a long observation
    DETAIL_INDENT: how far a revealed output line is indented
    NODE_MARKER / CHAIN_MARKER: the reasoning chain drawn down the gutter
    StepRow.render(): draws the summary and any revealed output
    StepRow.action_toggle_step(): opens or closes the row
    StepRow.watch_is_expanded(): redraws only this row when it opens
"""

from rich.text import Text
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import Static

from agent.cli import _shorten
from agent.loop import TOOL_ERROR_PREFIX
from tui.labels import label_for
from tui.theme import Palette, palette_for

PREVIEW_LINES = 12
MORE_OUTPUT_TEMPLATE = "… show full output ({remaining} more lines)"
DETAIL_INDENT = "    "
WARNING_PREFIX = "!"
INPUT_MARKER = "in "
OUTPUT_MARKER = "out"
# The reasoning chain: a node per entry, a rule joining them down the gutter.
NODE_MARKER = "●"
CHAIN_MARKER = "│"
COLLAPSED_MARKER = "▸"
EXPANDED_MARKER = "▾"
# The arguments that name a step's subject, in the order they are preferred.
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


def shorten_target(target: str) -> str:
    """Trims a target for display using the CLI's own truncation helper.

    The terminal and the headless CLI therefore elide long arguments
    identically, instead of each having its own idea of "too long".

    Args:
        target: Argument value naming what the step acted on.

    Returns:
        text: The value, truncated the same way the CLI truncates it.
    """
    return _shorten(target)


class StepRow(Static):
    """Renders one activity row that opens to reveal that step's output.

    Attributes:
        tool_name: Tool the agent dispatched for this step.
        tool_args: Arguments the step was dispatched with.
        observation: Output the tool returned.
        is_expanded: True while the row is showing its output.
    """

    BINDINGS = [
        Binding("enter", "toggle_step", "Expand step"),
        Binding("o", "show_full_output", "Full output"),
    ]

    is_expanded: reactive[bool] = reactive(True)
    shows_full_output: reactive[bool] = reactive(False)

    def __init__(
        self,
        tool_name: str,
        tool_args: dict[str, str],
        observation: str,
        palette: Palette | None = None,
    ) -> None:
        """Builds one activity row from a completed step.

        Args:
            tool_name: Tool the agent dispatched for this step.
            tool_args: Arguments the step was dispatched with.
            observation: Output the tool returned.
            palette: Colours to draw from; detected from the terminal when None.
        """
        super().__init__()
        self.palette: Palette = palette_for() if palette is None else palette
        self.tool_name: str = tool_name
        self.tool_args: dict[str, str] = tool_args
        self.observation: str = observation

    def has_failed(self) -> bool:
        """Reports whether this step's tool returned an error.

        The same prefix the agent loop writes is used, so a step reads as failed
        in the terminal exactly when the loop treated it as failed.

        Returns:
            has_failed: True when the observation is an error.
        """
        return self.observation.startswith(TOOL_ERROR_PREFIX)

    def summary_line(self) -> str:
        """Renders the collapsed one-line summary of the step.

        A failed step is prefixed so it stands out even where colour is
        unavailable, rather than relying on red alone to carry the meaning.

        Returns:
            line: Disclosure marker, activity label, and what it acted on.
        """
        marker = EXPANDED_MARKER if self.is_expanded else COLLAPSED_MARKER
        target = shorten_target(step_target(self.tool_args))
        label = label_for(self.tool_name)
        prefix = f"{WARNING_PREFIX} " if self.has_failed() else ""
        return f"{marker} {prefix}{label} {target}".rstrip()

    def highlight_color(self) -> str:
        """Returns the colour this row is drawn in.

        Returns:
            color: The error colour for a failed step, otherwise the default text colour.
        """
        if self.has_failed():
            return self.palette.status_error
        return self.palette.foreground

    def observation_lines(self) -> list[str]:
        """Splits the observation into lines.

        Returns:
            lines: Observation lines, empty when there was no output.
        """
        return self.observation.splitlines()

    def is_truncated(self) -> bool:
        """Reports whether the observation is longer than the preview shows.

        Returns:
            is_truncated: True when output is being held back behind the toggle.
        """
        return len(self.observation_lines()) > PREVIEW_LINES

    def input_line(self) -> str:
        """Renders the arguments the step was dispatched with.

        Returns:
            line: The primary argument in full, empty when the tool took none.
        """
        target = step_target(self.tool_args)
        return f"{INPUT_MARKER} {target}" if target else ""

    def detail_lines(self) -> list[str]:
        """Renders the output revealed when the row is expanded.

        A long observation is previewed rather than dumped, so one noisy test
        run cannot push the rest of the timeline off screen.

        Returns:
            lines: Observation lines, plus a hint when output is held back.
        """
        if not self.is_expanded or not self.observation:
            return []
        lines = self.observation_lines()
        if self.shows_full_output or not self.is_truncated():
            return lines
        remaining: int = len(lines) - PREVIEW_LINES
        hint = MORE_OUTPUT_TEMPLATE.format(remaining=remaining)
        return [*lines[:PREVIEW_LINES], hint]

    def action_show_full_output(self) -> None:
        """Reveals the rest of a long observation."""
        self.shows_full_output = True

    def render(self) -> Text:
        """Draws the summary line and, when open, the output beneath it.

        Returns:
            rendered: The row as coloured text ready for the timeline.
        """
        block: Text = Text()
        block.append(f"{NODE_MARKER} ", style=self.palette.accent)
        block.append(self.summary_line(), style=self.highlight_color())
        argument = self.input_line()
        if self.is_expanded and argument:
            block.append(f"\n{CHAIN_MARKER}{DETAIL_INDENT}{argument}")
        for index, line in enumerate(self.detail_lines()):
            prefix = OUTPUT_MARKER if index == 0 else "   "
            block.append(f"\n{CHAIN_MARKER}{DETAIL_INDENT}{prefix} {line}")
        return block

    def action_toggle_step(self) -> None:
        """Opens the row when it is closed, and closes it when it is open."""
        self.is_expanded = not self.is_expanded

    def watch_is_expanded(self, is_expanded: bool) -> None:
        """Redraws only this row when it opens or closes.

        Args:
            is_expanded: Whether the row is now showing its output.
        """
        del is_expanded
        if self.is_mounted:
            self.refresh()
