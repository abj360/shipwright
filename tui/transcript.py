#!/usr/bin/env python3
"""
transcript.py --- reads a saved transcript back as completed timeline rows

Contains:
    HistoricalStep: one step replayed from an earlier run
    _row_from_entry(): builds one replayed row from a transcript entry
    load_prior_rows(): reads a saved transcript into dimmed completed rows
    MISSING_PATH_NOTICE: usage line shown when /resume is typed bare
    describe_resume(): summarizes what a resume loaded, for the timeline
    resume(): resolves a /resume argument into a line for the timeline
"""

import json
from pathlib import Path
from typing import Any

from tui.labels import label_for

MISSING_PATH_NOTICE = "usage: /resume <transcript path>"


class HistoricalStep:
    """Represents one step replayed from an earlier run.

    Attributes:
        index: Position the step held in the original run.
        label: Activity wording shown on the row.
        target: Primary argument the step acted on.
        failed: True when the original step reported an error.
    """

    def __init__(self, index: int, label: str, target: str, failed: bool) -> None:
        """Records one replayed step.

        Args:
            index: Position the step held in the original run.
            label: Activity wording shown on the row.
            target: Primary argument the step acted on.
            failed: True when the original step reported an error.
        """
        self.index = index
        self.label = label
        self.target = target
        self.failed = failed

    @property
    def is_historical(self) -> bool:
        """Marks the row as replayed so the timeline dims it.

        Returns:
            is_historical: Always True for a replayed step.
        """
        return True


def _row_from_entry(index: int, entry: dict[str, Any]) -> HistoricalStep:
    """Builds one replayed row from a single transcript entry.

    Args:
        index: Position the step held in the original run.
        entry: One deserialized transcript step.

    Returns:
        row: Replayed step ready for the timeline.
    """
    observation = entry.get("observation", "")
    args = entry.get("tool_args", {})
    return HistoricalStep(
        index=index,
        label=label_for(str(entry.get("tool_name", ""))),
        target=str(args.get("path", "")) if isinstance(args, dict) else "",
        failed=isinstance(observation, str) and observation.startswith("error:"),
    )


def load_prior_rows(path: Path) -> list[HistoricalStep]:
    """Reads a saved transcript into rows the timeline renders dimmed.

    Args:
        path: JSON transcript written by an earlier run.

    Returns:
        rows: Completed steps in the order they originally ran.
    """
    # A transcript is operator-supplied JSON, so its fields are genuinely untyped.
    raw: list[dict[str, Any]] = json.loads(path.read_text())
    return [_row_from_entry(index, entry) for index, entry in enumerate(raw)]


def describe_resume(rows: list[HistoricalStep]) -> str:
    """Summarizes a resume for the line the timeline prints above the rows.

    Args:
        rows: Steps that were replayed.

    Returns:
        summary: One line naming how much history was restored.
    """
    return f"resumed {len(rows)} earlier steps"


def resume(argument: str) -> str:
    """Resolves a /resume argument into the line the timeline shows.

    Args:
        argument: Path the operator typed after the command, possibly empty.

    Returns:
        line: Summary of what was restored, or a usage hint.
    """
    trimmed = argument.strip()
    if not trimmed:
        return MISSING_PATH_NOTICE
    path = Path(trimmed)
    if not path.exists():
        return f"no transcript at {path}"
    return describe_resume(load_prior_rows(path))
