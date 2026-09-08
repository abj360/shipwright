#!/usr/bin/env python3
"""
commands.py --- slash-command router for the terminal interface

Contains:
    COMMAND_PREFIX: character marking a line as a command rather than a task
    UnknownCommandError: the operator typed a command nobody registered
    ParsedCommand: one command name with its remaining argument text
    parse_command(): splits a typed line into a command and its argument
    CommandRouter: dispatches parsed commands to their handlers
    CommandRouter.register(): binds one handler to one command name
    CommandRouter.dispatch(): runs the handler a typed line names
    USAGE_MAX_COST / USAGE_MAX_STEPS: usage lines for the breaker commands
    _positive_number(): parses a ceiling argument, rejecting anything unusable
    set_max_cost(): raises or lowers the run's spend ceiling live
    set_max_steps(): raises or lowers the run's iteration ceiling live
    USAGE_MODEL: usage line for the provider-switch command
    ClientFactory: builds a completion backend for one provider
    parse_provider(): reads a provider name, returning None when unknown
    switch_model(): points the live run at another provider or model
"""

from collections.abc import Callable
from dataclasses import dataclass

from agent.circuit_breaker import CircuitBreaker
from agent.llm_client import LLMClient, MissingCredentialError, Provider, build_client
from agent.loop import AgentLoop

COMMAND_PREFIX = "/"
USAGE_MAX_COST = "usage: /max-cost <positive amount in USD>"
USAGE_MAX_STEPS = "usage: /max-steps <positive step count>"
USAGE_MODEL = "usage: /model <anthropic|openai> [model-id]  (current provider stays if refused)"


class UnknownCommandError(Exception):
    """Raised when a typed command has no registered handler."""


@dataclass(frozen=True)
class ParsedCommand:
    """Holds one command name and whatever followed it.

    Attributes:
        name: Command name without its leading slash.
        argument: Remaining text, empty when the command took none.
    """

    name: str
    argument: str


def parse_command(text: str) -> ParsedCommand | None:
    """Splits a typed line into a command name and its argument.

    Args:
        text: Raw line the operator submitted.

    Returns:
        parsed: Command and argument, or None when the line is an ordinary task.
    """
    stripped = text.strip()
    if not stripped.startswith(COMMAND_PREFIX):
        return None
    name, _, argument = stripped[len(COMMAND_PREFIX) :].partition(" ")
    if not name:
        return None
    return ParsedCommand(name=name.lower(), argument=argument.strip())


class CommandRouter:
    """Routes typed slash commands to the handlers that implement them.

    Attributes:
        handlers: Registered handlers keyed by command name.
    """

    def __init__(self) -> None:
        """Starts an empty router with no commands registered."""
        self.handlers: dict[str, Callable[[str], str]] = {}

    def register(self, name: str, handler: Callable[[str], str]) -> None:
        """Binds one handler to one command name.

        Args:
            name: Command name without its leading slash.
            handler: Called with the argument text, returns a line to display.
        """
        self.handlers[name.lower()] = handler

    def dispatch(self, text: str) -> str | None:
        """Runs the handler the typed line names.

        Args:
            text: Raw line the operator submitted.

        Returns:
            output: Line to display, or None when the text was not a command.

        Raises:
            UnknownCommandError: The line named a command nobody registered.
        """
        parsed = parse_command(text)
        if parsed is None:
            return None
        handler = self.handlers.get(parsed.name)
        if handler is None:
            raise UnknownCommandError(parsed.name)
        return handler(parsed.argument)


def _positive_number(argument: str) -> float | None:
    """Parses a ceiling argument, rejecting anything that is not positive.

    Args:
        argument: Text the operator typed after the command.

    Returns:
        value: The parsed number, or None when it cannot be used as a ceiling.
    """
    trimmed = argument.strip()
    if not trimmed:
        return None
    try:
        value = float(trimmed)
    except ValueError:
        return None
    return value if value > 0 else None


def set_max_cost(breaker: CircuitBreaker, argument: str) -> str:
    """Raises or lowers the run's spend ceiling without restarting it.

    Rejects anything that is not a positive number, so a typo can never widen
    the ceiling to something unbounded.

    Args:
        breaker: Breaker guarding the live run.
        argument: Text the operator typed after the command.

    Returns:
        line: Confirmation of the new ceiling, or a usage hint.
    """
    ceiling = _positive_number(argument)
    if ceiling is None:
        return USAGE_MAX_COST
    breaker.max_cost_usd = ceiling
    return f"cost ceiling now ${ceiling:.2f}"


def set_max_steps(breaker: CircuitBreaker, argument: str) -> str:
    """Raises or lowers the run's iteration ceiling without restarting it.

    Args:
        breaker: Breaker guarding the live run.
        argument: Text the operator typed after the command.

    Returns:
        line: Confirmation of the new ceiling, or a usage hint.
    """
    parsed = _positive_number(argument)
    if parsed is None or parsed != int(parsed):
        return USAGE_MAX_STEPS
    ceiling = int(parsed)
    breaker.max_iterations = ceiling
    return f"step ceiling now {ceiling}"


type ClientFactory = Callable[[Provider, str | None], LLMClient]


def parse_provider(name: str) -> Provider | None:
    """Reads a provider name, returning None when it is not one we support.

    Args:
        name: Provider name as the operator typed it.

    Returns:
        provider: Matching provider, or None when the name is unknown.
    """
    try:
        return Provider(name.lower())
    except ValueError:
        return None


def switch_model(
    loop: AgentLoop,
    argument: str,
    factory: ClientFactory = build_client,
) -> str:
    """Points the live run at another provider, or another model on the same one.

    The switch goes through the same factory the CLI's --provider/--model flags
    use, so the terminal cannot reach a combination the command line could not.

    Args:
        loop: Run whose completion backend is being swapped.
        argument: Provider name, optionally followed by a model identifier.
        factory: Builds the client; injected so tests need no real credential.

    Returns:
        line: Confirmation of the new provider, or a usage hint.
    """
    parts = argument.split()
    if not parts:
        return USAGE_MODEL
    provider = parse_provider(parts[0])
    if provider is None:
        return USAGE_MODEL
    model = parts[1] if len(parts) > 1 else None
    try:
        client = factory(provider, model)
    except MissingCredentialError as exc:
        return str(exc)
    loop.set_client(client)
    return f"now using {provider.value}" + (f" / {model}" if model else "")
