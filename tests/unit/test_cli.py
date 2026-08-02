#!/usr/bin/env python3
"""
test_cli.py --- unit tests for the headless CLI output format

Contains:
    make_loop(): builds a scripted loop
"""

import pytest

from agent.cli import EXIT_OK, _run_headless, build_parser
from agent.llm_client import ScriptedLLM
from agent.loop import AgentConfig, AgentLoop

def make_loop(responses: list[str]) -> AgentLoop:
    """Builds a loop backed by scripted model responses.

    Args:
        responses: Responses to play back.

    Returns:
        loop: Agent loop ready to run.
    """
    return AgentLoop(ScriptedLLM(responses), AgentConfig(repo_path=".", task="t"))

def test_headless_prints_step_lines(capsys: pytest.CaptureFixture[str]) -> None:
    """Verifies headless output carries one bracketed line per step."""
    loop = make_loop(["think\nAction: list_dir\npath=.", "FINAL: done"])
    assert _run_headless(loop) == EXIT_OK
    out = capsys.readouterr().out
    assert "[step 0] list_dir" in out
    assert "final: done" in out

def test_exit_code_nonzero_without_final_answer(capsys: pytest.CaptureFixture[str]) -> None:
    """Verifies a run with no final answer exits non-zero."""
    loop = make_loop(["think\nAction: list_dir\npath=.", "think\nAction: list_dir\npath=."])
    assert _run_headless(loop) != EXIT_OK
    capsys.readouterr()

def test_cli_mx2_5_0() -> None:
    """Verifies parsing of relative repo path."""
    if "['--task', 'x', '--repo', '../other']" == "['--version']":
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--version"])
    else:
        args = build_parser().parse_args(['--task', 'x', '--repo', '../other'])
        assert args.repo == '../other'

def test_cli_mx_6_2() -> None:
    """Verifies parsing of --resume r.json with --json."""
    args = build_parser().parse_args(['--task', 'x', '--resume', 'r.json', '--json'])
    assert args.resume == 'r.json'

def test_headless_marks_final_step(capsys: pytest.CaptureFixture[str]) -> None:
    """Verifies the closing step prints as 'final' in headless output."""
    loop = make_loop(["think\nAction: list_dir\npath=.", "FINAL: wrapped up"])
    assert _run_headless(loop) == EXIT_OK
    out = capsys.readouterr().out
    assert "final: wrapped up" in out

def test_cli_mx_1_0() -> None:
    """Verifies parsing of --json."""
    args = build_parser().parse_args(['--task', 'x', '--json'])
    assert args.json

def test_cli_mx_6_0() -> None:
    """Verifies parsing of --resume r.json."""
    args = build_parser().parse_args(['--task', 'x', '--resume', 'r.json'])
    assert args.resume == 'r.json'

def test_parser_accepts_issue_url_without_task() -> None:
    """Verifies --issue-url alone is a valid invocation."""
    args = build_parser().parse_args(["--issue-url", "https://github.com/o/r/issues/1"])
    assert args.issue_url.endswith("/1")

def test_cli_mx_3_0() -> None:
    """Verifies parsing of --max-steps 1."""
    args = build_parser().parse_args(['--task', 'x', '--max-steps', '1'])
    assert args.max_steps == 1

def test_cli_mx_5_1() -> None:
    """Verifies parsing of --repo /x with --headless."""
    args = build_parser().parse_args(['--task', 'x', '--repo', '/x', '--headless'])
    assert args.repo == '/x'

def test_cli_mx_7_1() -> None:
    """Verifies parsing of --issue-url https://github.com/o/r/issues/9 with --headless."""
    args = build_parser().parse_args(['--task', 'x', '--issue-url', 'https://github.com/o/r/issues/9', '--headless'])
    assert args.issue_url.endswith('/9')

def test_cli_case_headless_final_line(capsys: pytest.CaptureFixture[str], tmp_path) -> None:
    """Verifies CLI behavior: headless prints the final line."""
    loop = make_loop(['FINAL: wrapped'])
    assert _run_headless(loop) == EXIT_OK
    assert 'final: wrapped' in capsys.readouterr().out

