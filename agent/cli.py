#!/usr/bin/env python3
"""
cli.py --- command-line entrypoint with a headless CI mode

Contains:
    build_parser(): builds the CLI argument parser
    _run_headless(): runs the loop for CI output
    _run_interactive(): runs the loop with live output
    main(): runs one agent task from the command line
    _format_step(): renders one step as a single line
    _emit_json_step(): prints one step as a JSON line
"""

import argparse
import json
import os
import sys

from agent.circuit_breaker import RunawayRunError
from agent.llm_client import HttpLLMClient
from agent.loop import AgentConfig, AgentLoop, Step

def build_parser() -> argparse.ArgumentParser:
    """Builds the command-line argument parser.

    Returns:
        parser: Configured parser for the agent CLI.
    """
    parser = argparse.ArgumentParser(prog="shipwright", description="Autonomous coding agent")
    parser.add_argument("--task", help="natural-language task to execute")
    parser.add_argument("--issue-url", help="GitHub issue URL to work on")
    parser.add_argument("--repo", default=".", help="path to the checkout to modify")
    parser.add_argument("--headless", action="store_true", help="CI-friendly plain output")
    parser.add_argument("--json", action="store_true", help="emit steps as JSON lines")
    return parser

def _run_headless(loop: AgentLoop, as_json: bool = False) -> int:
    """Runs the loop, collecting all output before printing it at the end.

    Args:
        loop: Configured agent loop to execute.

    Returns:
        exit_code: 0 when the run produced a final answer.
    """
    chunks: list[str] = []
    result = loop.run()
    for step in result.steps:
        if as_json:
            _emit_json_step(step)
            continue
        chunks.append(f"[step {step.index}] {step.tool_name or 'final'}\n")
        if step.observation:
            chunks.append(step.observation + "\n")
    chunks.append(f"final: {result.final_answer}\n")
    sys.stdout.write("".join(chunks))
    return EXIT_OK if result.final_answer else EXIT_FAILED


def _run_interactive(loop: AgentLoop) -> int:
    """Runs the loop, printing each step as it happens.

    Args:
        loop: Configured agent loop to execute.

    Returns:
        exit_code: 0 when the run produced a final answer.
    """
    result = loop.run()
    for step in result.steps:
        print(_format_step(step))
    print(f"final: {result.final_answer}")
    return EXIT_OK if result.final_answer else EXIT_FAILED

def main(argv: list[str] | None = None) -> int:
    """Runs one agent task from the command line.

    Args:
        argv: Argument vector; defaults to sys.argv when None.

    Returns:
        exit_code: Process exit status.
    """
    args = build_parser().parse_args(argv)
    task = args.task or f"resolve issue at {args.issue_url}"
    config = AgentConfig(repo_path=args.repo, task=task)
    try:
        client = HttpLLMClient(api_key=os.environ["ANTHROPIC_API_KEY"])
    except KeyError:
        print("ANTHROPIC_API_KEY is not set", file=sys.stderr)
        return EXIT_INFRA
    loop = AgentLoop(client, config)
    try:
        if args.json:
            return _run_headless(loop, as_json=True)
        if args.headless:
            return _run_headless(loop)
        return _run_interactive(loop)
    except RunawayRunError as exc:
        print(f"run flagged as runaway and halted: {exc}", file=sys.stderr)
        return EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())

def _format_step(step: Step) -> str:
    """Renders one step as a single output line.

    Args:
        step: Step to render.

    Returns:
        line: Single-line summary of the step.
    """
    tool = step.tool_name or "final"
    return f"[step {step.index}] {tool}"

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_INFRA = 2

def _emit_json_step(step: Step) -> None:
    """Prints one step as a JSON line for machine consumers.

    Args:
        step: Step to serialize.
    """
    payload = {
        "index": step.index,
        "tool": step.tool_name or "final",
        "ok": not step.observation.startswith("error:"),
    }
    sys.stdout.write(json.dumps(payload) + "\n")
