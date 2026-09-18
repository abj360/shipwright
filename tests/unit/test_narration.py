#!/usr/bin/env python3
"""
test_narration.py --- covers prose the model adds after a multi-line argument

A value such as write_file's content runs to the end of the reply, so a
sentence about what the model plans to do next was being written into the file.

Contains:
    test_trailing_narration_is_dropped(): the sentence never reaches the file
    test_content_with_no_narration_is_untouched(): ordinary content is left alone
    test_prose_that_belongs_to_the_file_stays(): a file may end with a sentence
    test_narration_inside_the_content_stays(): only a trailing line is dropped
    test_writing_through_the_loop_leaves_the_file_clean(): end to end
"""

from pathlib import Path

from agent.circuit_breaker import CircuitBreaker
from agent.llm_client import ScriptedLLM
from agent.loop import AgentConfig, AgentLoop, strip_trailing_narration

CODE = "def apply_discount(price, pct):\n    return price * (1 - pct)\n"


def test_trailing_narration_is_dropped() -> None:
    """Asserts a closing "now let me..." line is not part of the value."""
    value = f"{CODE}\nNow let me read the file back to verify the change:"

    assert strip_trailing_narration(value) == CODE.rstrip()


def test_content_with_no_narration_is_untouched() -> None:
    """Asserts content that says nothing about the next move is left as it is."""
    assert strip_trailing_narration(CODE) == CODE


def test_prose_that_belongs_to_the_file_stays() -> None:
    """Asserts a file ending in an ordinary sentence keeps it."""
    readme = "# Pricing\n\nThis module applies discounts to prices.\n"

    assert strip_trailing_narration(readme) == readme


def test_narration_inside_the_content_stays() -> None:
    """Asserts only a trailing paragraph goes; the same words earlier are content."""
    doc = "Let me explain the rules.\n\nThe rate is capped at one.\n"

    assert strip_trailing_narration(doc) == doc


def test_writing_through_the_loop_leaves_the_file_clean(tmp_path: Path) -> None:
    """Asserts a write whose reply ends in narration writes only the file's content."""
    reply = (
        "Adding the check.\n"
        "Action: write_file\n"
        f"path=pricing.py; content={CODE}\n"
        "Now let me read the file back to verify the change:"
    )
    config = AgentConfig(
        repo_path=str(tmp_path),
        task="add validation",
        breaker=CircuitBreaker(max_iterations=6, max_cost_usd=1.0),
    )

    AgentLoop(ScriptedLLM([reply, "FINAL: added the check"]), config).run()

    assert "Now let me" not in (tmp_path / "pricing.py").read_text()
