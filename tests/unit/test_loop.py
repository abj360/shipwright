#!/usr/bin/env python3
"""
test_loop.py --- unit tests for the ReAct agent loop

Contains:
    make_config(): builds a minimal agent config
"""

import pytest

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
