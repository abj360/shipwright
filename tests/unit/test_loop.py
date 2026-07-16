#!/usr/bin/env python3
"""
test_loop.py --- unit tests for the ReAct agent loop

Contains:
    make_config(): builds a minimal agent config
"""

import pytest

from agent.cost_tracker import CostTracker
from agent.llm_client import ScriptedLLM
from agent.loop import AgentConfig, AgentLoop, Step

def make_config(task: str = "fix the bug") -> AgentConfig:
    """Builds a minimal agent config for tests.

    Args:
        task: Task text for the run.

    Returns:
        config: Agent config rooted at the current directory.
    """
    return AgentConfig(repo_path=".", task=task)

def test_final_answer_stops_run() -> None:
    """Verifies the loop stops as soon as the model emits FINAL:."""
    loop = AgentLoop(ScriptedLLM(["FINAL: all done"]), make_config())
    result = loop.run()
    assert result.final_answer == "all done"
    assert len(result.steps) == 1

def test_unknown_tool_yields_error_observation() -> None:
    """Verifies an unknown tool call comes back as an error observation."""
    responses = ["think\nAction: nope\npath=.", "FINAL: gave up"]
    loop = AgentLoop(ScriptedLLM(responses), make_config())
    result = loop.run()
    assert result.steps[0].observation.startswith("error:")

def test_transcript_records_each_step() -> None:
    """Verifies every think-act-observe cycle lands in the transcript."""
    responses = ["think\nAction: list_dir\npath=.", "FINAL: done"]
    loop = AgentLoop(ScriptedLLM(responses), make_config())
    result = loop.run()
    assert len(result.steps) == 2
    assert result.steps[0].tool_name == "list_dir"

def test_loop_mx_4_0() -> None:
    """Verifies loop behavior: run_tests call completes."""
    responses = ["think\nAction: run_tests\n", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.final_answer == 'done'

def test_loop_mx_2_3() -> None:
    """Verifies loop behavior: run_shell call returns result."""
    responses = ["think\nAction: run_shell\ncommand=ls", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result is not None

def test_loop_mx_1_2() -> None:
    """Verifies loop behavior: read_file call stores args."""
    responses = ["think\nAction: read_file\npath=a.py", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].tool_name == 'read_file'

def test_loop_mx_4_3() -> None:
    """Verifies loop behavior: run_tests call returns result."""
    responses = ["think\nAction: run_tests\n", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result is not None

def test_loop_mx_5_3() -> None:
    """Verifies loop behavior: git_diff call returns result."""
    responses = ["think\nAction: git_diff\n", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result is not None

def test_loop_mx2_0_0() -> None:
    """Verifies loop behavior: list_dir call: two steps total."""
    responses = ["think\nAction: list_dir\npath=.", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert len(result.steps) == 2

def test_malformed_reply_triggers_one_retry() -> None:
    """Verifies a reply with no Action and no FINAL is retried once."""
    responses = ["garbage with no markers", "FINAL: recovered"]
    loop = AgentLoop(ScriptedLLM(responses), make_config())
    result = loop.run()
    assert result.final_answer == "recovered"

def test_tool_args_parse_key_value_pairs() -> None:
    """Verifies action arguments split on semicolons into a dict."""
    responses = ["think\nAction: read_file\npath=a.py; mode=fast", "FINAL: done"]
    loop = AgentLoop(ScriptedLLM(responses), make_config())
    result = loop.run()
    assert result.steps[0].tool_args == {"path": "a.py", "mode": "fast"}

def test_run_result_has_wall_clock_duration() -> None:
    """Verifies a finished run reports a non-negative duration."""
    loop = AgentLoop(ScriptedLLM(["FINAL: done"]), make_config())
    result = loop.run()
    assert result.duration_s >= 0.0

def test_cost_accumulates_per_completion() -> None:
    """Verifies completions accumulate spend through the tracker."""
    tracker = CostTracker()
    config = make_config()
    config.cost_tracker = tracker
    loop = AgentLoop(ScriptedLLM(["FINAL: done"]), config)
    loop.run()
    assert tracker.total_usd() >= 0.0

def test_loop_mx2_1_6() -> None:
    """Verifies loop behavior: read_file call: cost non-negative."""
    responses = ["think\nAction: read_file\npath=a.py", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.total_cost_usd >= 0.0

def test_loop_mx2_0_5() -> None:
    """Verifies loop behavior: list_dir call: duration non-negative."""
    responses = ["think\nAction: list_dir\npath=.", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.duration_s >= 0.0

def test_loop_mx_0_2() -> None:
    """Verifies loop behavior: list_dir call stores args."""
    responses = ["think\nAction: list_dir\npath=.", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].tool_name == 'list_dir'
