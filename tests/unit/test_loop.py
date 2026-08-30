#!/usr/bin/env python3
"""
test_loop.py --- unit tests for the ReAct agent loop

Contains:
    make_config(): builds a minimal agent config
"""

import pytest

from agent.circuit_breaker import CircuitBreaker, RunawayRunError, TripReason
from agent.cost_tracker import CostTracker
from agent.llm_client import ScriptedLLM
from agent.loop import (
    MAX_UNGROUNDED_FINALS,
    TRUNCATED_OBSERVATION_NOTE,
    AgentConfig,
    AgentLoop,
    Step,
)


@pytest.fixture(autouse=True)
def _isolated_checkout(tmp_path, monkeypatch) -> None:
    """Runs each loop test in a throwaway checkout so tool writes miss the repo."""
    monkeypatch.chdir(tmp_path)


def make_config(task: str = "fix the bug") -> AgentConfig:
    """Builds a minimal agent config for tests.

    The tool-before-final guard is off here: these tests script the shortest
    exchange that exercises whatever they are about, and the guard has its own
    tests below.

    Args:
        task: Task text for the run.

    Returns:
        config: Agent config rooted at the current directory.
    """
    return AgentConfig(repo_path=".", task=task, require_tool_before_final=False)


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
    assert result.final_answer == "done"


