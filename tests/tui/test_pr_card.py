#!/usr/bin/env python3
"""
test_pr_card.py --- covers the PR card's judgeline readiness badge

Contains:
    test_high_score_reads_ready(): a score above the threshold reads READY
    test_low_score_reads_not_ready(): a score below the threshold is blocked
    test_unscored_record_is_not_ready(): a missing score never reads as a pass
    test_non_numeric_score_is_rejected(): a malformed score is treated as absent
"""

from tui.widgets.pr_card import NOT_READY_BADGE, READY_BADGE, UNSCORED_BADGE, badge_for, read_score


def test_high_score_reads_ready() -> None:
    """Asserts a score clearing the judgeline threshold reads as ready."""
    badge = badge_for(read_score({"score": 0.94}))

    assert badge.startswith(READY_BADGE)
    assert "0.94" in badge


def test_low_score_reads_not_ready() -> None:
    """Asserts a score under the judgeline threshold is reported as blocked."""
    badge = badge_for(read_score({"score": 0.21}))

    assert badge.startswith(NOT_READY_BADGE)


def test_unscored_record_is_not_ready() -> None:
    """Asserts a record judgeline never scored is not presented as a pass."""
    assert read_score({"id": "abc"}) is None
    assert badge_for(None) == UNSCORED_BADGE


def test_non_numeric_score_is_rejected() -> None:
    """Asserts a malformed score field is treated as unscored, not coerced."""
    assert read_score({"score": "great"}) is None
    assert read_score({"score": True}) is None
