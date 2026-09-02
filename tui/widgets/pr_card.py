#!/usr/bin/env python3
"""
pr_card.py --- PR summary card carrying the run's judgeline score badge

Contains:
    READY_BADGE / NOT_READY_BADGE: wording shown beside the score
    UNSCORED_BADGE: wording used when the run record carries no score
    read_score(): reads the judgeline score off a run record
    badge_for(): renders the readiness badge for one score
    PrCard: renders the PR link and its readiness badge
    PrCard.compose(): lays out the PR line above the badge line
"""

from typing import Any

from textual.app import ComposeResult
from textual.widgets import Label, Static

from agent.judgeline_client import JudgelineClient, ScoreResult

READY_BADGE = "READY"
NOT_READY_BADGE = "NOT READY"
UNSCORED_BADGE = "NOT SCORED"


def read_score(record: dict[str, Any]) -> ScoreResult | None:
    """Reads the judgeline score already present on a run record.

    The score is whatever judgeline wrote when it scored the diff; the card
    never scores anything itself. A record with no score is reported as
    unscored rather than being treated as a pass.

    Args:
        record: Run record as returned by GET /runs/:id.

    Returns:
        result: Score carried by the record, or None when it is unscored.
    """
    raw = record.get("score")
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        return None
    return ScoreResult(score=float(raw), verdict=str(record.get("verdict", "")))


def badge_for(result: ScoreResult | None) -> str:
    """Renders the readiness badge for one score.

    Readiness is decided by the same judgeline threshold the merge gate uses,
    so the card and the gate can never disagree.

    Args:
        result: Score read off the run record, or None when unscored.

    Returns:
        badge: Badge text, including the score when there is one.
    """
    if result is None:
        return UNSCORED_BADGE
    is_ready = JudgelineClient().is_ready(result)
    label = READY_BADGE if is_ready else NOT_READY_BADGE
    return f"{label} ({result.score:.2f})"


class PrCard(Static):
    """Renders the draft PR for a finished run beside its readiness badge.

    Attributes:
        record: Run record the card was built from.
    """

    def __init__(self, record: dict[str, Any]) -> None:
        """Builds the card from one run record.

        Args:
            record: Run record as returned by GET /runs/:id.
        """
        super().__init__()
        self.record = record

    def compose(self) -> ComposeResult:
        """Lays out the PR line above the readiness badge."""
        url = str(self.record.get("prUrl", "")) or "no pull request yet"
        yield Label(url)
        yield Label(badge_for(read_score(self.record)))