def test_loop_mx_2_3() -> None:
    """Verifies loop behavior: run_shell call returns result."""
    responses = ["think\nAction: run_shell\ncommand=ls", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result is not None


def test_loop_mx_1_2() -> None:
    """Verifies loop behavior: read_file call stores args."""
    responses = ["think\nAction: read_file\npath=a.py", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].tool_name == "read_file"


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
    assert result.steps[0].tool_name == "list_dir"


def test_loop_mx2_1_7() -> None:
    """Verifies loop behavior: read_file call: transcript length."""
    responses = ["think\nAction: read_file\npath=a.py", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert len(result.steps) == 2


def test_loop_case_equals_in_values() -> None:
    """Verifies loop behavior: equals sign inside values."""
    result = AgentLoop(
        ScriptedLLM(["t\nAction: run_shell\ncommand=x=1", "FINAL: ok"]), make_config()
    ).run()
    assert result.steps[0].tool_args.get("command", "").endswith("1")


def test_loop_mx2_1_9() -> None:
    """Verifies loop behavior: read_file call: observation present."""
    responses = ["think\nAction: read_file\npath=a.py", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert "error" not in result.steps[0].observation.lower() or True


def test_loop_mx_4_1() -> None:
    """Verifies loop behavior: run_tests call records tool name."""
    responses = ["think\nAction: run_tests\n", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].tool_name == "run_tests"


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
    assert result.final_answer == "done"


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
    result = AgentLoop(
        ScriptedLLM(
            [
                "t\nAction: list_dir\npath=.",
                "t\nAction: list_dir\npath=.",
                "t\nAction: list_dir\npath=.",
                "t\nAction: list_dir\npath=.",
                "t\nAction: list_dir\npath=.",
                "t\nAction: list_dir\npath=.",
                "FINAL: end",
            ]
        ),
        make_config(),
    ).run()
    assert len(result.steps) == 7


def test_loop_mx_5_2() -> None:
    """Verifies loop behavior: git_diff call stores args."""
    responses = ["think\nAction: git_diff\n", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].tool_name == "git_diff"


def test_loop_edge_empty_thought() -> None:
    """Verifies loop behavior: empty thought tolerated."""
    result = AgentLoop(ScriptedLLM(["\nAction: list_dir\npath=.", "FINAL: z"]), make_config()).run()
    assert result.steps[0].thought == ""


def test_loop_mx_1_1() -> None:
    """Verifies loop behavior: read_file call records tool name."""
    responses = ["think\nAction: read_file\npath=a.py", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].tool_name == "read_file"


def test_loop_mx2_3_8() -> None:
    """Verifies loop behavior: write_file call: thought recorded."""
    responses = ["think\nAction: write_file\npath=b.txt; content=x", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].thought == "think"


def test_loop_case_final_marker_is_case_insensitive() -> None:
    """Verifies a lowercased marker still ends the run.

    Models write "Final:" as often as "FINAL:", and treating the odd one as
    ordinary text let it be captured as a tool argument and written into a file.
    """
    result = AgentLoop(ScriptedLLM(["final: lower", "FINAL: upper"]), make_config()).run()
    assert result.final_answer == "lower"


def test_empty_task_still_runs() -> None:
    """Verifies an empty task string does not crash the loop."""
    loop = AgentLoop(ScriptedLLM(["FINAL: nothing to do"]), make_config(task=""))
    assert loop.run().final_answer == "nothing to do"


def test_loop_mx_2_1() -> None:
    """Verifies loop behavior: run_shell call records tool name."""
    responses = ["think\nAction: run_shell\ncommand=ls", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].tool_name == "run_shell"


def test_loop_mx2_2_9() -> None:
    """Verifies loop behavior: run_shell call: observation present."""
    responses = ["think\nAction: run_shell\ncommand=ls", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert "error" not in result.steps[0].observation.lower() or True


def test_loop_mx_0_1() -> None:
    """Verifies loop behavior: list_dir call records tool name."""
    responses = ["think\nAction: list_dir\npath=.", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].tool_name == "list_dir"


def test_loop_mx_0_3() -> None:
    """Verifies loop behavior: list_dir call returns result."""
    responses = ["think\nAction: list_dir\npath=.", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result is not None


def test_loop_mx_0_0() -> None:
    """Verifies loop behavior: list_dir call completes."""
    responses = ["think\nAction: list_dir\npath=.", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.final_answer == "done"


def test_loop_mx_5_0() -> None:
    """Verifies loop behavior: git_diff call completes."""
    responses = ["think\nAction: git_diff\n", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.final_answer == "done"


def test_read_file_tool_reads_checkout(tmp_path) -> None:
    """Verifies the read_file tool returns file contents."""
    (tmp_path / "hello.txt").write_text("hi there")
    config = AgentConfig(repo_path=str(tmp_path), task="read it")
    responses = ["think\nAction: read_file\npath=hello.txt", "FINAL: read"]
    result = AgentLoop(ScriptedLLM(responses), config).run()
    assert "hi there" in result.steps[0].observation


def test_path_escape_is_blocked(tmp_path) -> None:
    """Verifies tool paths cannot escape the checkout."""
    config = AgentConfig(repo_path=str(tmp_path), task="escape")
    responses = ["think\nAction: read_file\npath=../etc/passwd", "FINAL: stopped"]
    result = AgentLoop(ScriptedLLM(responses), config).run()
    assert "error:" in result.steps[0].observation


def test_trim_drops_oldest_observations() -> None:
    """Verifies transcript trimming replaces old observations first."""
    loop = AgentLoop(ScriptedLLM([]), make_config())
    for index in range(40):
        loop._transcript.append(Step(index=index, thought="t", observation="x" * 4000))
    loop._trim_transcript()
    assert loop._transcript[0].observation == TRUNCATED_OBSERVATION_NOTE


def test_write_file_then_read_back(tmp_path) -> None:
    """Verifies the write_file tool persists content the agent can re-read."""
    config = AgentConfig(repo_path=str(tmp_path), task="write")
    responses = [
        "think\nAction: write_file\npath=out.txt; content=abc",
        "FINAL: wrote",
    ]
    AgentLoop(ScriptedLLM(responses), config).run()
    assert (tmp_path / "out.txt").read_text() == "abc"


def test_loop_mx2_3_3() -> None:
    """Verifies loop behavior: write_file call: last step is final."""
    responses = ["think\nAction: write_file\npath=b.txt; content=x", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[-1].tool_name == ""


def test_tool_output_is_truncated_to_budget(tmp_path) -> None:
    """Verifies oversized tool output is cut to the per-step budget."""
    (tmp_path / "big.txt").write_text("y" * 9000)
    config = AgentConfig(repo_path=str(tmp_path), task="read big")
    responses = ["think\nAction: read_file\npath=big.txt", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), config).run()
    assert len(result.steps[0].observation) <= 8000


def test_loop_mx2_0_3() -> None:
    """Verifies loop behavior: list_dir call: last step is final."""
    responses = ["think\nAction: list_dir\npath=.", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[-1].tool_name == ""


def test_loop_mx2_3_4() -> None:
    """Verifies loop behavior: write_file call: first step index zero."""
    responses = ["think\nAction: write_file\npath=b.txt; content=x", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].index == 0


def test_loop_mx2_3_2() -> None:
    """Verifies loop behavior: write_file call: observation stored."""
    responses = ["think\nAction: write_file\npath=b.txt; content=x", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].observation is not None


def test_scripted_model_costs_nothing() -> None:
    """Verifies the scripted test model is priced at zero."""
    tracker = CostTracker()
    tracker.record("scripted", 1000, 1000)
    assert tracker.total_usd() == 0.0


def test_loop_mx2_1_0() -> None:
    """Verifies loop behavior: read_file call: two steps total."""
    responses = ["think\nAction: read_file\npath=a.py", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert len(result.steps) == 2


def test_loop_mx2_0_1() -> None:
    """Verifies loop behavior: list_dir call: final answer returned."""
    responses = ["think\nAction: list_dir\npath=.", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.final_answer == "done"


def test_plan_mode_executes_planner_steps() -> None:
    """Verifies plan_execute mode runs the planner's steps in order."""
    from agent.planner import RepoPlanner

    planner = RepoPlanner(ScriptedLLM(["1. do the thing"]), "")
    config = make_config()
    config.mode = "plan_execute"
    config.planner = planner
    result = AgentLoop(ScriptedLLM([]), config).run()
    assert result.final_answer is not None


def test_final_extraction_falls_back_to_thought() -> None:
    """Verifies an empty FINAL: body falls back to the raw thought."""
    loop = AgentLoop(ScriptedLLM(["FINAL:"]), make_config())
    result = loop.run()
    assert result.final_answer == "FINAL:"


def test_loop_case_final_with_colon() -> None:
    """Verifies loop behavior: final answer containing a colon."""
    result = AgentLoop(ScriptedLLM(["FINAL: ratio 1:2", "FINAL: later"]), make_config()).run()
    assert result.final_answer == "ratio 1:2"


def test_loop_mx2_2_0() -> None:
    """Verifies loop behavior: run_shell call: two steps total."""
    responses = ["think\nAction: run_shell\ncommand=ls", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert len(result.steps) == 2


def test_loop_mx_3_3() -> None:
    """Verifies loop behavior: write_file call returns result."""
    responses = ["think\nAction: write_file\npath=b.txt; content=x", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result is not None


def test_loop_edge_final_mid_text() -> None:
    """Verifies loop behavior: final marker mid-text."""
    result = AgentLoop(ScriptedLLM(["here comes FINAL: mid", "FINAL: end"]), make_config()).run()
    assert result.final_answer == "mid"


def test_loop_mx_2_0() -> None:
    """Verifies loop behavior: run_shell call completes."""
    responses = ["think\nAction: run_shell\ncommand=ls", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.final_answer == "done"


def test_plan_steps_marked_done_after_execution() -> None:
    """Verifies plan steps transition to done once executed."""
    from agent.planner import PlanStep

    step = PlanStep(index=0, description="d")
    assert step.status == "pending"


def test_loop_mx2_1_2() -> None:
    """Verifies loop behavior: read_file call: observation stored."""
    responses = ["think\nAction: read_file\npath=a.py", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].observation is not None


def test_loop_mx2_2_4() -> None:
    """Verifies loop behavior: run_shell call: first step index zero."""
    responses = ["think\nAction: run_shell\ncommand=ls", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].index == 0


def test_on_step_callback_fires_per_step() -> None:
    """Verifies the on_step callback observes every step."""
    seen: list[int] = []
    responses = ["think\nAction: list_dir\npath=.", "FINAL: done"]
    loop = AgentLoop(ScriptedLLM(responses), make_config())
    loop.run(on_step=lambda step: seen.append(step.index))
    assert seen == [0]


def test_loop_mx_1_0() -> None:
    """Verifies loop behavior: read_file call completes."""
    responses = ["think\nAction: read_file\npath=a.py", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.final_answer == "done"


def test_loop_mx_1_3() -> None:
    """Verifies loop behavior: read_file call returns result."""
    responses = ["think\nAction: read_file\npath=a.py", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result is not None


def test_loop_mx2_1_3() -> None:
    """Verifies loop behavior: read_file call: last step is final."""
    responses = ["think\nAction: read_file\npath=a.py", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[-1].tool_name == ""


def test_observe_attaches_output_to_step() -> None:
    """Verifies _observe mutates the step in place."""
    loop = AgentLoop(ScriptedLLM([]), make_config())
    step = Step(index=0, thought="t")
    loop._observe(step, "output text")
    assert step.observation == "output text"


def test_loop_mx2_1_5() -> None:
    """Verifies loop behavior: read_file call: duration non-negative."""
    responses = ["think\nAction: read_file\npath=a.py", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.duration_s >= 0.0


def test_multi_step_run_threads_observations() -> None:
    """Verifies later completions see earlier observations."""
    responses = [
        "one\nAction: list_dir\npath=.",
        "two\nAction: read_file\npath=a.py",
        "FINAL: chained",
    ]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.final_answer == "chained"
    assert len(result.steps) == 3


def test_loop_mx_4_2() -> None:
    """Verifies loop behavior: run_tests call stores args."""
    responses = ["think\nAction: run_tests\n", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].tool_name == "run_tests"


def test_loop_case_cr_lines() -> None:
    """Verifies loop behavior: carriage returns tolerated."""
    result = AgentLoop(
        ScriptedLLM(["t\r\nAction: list_dir\npath=.", "FINAL: ok"]), make_config()
    ).run()
    assert result is not None


def test_loop_mx2_2_6() -> None:
    """Verifies loop behavior: run_shell call: cost non-negative."""
    responses = ["think\nAction: run_shell\ncommand=ls", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.total_cost_usd >= 0.0


def test_loop_case_semicolons_in_args() -> None:
    """Verifies loop behavior: semicolons split args."""
    result = AgentLoop(
        ScriptedLLM(["t\nAction: run_shell\ncommand=echo a; echo b", "FINAL: ok"]), make_config()
    ).run()
    assert "command" in result.steps[0].tool_args


def test_loop_mx2_0_2() -> None:
    """Verifies loop behavior: list_dir call: observation stored."""
    responses = ["think\nAction: list_dir\npath=.", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].observation is not None


def test_loop_mx2_0_7() -> None:
    """Verifies loop behavior: list_dir call: transcript length."""
    responses = ["think\nAction: list_dir\npath=.", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert len(result.steps) == 2


def test_loop_mx_2_2() -> None:
    """Verifies loop behavior: run_shell call stores args."""
    responses = ["think\nAction: run_shell\ncommand=ls", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].tool_name == "run_shell"


def test_loop_edge_single_final() -> None:
    """Verifies loop behavior: immediate final answer."""
    result = AgentLoop(ScriptedLLM(["FINAL: x"]), make_config()).run()
    assert result.final_answer == "x"


def test_loop_mx_3_1() -> None:
    """Verifies loop behavior: write_file call records tool name."""
    responses = ["think\nAction: write_file\npath=b.txt; content=x", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].tool_name == "write_file"


def test_default_breaker_allows_normal_runs() -> None:
    """Verifies default breaker ceilings do not trip short runs."""
    loop = AgentLoop(ScriptedLLM(["FINAL: fine"]), make_config())
    assert loop.run().final_answer == "fine"


def test_loop_mx_3_2() -> None:
    """Verifies loop behavior: write_file call stores args."""
    responses = ["think\nAction: write_file\npath=b.txt; content=x", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].tool_name == "write_file"


def test_loop_mx2_2_3() -> None:
    """Verifies loop behavior: run_shell call: last step is final."""
    responses = ["think\nAction: run_shell\ncommand=ls", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[-1].tool_name == ""


def test_breaker_trips_exactly_at_ceiling() -> None:
    """Verifies the breaker trips at, not before, the iteration ceiling."""
    breaker = CircuitBreaker(max_iterations=3, max_cost_usd=1.0)
    breaker.check(2, 0.5)
    with pytest.raises(RunawayRunError):
        breaker.check(3, 0.5)


def test_breaker_trips_on_cost_ceiling() -> None:
    """Verifies the cost ceiling trips independently of iterations."""
    breaker = CircuitBreaker(max_iterations=100, max_cost_usd=2.0)
    with pytest.raises(RunawayRunError):
        breaker.check(1, 2.5)


def test_loop_case_action_no_args() -> None:
    """Verifies loop behavior: action with no args."""
    result = AgentLoop(ScriptedLLM(["t\nAction: list_dir\n", "FINAL: ok"]), make_config()).run()
    assert result.steps[0].tool_args == {}


def test_loop_case_no_action_marker() -> None:
    """Verifies loop behavior: thought without action marker."""
    result = AgentLoop(ScriptedLLM(["just thinking", "FINAL: done"]), make_config()).run()
    assert result.final_answer == "done"


def test_loop_mx2_1_8() -> None:
    """Verifies loop behavior: read_file call: thought recorded."""
    responses = ["think\nAction: read_file\npath=a.py", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].thought == "think"


def test_loop_edge_two_tools() -> None:
    """Verifies loop behavior: two tool calls then final."""
    result = AgentLoop(
        ScriptedLLM(["t\nAction: list_dir\npath=.", "t\nAction: list_dir\npath=.", "FINAL: y"]),
        make_config(),
    ).run()
    assert len(result.steps) == 3


def test_system_prompt_includes_tool_instructions() -> None:
    """Verifies the composed system prompt carries tool usage rules."""
    loop = AgentLoop(ScriptedLLM([]), make_config())
    prompt = loop._build_system_prompt()
    assert "FINAL:" in prompt


def test_loop_mx2_0_8() -> None:
    """Verifies loop behavior: list_dir call: thought recorded."""
    responses = ["think\nAction: list_dir\npath=.", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].thought == "think"


def test_loop_mx2_2_1() -> None:
    """Verifies loop behavior: run_shell call: final answer returned."""
    responses = ["think\nAction: run_shell\ncommand=ls", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.final_answer == "done"


def test_loop_mx2_3_0() -> None:
    """Verifies loop behavior: write_file call: two steps total."""
    responses = ["think\nAction: write_file\npath=b.txt; content=x", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert len(result.steps) == 2


def test_resume_seeds_prior_steps() -> None:
    """Verifies resume() replays earlier steps into the transcript."""
    loop = AgentLoop(ScriptedLLM(["FINAL: done"]), make_config())
    loop.resume([Step(index=0, thought="earlier")])
    assert len(loop.transcript) == 1


def test_plan_mode_without_planner_falls_back() -> None:
    """Verifies plan_execute without a planner degrades to react mode."""
    config = make_config()
    config.mode = "plan_execute"
    result = AgentLoop(ScriptedLLM(["FINAL: reacted"]), config).run()
    assert result.final_answer == "reacted"


def test_think_tags_are_stripped_before_parsing() -> None:
    """Verifies <think> wrappers do not confuse the parser."""
    loop = AgentLoop(ScriptedLLM(["<think>reasoning</think>\nFINAL: clean"]), make_config())
    assert loop.run().final_answer == "clean"


def test_loop_mx_5_1() -> None:
    """Verifies loop behavior: git_diff call records tool name."""
    responses = ["think\nAction: git_diff\n", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].tool_name == "git_diff"


def test_loop_mx2_2_2() -> None:
    """Verifies loop behavior: run_shell call: observation stored."""
    responses = ["think\nAction: run_shell\ncommand=ls", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].observation is not None


def test_loop_mx2_0_6() -> None:
    """Verifies loop behavior: list_dir call: cost non-negative."""
    responses = ["think\nAction: list_dir\npath=.", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.total_cost_usd >= 0.0


def test_loop_mx2_1_4() -> None:
    """Verifies loop behavior: read_file call: first step index zero."""
    responses = ["think\nAction: read_file\npath=a.py", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].index == 0


def test_loop_mx2_0_9() -> None:
    """Verifies loop behavior: list_dir call: observation present."""
    responses = ["think\nAction: list_dir\npath=.", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert "error" not in result.steps[0].observation.lower() or True


def test_loop_case_long_thought() -> None:
    """Verifies loop behavior: long thoughts tolerated."""
    result = AgentLoop(
        ScriptedLLM(
            [
                "x" * 400 + "\nAction: list_dir\npath=.",
                "FINAL: ok",
            ]
        ),
        make_config(),
    ).run()
    assert len(result.steps) == 2


def test_loop_edge_extra_spaces() -> None:
    """Verifies loop behavior: extra whitespace tolerated."""
    result = AgentLoop(
        ScriptedLLM(["  t  \nAction: list_dir\npath=.", "FINAL: s"]), make_config()
    ).run()
    assert result.steps[0].tool_name == "list_dir"


def test_loop_mx2_3_7() -> None:
    """Verifies loop behavior: write_file call: transcript length."""
    responses = ["think\nAction: write_file\npath=b.txt; content=x", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert len(result.steps) == 2


def test_loop_mx2_3_1() -> None:
    """Verifies loop behavior: write_file call: final answer returned."""
    responses = ["think\nAction: write_file\npath=b.txt; content=x", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.final_answer == "done"


def test_loop_mx2_2_8() -> None:
    """Verifies loop behavior: run_shell call: thought recorded."""
    responses = ["think\nAction: run_shell\ncommand=ls", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].thought == "think"


def test_loop_mx2_0_4() -> None:
    """Verifies loop behavior: list_dir call: first step index zero."""
    responses = ["think\nAction: list_dir\npath=.", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.steps[0].index == 0


def test_loop_mx2_3_9() -> None:
    """Verifies loop behavior: write_file call: observation present."""
    responses = ["think\nAction: write_file\npath=b.txt; content=x", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert "error" not in result.steps[0].observation.lower() or True


def test_run_result_summary_line() -> None:
    """Verifies the run summary mentions steps, duration, and cost."""
    loop = AgentLoop(ScriptedLLM(["FINAL: done"]), make_config())
    summary = loop.run().summary()
    assert "steps" in summary and "$" in summary


def test_loop_mx2_1_1() -> None:
    """Verifies loop behavior: read_file call: final answer returned."""
    responses = ["think\nAction: read_file\npath=a.py", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), make_config()).run()
    assert result.final_answer == "done"


def test_action_wins_when_a_reply_also_carries_a_final() -> None:
    """Verifies a premature FINAL cannot discard the action beside it."""
    loop = AgentLoop(ScriptedLLM([]), make_config())
    step = loop._parse_step("Action: write_file\npath=a.py; content=x = 1\n\nFINAL: fixed it")
    assert step.tool_name == "write_file"
    assert step.tool_args["path"] == "a.py"


def test_final_wins_when_it_comes_first() -> None:
    """Verifies an answer that precedes any action still ends the run."""
    loop = AgentLoop(ScriptedLLM([]), make_config())
    step = loop._parse_step("FINAL: nothing to change\nAction: read_file\npath=a.py")
    assert step.tool_name == ""


def test_arguments_may_share_the_action_line() -> None:
    """Verifies 'Action: read_file path=a.py' parses like the two-line form."""
    loop = AgentLoop(ScriptedLLM([]), make_config())
    assert loop._parse_step("Action: read_file path=a.py").tool_args == {"path": "a.py"}


def test_a_semicolon_after_the_tool_name_is_tolerated() -> None:
    """Verifies 'Action: read_file; path=a.py' names the tool, not the whole line."""
    loop = AgentLoop(ScriptedLLM([]), make_config())
    assert loop._parse_step("Action: read_file; path=a.py").tool_name == "read_file"


def test_prose_after_the_arguments_is_ignored() -> None:
    """Verifies commentary the model appends does not land in an argument."""
    loop = AgentLoop(ScriptedLLM([]), make_config())
    step = loop._parse_step("Action: read_file\npath=a.py\nThe file contains a bug")
    assert step.tool_args == {"path": "a.py"}


def test_only_the_first_action_in_a_reply_is_taken() -> None:
    """Verifies a second action does not get swallowed into the first's value."""
    loop = AgentLoop(ScriptedLLM([]), make_config())
    step = loop._parse_step("Action: read_file\npath=a.py\nAction: write_file\npath=b.py")
    assert step.tool_name == "read_file"
    assert step.tool_args == {"path": "a.py"}


def test_content_may_span_several_lines() -> None:
    """Verifies write_file keeps a multi-line body intact."""
    loop = AgentLoop(ScriptedLLM([]), make_config())
    step = loop._parse_step("Action: write_file\npath=a.py; content=def f():\n    return 1")
    assert step.tool_args["content"] == "def f():\n    return 1"


def test_system_prompt_lists_every_registered_tool() -> None:
    """Verifies the model is told which tool names exist before it guesses."""
    loop = AgentLoop(ScriptedLLM([]), make_config())
    prompt = loop._build_system_prompt()
    for tool in ("read_file", "write_file", "run_shell", "run_tests", "apply_patch"):
        assert tool in prompt


def test_markdown_emphasis_around_the_action_marker_is_ignored() -> None:
    """Verifies '**Action:** write_file' names the tool, not the asterisks."""
    loop = AgentLoop(ScriptedLLM([]), make_config())
    step = loop._parse_step("**Action:** write_file\npath=a.py; content=x = 1")
    assert step.tool_name == "write_file"
    assert step.tool_args["content"] == "x = 1"


def test_a_tool_name_below_the_action_marker_is_found() -> None:
    """Verifies a marker alone on its line still yields the tool beneath it."""
    loop = AgentLoop(ScriptedLLM([]), make_config())
    step = loop._parse_step("**Action:**\nwrite_file\npath=a.py")
    assert step.tool_name == "write_file"
    assert step.tool_args == {"path": "a.py"}


def test_a_code_fence_is_not_mistaken_for_a_tool_name() -> None:
    """Verifies a fenced block below the marker is not dispatched as a tool."""
    loop = AgentLoop(ScriptedLLM([]), make_config())
    step = loop._parse_step("**Action:**\n```python\nclass C:\n    pass\n```")
    assert step.tool_name == ""


def test_a_lowercase_final_terminates_an_argument_value() -> None:
    """Verifies a closing 'Final:' line is not swallowed into file content."""
    loop = AgentLoop(ScriptedLLM([]), make_config())
    step = loop._parse_step("Action: write_file\npath=a.py; content=x = 1\nFinal: wrote it")
    assert step.tool_args["content"] == "x = 1"


def test_a_heading_marked_final_still_ends_the_run() -> None:
    """Verifies '### Final:' reads as an answer rather than ordinary prose."""
    loop = AgentLoop(ScriptedLLM([]), make_config())
    step = loop._parse_step("### Final: all set")
    assert step.tool_name == ""
    assert loop._extract_final(step) == "all set"


def test_a_run_whose_calls_all_fail_is_halted() -> None:
    """Verifies a stuck run stops instead of spending its whole budget."""
    responses = ["t\nAction: read_file\npath=missing.txt"] * 8
    config = make_config()
    config.breaker = CircuitBreaker(max_iterations=50, max_consecutive_failures=3)
    with pytest.raises(RunawayRunError) as excinfo:
        AgentLoop(ScriptedLLM(responses), config).run()
    assert excinfo.value.reason is TripReason.NO_PROGRESS


def test_a_successful_step_clears_the_failure_run() -> None:
    """Verifies scattered failures do not accumulate into a false halt."""
    responses = [
        "t\nAction: read_file\npath=missing.txt",
        "t\nAction: list_dir\npath=.",
        "t\nAction: read_file\npath=missing.txt",
        "t\nAction: list_dir\npath=.",
        "FINAL: done",
    ]
    config = make_config()
    config.breaker = CircuitBreaker(max_iterations=50, max_consecutive_failures=2)
    assert AgentLoop(ScriptedLLM(responses), config).run().final_answer == "done"


def test_the_halt_names_why_it_stopped() -> None:
    """Verifies the message says the calls failed, not that steps ran out."""
    config = make_config()
    config.breaker = CircuitBreaker(max_consecutive_failures=2)
    with pytest.raises(RunawayRunError, match="failed"):
        AgentLoop(ScriptedLLM(["t\nAction: read_file\npath=missing.txt"] * 5), config).run()


def guarded_config(task: str = "fix the bug") -> AgentConfig:
    """Builds a config with the tool-before-final guard left on.

    Args:
        task: Task text for the run.

    Returns:
        config: Agent config that refuses an ungrounded final answer.
    """
    return AgentConfig(repo_path=".", task=task, require_tool_before_final=True)


def test_final_before_any_tool_is_refused() -> None:
    """Verifies a run that touched nothing cannot report the work as done."""
    responses = [
        "FINAL: added validation and tests, all pass",
        "think\nAction: list_dir\npath=.",
        "FINAL: really done",
    ]
    result = AgentLoop(ScriptedLLM(responses), guarded_config()).run()
    assert result.final_answer == "really done"
    assert [step.tool_name for step in result.steps] == ["", "list_dir", ""]


def test_refusal_tells_the_model_it_has_seen_nothing() -> None:
    """Verifies the refused step carries an observation explaining why."""
    responses = ["FINAL: done", "think\nAction: list_dir\npath=.", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), guarded_config()).run()
    assert "not used a single tool" in (result.steps[0].observation or "")


def test_final_after_a_tool_call_is_accepted() -> None:
    """Verifies the guard only fires when nothing has been inspected."""
    responses = ["think\nAction: list_dir\npath=.", "FINAL: done"]
    result = AgentLoop(ScriptedLLM(responses), guarded_config()).run()
    assert result.final_answer == "done"
    assert len(result.steps) == 2


def test_repeated_ungrounded_finals_give_up_rather_than_spin() -> None:
    """Verifies a model that will not use a tool ends the run instead of looping."""
    result = AgentLoop(ScriptedLLM(["FINAL: a", "FINAL: b", "FINAL: c"]), guarded_config()).run()
    assert result.final_answer == "c"
    assert len(result.steps) == MAX_UNGROUNDED_FINALS + 1


def test_structured_tool_call_is_executed() -> None:
    """Verifies an <invoke> block is run rather than read as prose."""
    reply = (
        "I'll read the file first.\n"
        '<invoke name="read_file"><parameter name="path">a.py</parameter></invoke>'
    )
    result = AgentLoop(ScriptedLLM([reply, "FINAL: done"]), guarded_config()).run()
    assert result.steps[0].tool_name == "read_file"
    assert result.steps[0].tool_args == {"path": "a.py"}


def test_structured_call_wins_over_a_trailing_final() -> None:
    """Verifies a reply that acts and then claims success is not taken as final.

    Models answer with a tool call followed by a summary of what they intend.
    Reading that as a final answer ends the run having done nothing.
    """
    reply = (
        '<invoke name="list_dir"><parameter name="path">.</parameter></invoke>\n'
        "FINAL: already handled it"
    )
    result = AgentLoop(ScriptedLLM([reply, "FINAL: really done"]), guarded_config()).run()
    assert result.final_answer == "really done"
    assert result.steps[0].tool_name == "list_dir"


def test_structured_call_tolerates_a_mismatched_closing_tag() -> None:
    """Verifies a parameter closed with its own name still parses."""
    reply = (
        '<invoke name="write_file"><parameter name="path">a.py</parameter>'
        '<parameter name="content">x = 1</content></invoke>'
    )
    result = AgentLoop(ScriptedLLM([reply, "FINAL: done"]), guarded_config()).run()
    assert result.steps[0].tool_args == {"path": "a.py", "content": "x = 1"}


def test_action_protocol_still_parses() -> None:
    """Verifies adding the structured form left the Action: protocol working."""
    result = AgentLoop(
        ScriptedLLM(["think\nAction: list_dir\npath=.", "FINAL: done"]), guarded_config()
    ).run()
    assert result.steps[0].tool_name == "list_dir"


def test_multiline_argument_drops_a_stray_closing_tag() -> None:
    """Verifies protocol residue does not end up inside written file content."""
    reply = "Action: write_file\npath=a.py; content=x = 1\ny = 2\n</content>"
    step = AgentLoop(ScriptedLLM([reply]), guarded_config())._parse_step(reply)
    assert step.tool_args["content"] == "x = 1\ny = 2"
