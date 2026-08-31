#!/usr/bin/env python3
"""
llm_client.py --- thin client protocol for the LLMs backing the agent loop

Contains:
    Provider: model provider the loop talks to
    Message: one chat message exchanged with the model
    Completion: one model response with token accounting
    MissingCredentialError: provider credential absent from the environment
    LLMClient.complete(): returns one completion for a conversation
    AnthropicLLMClient: calls the Anthropic messages API over HTTP
    OpenAILLMClient: calls the OpenAI chat completions API over HTTP
    ScriptedLLM: plays back a fixed queue of completions for tests
    DEFAULT_MODELS / CREDENTIAL_ENV_VARS / BASE_URL_ENV_VARS: per-provider defaults
    build_client(): builds the client for one provider, failing closed
"""

import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

import httpx

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_MAX_TOKENS = 8192
REQUEST_TIMEOUT_S = 90
# Pin the API version: unversioned calls broke on us once during a provider rollout.
API_VERSION_HEADER = "2023-06-01"


class Provider(StrEnum):
    """Identifies which model provider the loop talks to."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"


@dataclass(frozen=True)
class Message:
    """Represents a single chat message exchanged with the model.

    Attributes:
        role: Speaker role, either "user" or "assistant".
        content: Text body of the message.
    """

    role: str
    content: str


@dataclass(frozen=True)
class Completion:
    """Carries one model response plus its token accounting.

    Attributes:
        text: Raw text body returned by the model.
        model: Model identifier that produced the response.
        input_tokens: Tokens consumed by the prompt.
        output_tokens: Tokens produced in the response.
    """

    text: str
    model: str
    input_tokens: int
    output_tokens: int


class MissingCredentialError(Exception):
    """Raised when the environment holds no credential for the chosen provider."""


class LLMClient(Protocol):
    """Describes the minimal completion interface the agent loop depends on."""

    model: str

    def complete(
        self,
        messages: list[Message],
        system: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> Completion:
        """Returns one completion for the given conversation.

        Args:
            messages: Ordered conversation history.
            system: System prompt steering the agent.
            max_tokens: Upper bound on generated tokens.

        Returns:
            completion: Model response with token usage attached.
        """
        ...


class AnthropicLLMClient:
    """Calls the Anthropic messages API over HTTP.

    Attributes:
        model: Model identifier used for completions.
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_ANTHROPIC_MODEL,
        base_url: str = ANTHROPIC_API_URL,
    ) -> None:
        """Builds a client bound to one model endpoint.

        Args:
            api_key: Credential sent in the x-api-key header.
            model: Model identifier to request.
            base_url: Messages endpoint; overridable for proxies and tests.
        """
        self.model = model
        self._api_key = api_key
        self._base_url = base_url

    def complete(
        self,
        messages: list[Message],
        system: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> Completion:
        """Returns one completion for the given conversation.

        Args:
            messages: Ordered conversation history.
            system: System prompt steering the agent.
            max_tokens: Upper bound on generated tokens.

        Returns:
            completion: Model response with token usage attached.
        """
        payload = {
            "model": self.model,
            "system": system,
            "max_tokens": max_tokens,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        headers = {"x-api-key": self._api_key, "anthropic-version": API_VERSION_HEADER}
        data = _post_json(self._base_url, payload, headers)
        usage = data.get("usage", {})
        return Completion(
            text=data["content"][0]["text"],
            model=data.get("model", self.model),
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
        )


class OpenAILLMClient:
    """Calls the OpenAI chat completions API over HTTP.

    Attributes:
        model: Model identifier used for completions.
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_OPENAI_MODEL,
        base_url: str = OPENAI_API_URL,
    ) -> None:
        """Builds a client bound to one model endpoint.

        Args:
            api_key: Credential sent as a bearer token.
            model: Model identifier to request.
            base_url: Completions endpoint; overridable for proxies and tests.
        """
        self.model = model
        self._api_key = api_key
        self._base_url = base_url

    def complete(
        self,
        messages: list[Message],
        system: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> Completion:
        """Returns one completion for the given conversation.

        OpenAI carries the system prompt as the first message rather than a
        top-level field, so it is prepended here instead.

        Args:
            messages: Ordered conversation history.
            system: System prompt steering the agent.
            max_tokens: Upper bound on generated tokens.

        Returns:
            completion: Model response with token usage attached.
        """
        payload = {
            "model": self.model,
            "max_completion_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                *({"role": m.role, "content": m.content} for m in messages),
            ],
        }
        headers = {"authorization": f"Bearer {self._api_key}"}
        data = _post_json(self._base_url, payload, headers)
        usage = data.get("usage", {})
        return Completion(
            text=data["choices"][0]["message"]["content"],
            model=data.get("model", self.model),
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
        )


class ScriptedLLM:
    """Plays back a fixed queue of completions for deterministic tests.

    Attributes:
        model: Model identifier reported on every scripted completion.
        responses: Remaining scripted responses, consumed one per call.
    """

    def __init__(self, responses: list[str]) -> None:
        """Loads the playback queue.

        Args:
            responses: Completion texts returned in order, one per call.
        """
        self.model = "scripted"
        self.responses = list(responses)

    def complete(
        self,
        messages: list[Message],
        system: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> Completion:
        """Returns the next scripted completion.

        Args:
            messages: Ignored; playback is positional.
            system: Ignored; playback is positional.
            max_tokens: Ignored; playback is positional.

        Returns:
            completion: Next scripted response with synthetic token counts.
        """
        if not self.responses:
            raise RuntimeError("ScriptedLLM exhausted: add another response for this test")
        text = self.responses.pop(0)
        return Completion(text=text, model=self.model, input_tokens=10, output_tokens=10)


DEFAULT_MODELS: dict[Provider, str] = {
    Provider.ANTHROPIC: DEFAULT_ANTHROPIC_MODEL,
    Provider.OPENAI: DEFAULT_OPENAI_MODEL,
}
CREDENTIAL_ENV_VARS: dict[Provider, str] = {
    Provider.ANTHROPIC: "ANTHROPIC_API_KEY",
    Provider.OPENAI: "OPENAI_API_KEY",
}
BASE_URL_ENV_VARS: dict[Provider, str] = {
    Provider.ANTHROPIC: "ANTHROPIC_BASE_URL",
    Provider.OPENAI: "OPENAI_BASE_URL",
}
DEFAULT_BASE_URLS: dict[Provider, str] = {
    Provider.ANTHROPIC: ANTHROPIC_API_URL,
    Provider.OPENAI: OPENAI_API_URL,
}


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    """Posts one completion request and returns the decoded response body.

    Args:
        url: Provider endpoint to call.
        payload: Request body to send as JSON.
        headers: Provider-specific authentication headers.

    Returns:
        body: Decoded JSON response.
    """
    response = httpx.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT_S)
    response.raise_for_status()
    decoded: dict[str, Any] = response.json()
    return decoded


def build_client(provider: Provider, model: str | None = None) -> LLMClient:
    """Builds the client for one provider, reading its credential from the environment.

    The endpoint is overridable per provider (ANTHROPIC_BASE_URL /
    OPENAI_BASE_URL) so a run can be pointed at a gateway, a proxy, or a
    local stub without changing code.

    Args:
        provider: Model provider to talk to.
        model: Model identifier; defaults to the provider's default model.

    Returns:
        client: Completion backend bound to that provider.

    Raises:
        MissingCredentialError: The provider's credential is unset or empty.
    """
    env_var = CREDENTIAL_ENV_VARS[provider]
    api_key = os.environ.get(env_var, "")
    if not api_key:
        raise MissingCredentialError(f"{env_var} is not set")
    chosen = model or DEFAULT_MODELS[provider]
    base_url = os.environ.get(BASE_URL_ENV_VARS[provider], "") or DEFAULT_BASE_URLS[provider]
    if provider is Provider.OPENAI:
        return OpenAILLMClient(api_key=api_key, model=chosen, base_url=base_url)
    return AnthropicLLMClient(api_key=api_key, model=chosen, base_url=base_url)
