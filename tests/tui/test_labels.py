#!/usr/bin/env python3
"""
test_labels.py --- covers the activity wording carried over from the web view

Contains:
    test_known_tools_keep_their_wording(): the three headline labels are unchanged
    test_every_dispatcher_tool_has_a_label(): no tool renders as the fallback
    test_unknown_tool_falls_back(): an unregistered tool still reads sensibly
"""

from tui.labels import FALLBACK_LABEL, TOOL_LABELS, label_for


def test_known_tools_keep_their_wording() -> None:
    """Asserts the labels the web view used are reproduced exactly."""
    assert label_for("read_file") == "Read"
    assert label_for("edit_file") == "Edited"
    assert label_for("run_shell") == "Ran"


def test_every_dispatcher_tool_has_a_label() -> None:
    """Asserts every tool the dispatcher exposes has explicit wording."""
    from agent.tool_dispatcher import REQUIRED_ARGS

    unlabelled = set(REQUIRED_ARGS) - set(TOOL_LABELS)

    assert unlabelled == set()


def test_unknown_tool_falls_back() -> None:
    """Asserts an unregistered tool name still renders readable wording."""
    assert label_for("teleport") == FALLBACK_LABEL
