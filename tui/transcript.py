#!/usr/bin/env python3
"""
transcript.py --- reads a saved transcript back as completed timeline rows

Contains:
    HistoricalStep: one step replayed from an earlier run
    load_prior_rows(): reads a saved transcript into dimmed completed rows
    describe_resume(): summarizes what a resume loaded, for the timeline
"""

import json
from pathlib import Path

from tui.labels import label_for


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


def load_prior_rows(path: Path) -> list[HistoricalStep]:
    """Reads a saved transcript into rows the timeline renders dimmed.

    Args:
        path: JSON transcript written by an earlier run.

    Returns:
        rows: Completed steps in the order they originally ran.
    """
    raw = json.loads(path.read_text())
    rows = []
    for index, entry in enumerate(raw):
        observation = entry.get("observation", "")
        rows.append(
            HistoricalStep(
                index=index,
                label=label_for(entry.get("tool_name", "")),
                target=entry.get("tool_args", {}).get("path", ""),
                failed=observation.startswith("error:"),
            )
        )
    return rows


def describe_resume(rows: list[HistoricalStep]) -> str:
    """Summarizes a resume for the line the timeline prints above the rows.

    Args:
        rows: Steps that were replayed.

    Returns:
        summary: One line naming how much history was restored.
    """
    return f"resumed {len(rows)} earlier steps"
