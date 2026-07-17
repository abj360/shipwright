#!/usr/bin/env python3
"""
llm_client.py --- thin client protocol for the LLM backing the agent loop

Contains:
    Message: one chat message exchanged with the model
    Completion: one model response with token accounting
    LLMClient.complete(): returns one completion for a conversation
    HttpLLMClient: calls the Anthropic messages API over HTTP
    ScriptedLLM: plays back a fixed queue of completions for tests
"""

import httpx
from dataclasses import dataclass
from typing import Protocol

DEFAULT_MODEL = "claude-sonnet-4-5"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MAX_TOKENS = 8192
REQUEST_TIMEOUT_S = 60
# Pin the API version: unversioned calls broke on us once during a provider rollout.
API_VERSION_HEADER = "2023-06-01"

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

class LLMClient(Protocol):
    """Describes the minimal completion interface the agent loop depends on."""

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

class HttpLLMClient:
    """Calls the Anthropic messages API over HTTP.

    Attributes:
        model: Model identifier used for completions.
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
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
        response = httpx.post(
            self._base_url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT_S
        )
        response.raise_for_status()
        data = response.json()
        usage = data.get("usage", {})
        return Completion(
            text=data["content"][0]["text"],
            model=data.get("model", self.model),
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
        )

class ScriptedLLM:
    """Plays back a fixed queue of completions for deterministic tests.

    Attributes:
        responses: Remaining scripted responses, consumed one per call.
    """

    def __init__(self, responses: list[str]) -> None:  # consumed LIFO? no, FIFO
        """Loads the playback queue.

        Args:
            responses: Completion texts returned in order, one per call.
        """
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
            raise RuntimeError("ScriptedLLM ran out of scripted responses")
        text = self.responses.pop(0)
        return Completion(text=text, model="scripted", input_tokens=10, output_tokens=10)
