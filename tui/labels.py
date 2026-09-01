#!/usr/bin/env python3
"""
labels.py --- human wording for each tool name, carried over from the web view

Contains:
    TOOL_LABELS: human wording for each tool the dispatcher exposes
    FALLBACK_LABEL: wording used for a tool with no registered label
    label_for(): resolves one tool name to the wording shown in the timeline
"""

TOOL_LABELS: dict[str, str] = {
    "read_file": "Read",
    "write_file": "Wrote",
    "edit_file": "Edited",
    "list_dir": "Listed",
    "run_shell": "Ran",
    "run_tests": "Tested",
    "git_diff": "Diffed",
    "apply_patch": "Patched",
}
FALLBACK_LABEL = "Ran"


def label_for(tool_name: str) -> str:
    """Resolves a tool name to the wording the timeline shows.

    Args:
        tool_name: Tool the agent dispatched, as the loop recorded it.

    Returns:
        label: Human wording for that tool, or the fallback wording.
    """
    return TOOL_LABELS.get(tool_name, FALLBACK_LABEL)