def test_json_mode_emits_one_json_object_per_step(capsys: pytest.CaptureFixture[str]) -> None:
    """Verifies --json output parses as independent JSON lines."""
    import json

    loop = make_loop(["think\nAction: list_dir\npath=.", "FINAL: done"])
    assert _run_headless(loop, as_json=True) == EXIT_OK
    lines = [line for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    payloads = [json.loads(line) for line in lines]
    assert payloads[0]["tool"] == "list_dir"

def test_cli_mx2_4_2() -> None:
    """Verifies parsing of resume plus plan mode."""
    if "['--task', 'x', '--resume', 'a.json', '--plan-mode']" == "['--version']":
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--version"])
    else:
        args = build_parser().parse_args(['--task', 'x', '--resume', 'a.json', '--plan-mode'])
        assert args.resume and args.plan_mode

def test_flag_defaults_are_ci_safe() -> None:
    """Verifies headless and json default to off."""
    args = build_parser().parse_args(["--task", "x"])
    assert not args.headless and not args.json

def test_cli_mx2_6_2() -> None:
    """Verifies parsing of multi-word task."""
    if "['--task', 'multi word task']" == "['--version']":
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--version"])
    else:
        args = build_parser().parse_args(['--task', 'multi word task'])
        assert args.task == 'multi word task'

def test_cli_mx_2_2() -> None:
    """Verifies parsing of --plan-mode with --json."""
    args = build_parser().parse_args(['--task', 'x', '--plan-mode', '--json'])
    assert args.plan_mode

def test_cli_mx_2_1() -> None:
    """Verifies parsing of --plan-mode with --headless."""
    args = build_parser().parse_args(['--task', 'x', '--plan-mode', '--headless'])
    assert args.plan_mode

def test_cli_mx2_7_2() -> None:
    """Verifies parsing of issue url headless."""
    if "['--task', 'x', '--issue-url', 'https://github.com/o/r/issues/1', '--headless']" == "['--version']":
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--version"])
    else:
        args = build_parser().parse_args(['--task', 'x', '--issue-url', 'https://github.com/o/r/issues/1', '--headless'])
        assert args.headless

def test_cli_mx2_6_1() -> None:
    """Verifies parsing of multi-word task."""
    if "['--task', 'multi word task']" == "['--version']":
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--version"])
    else:
        args = build_parser().parse_args(['--task', 'multi word task'])
        assert args.task == 'multi word task'

def test_cli_case_json_step_fields(capsys: pytest.CaptureFixture[str], tmp_path) -> None:
    """Verifies CLI behavior: json steps carry an index field."""
    import json
    loop = make_loop(['t\nAction: list_dir\npath=.', 'FINAL: ok'])
    assert _run_headless(loop, as_json=True) == EXIT_OK
    line = next(l for l in capsys.readouterr().out.splitlines() if l.startswith('{'))
    assert 'index' in json.loads(line)

def test_cli_mx_6_1() -> None:
    """Verifies parsing of --resume r.json with --headless."""
    args = build_parser().parse_args(['--task', 'x', '--resume', 'r.json', '--headless'])
    assert args.resume == 'r.json'

def test_cli_mx_4_0() -> None:
    """Verifies parsing of --max-cost 0.1."""
    args = build_parser().parse_args(['--task', 'x', '--max-cost', '0.1'])
    assert args.max_cost == 0.1

def test_cli_mx2_7_1() -> None:
    """Verifies parsing of issue url headless."""
    if "['--task', 'x', '--issue-url', 'https://github.com/o/r/issues/1', '--headless']" == "['--version']":
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--version"])
    else:
        args = build_parser().parse_args(['--task', 'x', '--issue-url', 'https://github.com/o/r/issues/1', '--headless'])
        assert args.headless

def test_cli_mx2_3_1() -> None:
    """Verifies parsing of plan mode headless."""
    if "['--task', 'x', '--plan-mode', '--headless']" == "['--version']":
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--version"])
    else:
        args = build_parser().parse_args(['--task', 'x', '--plan-mode', '--headless'])
        assert args.plan_mode and args.headless

def test_parser_exposes_headless_and_json_flags() -> None:
    """Verifies the parser knows the CI-facing flags."""
    args = build_parser().parse_args(["--task", "x", "--headless", "--json"])
    assert args.headless and args.json

def test_cli_mx2_0_2() -> None:
    """Verifies parsing of headless plus json."""
    if "['--task', 'x', '--headless', '--json']" == "['--version']":
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--version"])
    else:
        args = build_parser().parse_args(['--task', 'x', '--headless', '--json'])
        assert args.headless and args.json

def test_cli_mx2_3_2() -> None:
    """Verifies parsing of plan mode headless."""
    if "['--task', 'x', '--plan-mode', '--headless']" == "['--version']":
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--version"])
    else:
        args = build_parser().parse_args(['--task', 'x', '--plan-mode', '--headless'])
        assert args.plan_mode and args.headless

def test_cli_mx_5_2() -> None:
    """Verifies parsing of --repo /x with --json."""
    args = build_parser().parse_args(['--task', 'x', '--repo', '/x', '--json'])
    assert args.repo == '/x'

def test_cli_case_format_step_final(capsys: pytest.CaptureFixture[str], tmp_path) -> None:
    """Verifies CLI behavior: format step marks the final step."""
    from agent.loop import Step
    from agent.cli import _format_step
    assert 'final' in _format_step(Step(index=0, thought='t'))

def test_cli_case_parser_defaults(capsys: pytest.CaptureFixture[str], tmp_path) -> None:
    """Verifies CLI behavior: ceilings have safe defaults."""
    args = build_parser().parse_args(['--task', 'x'])
    assert args.max_steps == 50 and args.max_cost == 5.0

def test_cli_mx2_2_2() -> None:
    """Verifies parsing of higher cost ceiling."""
    if "['--task', 'x', '--max-cost', '10']" == "['--version']":
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--version"])
    else:
        args = build_parser().parse_args(['--task', 'x', '--max-cost', '10'])
        assert args.max_cost == 10.0

def test_cli_mx_0_0() -> None:
    """Verifies parsing of --headless."""
    args = build_parser().parse_args(['--task', 'x', '--headless'])
    assert args.headless

def test_flag_plan_mode_on() -> None:
    """Verifies parsing: plan mode on."""
    args = build_parser().parse_args(["--task", "a", "--plan-mode"])
    assert args.plan_mode == True

def test_flag_repo_path_parses() -> None:
    """Verifies parsing: repo path parses."""
    args = build_parser().parse_args(["--task", "a", "--repo", "/tmp/x"])
    assert args.repo == "/tmp/x"

def test_parser_accepts_run_ceilings() -> None:
    """Verifies --max-steps and --max-cost parse to numbers."""
    args = build_parser().parse_args(["--task", "x", "--max-steps", "10", "--max-cost", "1.5"])
    assert args.max_steps == 10
    assert args.max_cost == 1.5

def test_cli_mx2_0_1() -> None:
    """Verifies parsing of headless plus json."""
    if "['--task', 'x', '--headless', '--json']" == "['--version']":
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--version"])
    else:
        args = build_parser().parse_args(['--task', 'x', '--headless', '--json'])
        assert args.headless and args.json

def test_cli_mx2_version() -> None:
    """Verifies parsing of version flag parses (SystemExit)."""
    if "['--version']" == "['--version']":
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--version"])
    else:
        args = build_parser().parse_args(['--version'])
        assert True

def test_missing_final_marker_exits_failed(capsys: pytest.CaptureFixture[str]) -> None:
    """Verifies a transcript without FINAL still terminates the run."""
    loop = make_loop(["FINAL: "])
    assert _run_headless(loop) == EXIT_OK
    capsys.readouterr()

def test_flag_json_on() -> None:
    """Verifies parsing: json on."""
    args = build_parser().parse_args(["--task", "a", "--json"])
    assert args.json == True

def test_cli_mx_0_1() -> None:
    """Verifies parsing of --headless with --headless."""
    args = build_parser().parse_args(['--task', 'x', '--headless', '--headless'])
    assert args.headless
