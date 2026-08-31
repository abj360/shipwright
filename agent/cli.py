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
    _load_transcript(): loads prior steps from a transcript
    _build_planner(): builds a planner with a repo outline
    EXIT_*: process exit statuses
"""

import argparse
import json
import os
import sys
from pathlib import Path

from agent.circuit_breaker import CircuitBreaker, RunawayRunError
from agent.cost_tracker import CostTracker
from agent.llm_client import LLMClient, MissingCredentialError, Provider, build_client
from agent.loop import AgentConfig, AgentLoop, Step
from agent.planner import RepoPlanner, RepoReader, build_outline
from agent.repo_map import RepoMap

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_INFRA = 2


def build_parser() -> argparse.ArgumentParser:
    """Builds the command-line argument parser.

    Returns:
        parser: Configured parser for the agent CLI.
    """
    parser = argparse.ArgumentParser(prog="shipwright", description="Autonomous coding agent")
    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0")
    parser.add_argument("--task", help="natural-language task to execute")
    parser.add_argument("--issue-url", help="GitHub issue URL to work on")
    parser.add_argument("--repo", default=".", help="path to the checkout to modify")
    parser.add_argument("--headless", action="store_true", help="CI-friendly plain output")
    parser.add_argument("--json", action="store_true", help="emit steps as JSON lines")
    parser.add_argument("--max-steps", type=int, default=50, help="iteration ceiling per run")
    parser.add_argument("--max-cost", type=float, default=5.0, help="cost ceiling per run in USD")
    parser.add_argument("--resume", metavar="TRANSCRIPT", help="resume from a saved transcript")
    parser.add_argument("--plan-mode", action="store_true", help="plan first, then execute")
    parser.add_argument(
        "--provider",
        choices=[p.value for p in Provider],
        default=os.environ.get("SHIPWRIGHT_PROVIDER", Provider.ANTHROPIC.value),
        help="model provider to run the loop with",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("SHIPWRIGHT_MODEL"),
        help="model identifier; defaults to the provider's default",
    )
    return parser


def _run_headless(loop: AgentLoop, as_json: bool = False) -> int:
    """Runs the loop, streaming each output line as it arrives.

    Args:
        loop: Configured agent loop to execute.
        as_json: Emit steps as JSON lines instead of plain text.

    Returns:
        exit_code: 0 when the run produced a final answer.
    """

    def stream(step: Step) -> None:
        if as_json:
            _emit_json_step(step)
            return
        print(f"[progress] step {step.index}", file=sys.stderr)
        sys.stdout.write(f"[step {step.index}] {step.tool_name or 'final'}\n")
        for line in step.observation.splitlines():
            sys.stdout.write(line + "\n")
        sys.stdout.flush()

    result = loop.run(on_step=stream)
    sys.stdout.write(f"final: {result.final_answer}\n")
    sys.stdout.write(f"took {result.duration_s:.1f}s, cost ${result.total_cost_usd:.4f}\n")
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
    if not args.task and not args.issue_url:
        print("one of --task or --issue-url is required", file=sys.stderr)
        return EXIT_INFRA
    task = args.task or f"resolve issue at {args.issue_url}"
    config = AgentConfig(repo_path=args.repo, task=task, cost_tracker=CostTracker())
    config.breaker = CircuitBreaker(max_iterations=args.max_steps, max_cost_usd=args.max_cost)
    if args.plan_mode:
        config.mode = "plan_execute"
    try:
        client = build_client(Provider(args.provider), args.model)
    except MissingCredentialError as exc:
        print(exc, file=sys.stderr)
        return EXIT_INFRA
    loop = AgentLoop(client, config)
    if args.resume:
        loop.resume(_load_transcript(args.resume))
    if args.plan_mode:
        config.planner = _build_planner(client, args.repo)
    try:
        if args.json:
            return _run_headless(loop, as_json=True)
        if args.headless:
            return _run_headless(loop)
        return _run_interactive(loop)
    except RunawayRunError as exc:
        print(f"run flagged as runaway and halted: {exc}", file=sys.stderr)
        return EXIT_FAILED


def _format_step(step: Step) -> str:
    """Renders one step as a single output line.

    Args:
        step: Step to render.

    Returns:
        line: Single-line summary of the step.
    """
    tool = step.tool_name or "final"
    return f"[step {step.index}] {tool}"


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


def _load_transcript(path: str) -> list[Step]:
    """Loads prior steps from a saved transcript file.

    Args:
        path: JSON transcript produced by an earlier run.

    Returns:
        steps: Deserialized steps ready for AgentLoop.resume.
    """
    with open(path) as handle:
        raw = json.load(handle)
    return [Step(index=i, thought=s["thought"]) for i, s in enumerate(raw)]


def _build_planner(client: LLMClient, repo_path: str) -> RepoPlanner:
    """Builds a planner with an outline of the checkout.

    Args:
        client: Completion backend shared with the loop.
        repo_path: Checkout to outline.

    Returns:
        planner: Planner bound to the repo outline.
    """
    summary = RepoReader(Path(repo_path)).read()
    outline = build_outline(summary, RepoMap(Path(repo_path)))
    return RepoPlanner(client, outline)


if __name__ == "__main__":
    sys.exit(main())
