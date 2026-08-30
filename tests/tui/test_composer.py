#!/usr/bin/env python3
"""
test_composer.py --- covers the composer's send-or-queue behaviour

Contains:
    test_idle_submit_sends(): an instruction typed while idle is sent
    test_busy_submit_queues(): an instruction typed mid-run is queued
    test_queue_drains_oldest_first(): queued work runs in the order it was typed
    test_blank_input_is_ignored(): whitespace never becomes an instruction
    test_going_idle_lets_the_next_one_send(): the queue stops after the run ends
    test_queue_holds_several_follow_ups(): a long queue keeps every instruction
"""

from tui.screens.composer import QUEUED_NOTICE, SENT_NOTICE, Composer


def test_idle_submit_sends() -> None:
    """Asserts an instruction typed while nothing is running is sent straight on."""
    composer = Composer()

    assert composer.submit("add a health endpoint") == SENT_NOTICE
    assert composer.pending == []


def test_busy_submit_queues() -> None:
    """Asserts an instruction typed during a run is held rather than sent."""
    composer = Composer()
    composer.mark_busy()

    assert composer.submit("then bump the version") == QUEUED_NOTICE
    assert composer.pending == ["then bump the version"]


def test_queue_drains_oldest_first() -> None:
    """Asserts queued instructions come back in the order they were typed."""
    composer = Composer()
    composer.mark_busy()
    composer.submit("first")
    composer.submit("second")

    assert composer.take_next() == "first"
    assert composer.take_next() == "second"
    assert composer.take_next() is None


def test_blank_input_is_ignored() -> None:
    """Asserts whitespace-only input is never queued or sent."""
    composer = Composer()
    composer.mark_busy()

    assert composer.submit("   ") == ""
    assert composer.pending == []


def test_going_idle_lets_the_next_one_send() -> None:
    """Asserts the composer stops queueing once the run has finished."""
    composer = Composer()
    composer.mark_busy()
    composer.submit("queued one")
    composer.mark_idle()

    assert composer.submit("straight through") == SENT_NOTICE
    assert composer.pending == ["queued one"]


def test_queue_holds_several_follow_ups() -> None:
    """Asserts a run interrupted repeatedly keeps every queued instruction."""
    composer = Composer()
    composer.mark_busy()
    for index in range(5):
        composer.submit(f"step {index}")

    drained = [composer.take_next() for _ in range(5)]

    assert drained == [f"step {index}" for index in range(5)]
