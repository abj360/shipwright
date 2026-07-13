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
