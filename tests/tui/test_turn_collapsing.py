#!/usr/bin/env python3
"""
test_turn_collapsing.py --- covers which turns the timeline folds away

Contains:
    _finished(): a finished turn
    _running(): a turn still in flight
    test_newest_turn_stays_open(): the turn being watched is never folded
    test_older_finished_turns_collapse(): completed history folds away
    test_running_turns_are_never_collapsed(): an in-flight turn stays open
    test_collapsing_is_idempotent(): a second pass folds nothing new
    test_keep_expanded_zero_folds_everything(): every finished turn can fold
    test_empty_timeline_collapses_nothing(): no turns is not an error
    test_keep_more_than_exists_collapses_nothing(): an oversized keep is safe
    test_unfinished_newest_turn_blocks_nothing(): older turns still fold
"""

import pytest

from tui.screens.timeline import Timeline, Turn, collapse_completed_turns


def _finished(instruction: str) -> Turn:
    """Builds a turn that has already produced an answer.

    Args:
        instruction: What the turn was asked to do.

    Returns:
        turn: A finished turn.
    """
    return Turn(instruction=instruction, answer="done")


def _running(instruction: str) -> Turn:
    """Builds a turn that is still in flight.

    Args:
        instruction: What the turn was asked to do.

    Returns:
        turn: An unfinished turn.
    """
    return Turn(instruction=instruction)


def test_newest_turn_stays_open() -> None:
    """Asserts the most recent turn is never folded away."""
    turns = [_finished("one"), _finished("two")]

    collapse_completed_turns(turns, keep_expanded=1)

    assert turns[0].is_collapsed is True
    assert turns[1].is_collapsed is False


def test_older_finished_turns_collapse() -> None:
    """Asserts completed history folds so the live turn has room."""
    turns = [_finished(str(index)) for index in range(5)]

    collapsed = collapse_completed_turns(turns, keep_expanded=1)

    assert collapsed == 4
    assert [turn.is_collapsed for turn in turns] == [True, True, True, True, False]


def test_running_turns_are_never_collapsed() -> None:
    """Asserts a turn still working is left open however old it is."""
    turns = [_running("still going"), _finished("a"), _finished("b")]

    collapse_completed_turns(turns, keep_expanded=1)

    assert turns[0].is_collapsed is False


def test_collapsing_is_idempotent() -> None:
    """Asserts running the pass twice does not fold anything a second time."""
    turns = [_finished("one"), _finished("two"), _finished("three")]

    first = collapse_completed_turns(turns, keep_expanded=1)
    second = collapse_completed_turns(turns, keep_expanded=1)

    assert first == 2
    assert second == 0


def test_keep_expanded_zero_folds_everything() -> None:
    """Asserts asking to keep nothing open folds every finished turn."""
    turns = [_finished("one"), _finished("two")]

    collapse_completed_turns(turns, keep_expanded=0)

    assert all(turn.is_collapsed for turn in turns)


def test_negative_keep_expanded_is_rejected() -> None:
    """Asserts a nonsensical keep count is refused rather than silently clamped."""
    with pytest.raises(ValueError):
        collapse_completed_turns([_finished("one")], keep_expanded=-1)


def test_starting_a_turn_collapses_the_previous_one() -> None:
    """Asserts opening a new turn folds the finished one behind it."""
    timeline = Timeline()
    timeline.start_turn("first")
    timeline.finish_turn("done")

    timeline.start_turn("second")

    assert timeline.turns[0].is_collapsed is True
    assert timeline.turns[1].is_collapsed is False


def test_empty_timeline_collapses_nothing() -> None:
    """Asserts collapsing an empty timeline is a no-op rather than an error."""
    assert collapse_completed_turns([], keep_expanded=1) == 0


def test_keep_more_than_exists_collapses_nothing() -> None:
    """Asserts keeping more turns open than exist folds nothing away."""
    turns = [_finished("one")]

    assert collapse_completed_turns(turns, keep_expanded=10) == 0
    assert turns[0].is_collapsed is False


def test_unfinished_newest_turn_blocks_nothing() -> None:
    """Asserts a live newest turn does not stop older finished ones folding."""
    turns = [_finished("one"), _finished("two"), _running("three")]

    collapsed = collapse_completed_turns(turns, keep_expanded=1)

    assert collapsed == 2
    assert turns[2].is_collapsed is False
