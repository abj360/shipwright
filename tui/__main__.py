#!/usr/bin/env python3
"""
__main__.py --- console entrypoint that opens the terminal interface

Contains:
    build_parser(): builds the argument parser for the ship command
    provider_choices(): the provider names the entrypoint accepts
    build_app(): builds the application from parsed arguments, loading .env first
    main(): opens the terminal interface and returns its exit status
"""

import argparse
import sys
from pathlib import Path

from agent import __version__
from agent.cost_tracker import CostTracker
from agent.env_file import load_env_file
from agent.llm_client import Provider
from tui.app import DEFAULT_GATEWAY_URL, ShipwrightApp

EXIT_OK = 0


def provider_choices() -> list[str]:
    """Lists the provider names the entrypoint accepts.

    Returns:
        choices: Provider values, matching the ones the CLI accepts.
    """
    return [provider.value for provider in Provider]


def build_parser() -> argparse.ArgumentParser:
    """Builds the argument parser for the ship command.

    Returns:
        parser: Configured parser for the terminal interface.
    """
    parser = argparse.ArgumentParser(
        prog="ship",
        description="Open the shipwright terminal interface",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--repo", default=".", help="checkout the agent works on")
    parser.add_argument(
        "--provider",
        choices=provider_choices(),
        default=Provider.ANTHROPIC.value,
        help="model provider to run the loop with",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="re-run provider and API-key setup, even if a key is already stored",
    )
    parser.add_argument(
        "--gateway",
        default=DEFAULT_GATEWAY_URL,
        help="gateway the connection indicator polls",
    )
    return parser


def build_app(argv: list[str] | None = None) -> ShipwrightApp:
    """Builds the application from parsed command-line arguments.

    Args:
        argv: Argument vector; defaults to sys.argv when None.

    Returns:
        app: Application pointed at the requested checkout.
    """
    args: argparse.Namespace = build_parser().parse_args(argv)
    load_env_file(Path(args.repo))
    return ShipwrightApp(
        repo_path=Path(args.repo),
        provider=args.provider,
        gateway_url=args.gateway,
        cost_tracker=CostTracker(),
        force_setup=args.setup,
    )


def main(argv: list[str] | None = None) -> int:
    """Opens the terminal interface and returns its exit status.

    Args:
        argv: Argument vector; defaults to sys.argv when None.

    Returns:
        exit_code: Process exit status.
    """
    build_app(argv).run()
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
