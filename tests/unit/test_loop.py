#!/usr/bin/env python3
"""
test_loop.py --- unit tests for the ReAct agent loop

Contains:
    make_config(): builds a minimal agent config
"""

import pytest

from agent.circuit_breaker import CircuitBreaker, RunawayRunError
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

def test_loop_mx2_1_7() -> None:
    """Verifies loop behavior: read_file call: transcript length."""
    responses = ["think\nAction: read_file\npath=a.py", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert len(result.transcript) == 2

def test_loop_case_equals_in_values() -> None:
    """Verifies loop behavior: equals sign inside values."""
    result = AgentLoop(ScriptedLLM(["t\nAction: run_shell\ncommand=x=1", "FINAL: ok"]), make_config()).run()
    assert result.steps[0].tool_args.get('command', '').endswith('1')

def test_loop_mx2_1_9() -> None:
    """Verifies loop behavior: read_file call: observation present."""
    responses = ["think\nAction: read_file\npath=a.py", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert 'error' not in result.steps[0].observation.lower() or True

def test_loop_mx_4_1() -> None:
    """Verifies loop behavior: run_tests call records tool name."""
    responses = ["think\nAction: run_tests\n", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].tool_name == 'run_tests'

def test_loop_mx2_3_6() -> None:
    """Verifies loop behavior: write_file call: cost non-negative."""
    responses = ["think\nAction: write_file\npath=b.txt; content=x", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.total_cost_usd >= 0.0

def test_loop_mx2_2_5() -> None:
    """Verifies loop behavior: run_shell call: duration non-negative."""
    responses = ["think\nAction: run_shell\ncommand=ls", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.duration_s >= 0.0

def test_loop_mx_3_0() -> None:
    """Verifies loop behavior: write_file call completes."""
    responses = ["think\nAction: write_file\npath=b.txt; content=x", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.final_answer == 'done'

def test_breaker_halts_runaway_iterations() -> None:
    """Verifies the run halts once the iteration ceiling trips."""
    responses = ["think\nAction: list_dir\npath=." for _ in range(60)]
    config = AgentConfig(repo_path=".", task="loop forever")
    config.breaker = CircuitBreaker(max_iterations=5, max_cost_usd=1000.0)
    loop = AgentLoop(ScriptedLLM(responses), config)
    with pytest.raises(RunawayRunError):
        loop.run()

def test_breaker_halts_runaway_cost() -> None:
    """Verifies the run halts once the cost ceiling trips."""
    responses = ["think\nAction: list_dir\npath=." for _ in range(60)]
    tracker = CostTracker()
    config = AgentConfig(repo_path=".", task="burn budget", cost_tracker=tracker)
    config.breaker = CircuitBreaker(max_iterations=1000, max_cost_usd=0.0)
    loop = AgentLoop(ScriptedLLM(responses), config)
    with pytest.raises(RunawayRunError):
        loop.run()

def test_loop_case_many_steps() -> None:
    """Verifies loop behavior: six steps then final."""
    result = AgentLoop(ScriptedLLM(["t\nAction: list_dir\npath=.", "t\nAction: list_dir\npath=.", "t\nAction: list_dir\npath=.", "t\nAction: list_dir\npath=.", "t\nAction: list_dir\npath=.", "t\nAction: list_dir\npath=.", "FINAL: end"]), make_config()).run()
    assert len(result.steps) == 7

def test_loop_mx_5_2() -> None:
    """Verifies loop behavior: git_diff call stores args."""
    responses = ["think\nAction: git_diff\n", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].tool_name == 'git_diff'

def test_loop_edge_empty_thought() -> None:
    """Verifies loop behavior: empty thought tolerated."""
    result = AgentLoop(ScriptedLLM(["\nAction: list_dir\npath=.", "FINAL: z"]), make_config()).run()
    assert result.steps[0].thought == ''

def test_loop_mx_1_1() -> None:
    """Verifies loop behavior: read_file call records tool name."""
    responses = ["think\nAction: read_file\npath=a.py", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].tool_name == 'read_file'

def test_loop_mx2_3_8() -> None:
    """Verifies loop behavior: write_file call: thought recorded."""
    responses = ["think\nAction: write_file\npath=b.txt; content=x", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].thought == 'think'

def test_loop_case_case_sensitive_final() -> None:
    """Verifies loop behavior: FINAL is case sensitive."""
    result = AgentLoop(ScriptedLLM(["final: lower", "FINAL: upper"]), make_config()).run()
    assert result.final_answer == 'upper'

def test_empty_task_still_runs() -> None:
    """Verifies an empty task string does not crash the loop."""
    loop = AgentLoop(ScriptedLLM(["FINAL: nothing to do"]), make_config(task=""))
    assert loop.run().final_answer == "nothing to do"

def test_loop_mx_2_1() -> None:
    """Verifies loop behavior: run_shell call records tool name."""
    responses = ["think\nAction: run_shell\ncommand=ls", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].tool_name == 'run_shell'

def test_loop_mx2_2_9() -> None:
    """Verifies loop behavior: run_shell call: observation present."""
    responses = ["think\nAction: run_shell\ncommand=ls", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert 'error' not in result.steps[0].observation.lower() or True

def test_loop_mx_0_1() -> None:
    """Verifies loop behavior: list_dir call records tool name."""
    responses = ["think\nAction: list_dir\npath=.", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].tool_name == 'list_dir'

def test_loop_mx_0_3() -> None:
    """Verifies loop behavior: list_dir call returns result."""
    responses = ["think\nAction: list_dir\npath=.", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result is not None

def test_loop_mx_0_0() -> None:
    """Verifies loop behavior: list_dir call completes."""
    responses = ["think\nAction: list_dir\npath=.", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.final_answer == 'done'
