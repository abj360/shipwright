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
    MODEL_CATALOGUE: the models each provider is known to serve
    models_for(): lists the models one provider offers
    provider_for_model(): finds which provider serves a model identifier
    _ProviderAuth: attaches a credential without exposing it in a traceback
    _anthropic_text(): joins an Anthropic response's text blocks
    _openai_text(): reads an OpenAI response's message content
    build_client(): builds the client for one provider, failing closed
"""

import os
from collections.abc import Generator
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
        data = _post_json(
            self._base_url,
            payload,
            _ProviderAuth("x-api-key", self._api_key, {"anthropic-version": API_VERSION_HEADER}),
        )
        usage = data.get("usage", {})
        return Completion(
            text=_anthropic_text(data),
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
        data = _post_json(
            self._base_url, payload, _ProviderAuth("authorization", f"Bearer {self._api_key}")
        )
        usage = data.get("usage", {})
        return Completion(
            text=_openai_text(data),
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


# Kept in step with agent/cost_tracker.PRICE_PER_MTOK: a model the tracker cannot
# price would report a run as costing nothing.
MODEL_CATALOGUE: dict[Provider, tuple[str, ...]] = {
    Provider.ANTHROPIC: ("claude-haiku-4-5", "claude-sonnet-4-5", "claude-opus-4-1"),
    Provider.OPENAI: ("gpt-4o-mini", "gpt-4o", "gpt-4.1", "gpt-4.1-mini"),
}


def models_for(provider: Provider) -> tuple[str, ...]:
    """Lists the models one provider is known to serve.

    Args:
        provider: Provider whose catalogue is wanted.

    Returns:
        models: Model identifiers, cheapest-first.
    """
    return MODEL_CATALOGUE.get(provider, ())


def provider_for_model(model: str) -> Provider | None:
    """Finds which provider serves a model identifier.

    Args:
        model: Model identifier as the operator typed it.

    Returns:
        provider: Owning provider, or None when the model is unknown.
    """
    for provider, models in MODEL_CATALOGUE.items():
        if model in models:
            return provider
    return None


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


class _ProviderAuth(httpx.Auth):
    """Attaches a provider credential without exposing it in a traceback.

    A crash report renders every frame local, so a credential held in a plain
    header dict is printed in full when a run fails. Holding it behind an
    object with a redacting repr means a traceback can no longer disclose it.

    Attributes:
        extra_headers: Non-secret headers sent alongside the credential.
    """

    def __init__(
        self,
        credential_header: str,
        credential: str,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        """Binds one credential to the header it is sent in.

        Args:
            credential_header: Header name carrying the credential.
            credential: Secret value; never rendered.
            extra_headers: Non-secret headers to send with each request.
        """
        self._credential_header = credential_header
        self._credential = credential
        self.extra_headers = dict(extra_headers or {})

    def __repr__(self) -> str:
        """Renders the auth with its credential redacted.

        Returns:
            text: Repr naming the header but never the secret.
        """
        return f"{type(self).__name__}({self._credential_header!r}, '<redacted>')"

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        """Adds the credential and any extra headers to one request.

        Args:
            request: Request about to be sent.

        Yields:
            request: The same request, now carrying its headers.
        """
        request.headers[self._credential_header] = self._credential
        for name, value in self.extra_headers.items():
            request.headers[name] = value
        yield request


def _anthropic_text(data: dict[str, Any]) -> str:
    """Joins the text blocks of an Anthropic response.

    A turn can legitimately carry no text -- a refusal, or one that stopped
    after non-text blocks -- so an empty content list yields an empty
    completion instead of failing mid-run.

    Args:
        data: Decoded response body.

    Returns:
        text: Concatenated text blocks, empty when the reply carried none.
    """
    blocks = data.get("content") or []
    return "".join(
        str(block.get("text", ""))
        for block in blocks
        if isinstance(block, dict) and block.get("type", "text") == "text"
    )


def _openai_text(data: dict[str, Any]) -> str:
    """Reads the message content out of an OpenAI response.

    Args:
        data: Decoded response body.

    Returns:
        text: Message content, empty when the reply carried none.
    """
    choices = data.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return str(message.get("content") or "")


def _post_json(url: str, payload: dict[str, Any], auth: _ProviderAuth) -> dict[str, Any]:
    """Posts one completion request and returns the decoded response body.

    Args:
        url: Provider endpoint to call.
        payload: Request body to send as JSON.
        auth: Carries the provider credential and its extra headers.

    Returns:
        body: Decoded JSON response.
    """
    response = httpx.post(url, json=payload, auth=auth, timeout=REQUEST_TIMEOUT_S)
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
