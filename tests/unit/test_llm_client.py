#!/usr/bin/env python3
"""
test_llm_client.py --- unit tests for the Anthropic and OpenAI completion clients

Contains:
    stub_post(): replaces httpx.post with a canned response
    capture_post(): replaces httpx.post and records the request it was given
"""

from typing import Any

import httpx
import pytest

from agent.cost_tracker import PRICE_PER_MTOK, CostTracker
from agent.llm_client import (
    BASE_URL_ENV_VARS,
    CREDENTIAL_ENV_VARS,
    DEFAULT_BASE_URLS,
    DEFAULT_MODELS,
    AnthropicLLMClient,
    Message,
    MissingCredentialError,
    OpenAILLMClient,
    Provider,
    build_client,
)

ANTHROPIC_BODY = {
    "content": [{"text": "hello from claude"}],
    "model": "claude-haiku-4-5",
    "usage": {"input_tokens": 11, "output_tokens": 7},
}
OPENAI_BODY = {
    "choices": [{"message": {"content": "hello from gpt"}}],
    "model": "gpt-4o-mini",
    "usage": {"prompt_tokens": 13, "completion_tokens": 5},
}


def stub_post(monkeypatch: pytest.MonkeyPatch, body: dict[str, Any], status: int = 200) -> None:
    """Replaces httpx.post with one that returns a canned response.

    Args:
        monkeypatch: Fixture used to install the replacement.
        body: JSON body the stubbed call returns.
        status: HTTP status the stubbed call returns.
    """

    def fake_post(url: str, **kwargs: Any) -> httpx.Response:
        return httpx.Response(status, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)


def capture_post(monkeypatch: pytest.MonkeyPatch, body: dict[str, Any]) -> dict[str, Any]:
    """Replaces httpx.post with one that records the request it was handed.

    Args:
        monkeypatch: Fixture used to install the replacement.
        body: JSON body the stubbed call returns.

    Returns:
        seen: Mapping populated with the url, payload, and headers of the call.
    """
    seen: dict[str, Any] = {}

    def fake_post(url: str, **kwargs: Any) -> httpx.Response:
        seen["url"] = url
        seen["payload"] = kwargs["json"]
        seen["headers"] = kwargs["headers"]
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    return seen


def test_anthropic_client_reads_text_and_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies the Anthropic client maps its response shape onto a Completion."""
    stub_post(monkeypatch, ANTHROPIC_BODY)
    completion = AnthropicLLMClient(api_key="k").complete([Message("user", "hi")], "sys")
    assert completion.text == "hello from claude"
    assert completion.model == "claude-haiku-4-5"
    assert (completion.input_tokens, completion.output_tokens) == (11, 7)


def test_openai_client_reads_text_and_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies the OpenAI client maps its own response shape onto a Completion."""
    stub_post(monkeypatch, OPENAI_BODY)
    completion = OpenAILLMClient(api_key="k").complete([Message("user", "hi")], "sys")
    assert completion.text == "hello from gpt"
    assert completion.model == "gpt-4o-mini"
    assert (completion.input_tokens, completion.output_tokens) == (13, 5)


def test_anthropic_sends_system_as_a_top_level_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies the system prompt stays out of the Anthropic message list."""
    seen = capture_post(monkeypatch, ANTHROPIC_BODY)
    AnthropicLLMClient(api_key="secret").complete([Message("user", "hi")], "be careful")
    assert seen["payload"]["system"] == "be careful"
    assert [m["role"] for m in seen["payload"]["messages"]] == ["user"]
    assert seen["headers"]["x-api-key"] == "secret"


def test_openai_prepends_system_as_a_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies the system prompt becomes OpenAI's first message."""
    seen = capture_post(monkeypatch, OPENAI_BODY)
    OpenAILLMClient(api_key="secret").complete([Message("user", "hi")], "be careful")
    assert [m["role"] for m in seen["payload"]["messages"]] == ["system", "user"]
    assert seen["payload"]["messages"][0]["content"] == "be careful"
    assert seen["headers"]["authorization"] == "Bearer secret"


def test_openai_bounds_output_with_max_completion_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies the OpenAI token ceiling uses the parameter that API accepts."""
    seen = capture_post(monkeypatch, OPENAI_BODY)
    OpenAILLMClient(api_key="k").complete([Message("user", "hi")], "sys", max_tokens=64)
    assert seen["payload"]["max_completion_tokens"] == 64
    assert "max_tokens" not in seen["payload"]


@pytest.mark.parametrize(
    ("client_factory", "body"),
    [(AnthropicLLMClient, ANTHROPIC_BODY), (OpenAILLMClient, OPENAI_BODY)],
)
def test_error_responses_raise(
    monkeypatch: pytest.MonkeyPatch, client_factory: Any, body: dict[str, Any]
) -> None:
    """Verifies a provider error surfaces instead of being read as a completion."""
    stub_post(monkeypatch, body, status=500)
    with pytest.raises(httpx.HTTPStatusError):
        client_factory(api_key="k").complete([Message("user", "hi")], "sys")


@pytest.mark.parametrize("provider", list(Provider))
def test_build_client_fails_closed_without_a_credential(
    monkeypatch: pytest.MonkeyPatch, provider: Provider
) -> None:
    """Verifies a missing credential stops the run instead of calling the API."""
    monkeypatch.delenv(CREDENTIAL_ENV_VARS[provider], raising=False)
    with pytest.raises(MissingCredentialError, match=CREDENTIAL_ENV_VARS[provider]):
        build_client(provider)


@pytest.mark.parametrize("provider", list(Provider))
def test_build_client_rejects_an_empty_credential(
    monkeypatch: pytest.MonkeyPatch, provider: Provider
) -> None:
    """Verifies an empty credential is treated as absent, not as a valid key."""
    monkeypatch.setenv(CREDENTIAL_ENV_VARS[provider], "")
    with pytest.raises(MissingCredentialError):
        build_client(provider)


@pytest.mark.parametrize("provider", list(Provider))
def test_build_client_defaults_the_model_per_provider(
    monkeypatch: pytest.MonkeyPatch, provider: Provider
) -> None:
    """Verifies each provider gets its own default model."""
    monkeypatch.setenv(CREDENTIAL_ENV_VARS[provider], "k")
    assert build_client(provider).model == DEFAULT_MODELS[provider]


@pytest.mark.parametrize("provider", list(Provider))
def test_build_client_honours_an_explicit_model(
    monkeypatch: pytest.MonkeyPatch, provider: Provider
) -> None:
    """Verifies an explicit model overrides the provider default."""
    monkeypatch.setenv(CREDENTIAL_ENV_VARS[provider], "k")
    assert build_client(provider, "custom-model").model == "custom-model"


def test_build_client_picks_the_matching_implementation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies the factory returns the client that speaks the chosen protocol."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("OPENAI_API_KEY", "o")
    assert isinstance(build_client(Provider.ANTHROPIC), AnthropicLLMClient)
    assert isinstance(build_client(Provider.OPENAI), OpenAILLMClient)


@pytest.mark.parametrize("provider", list(Provider))
def test_default_models_are_priced(provider: Provider) -> None:
    """Verifies every default model has a price, so runs are never billed by fallback."""
    assert DEFAULT_MODELS[provider] in PRICE_PER_MTOK


def test_openai_usage_is_priced_at_its_own_rate() -> None:
    """Verifies OpenAI usage is costed from the OpenAI row, not the fallback."""
    tracker = CostTracker()
    assert tracker.record("gpt-4o-mini", 1_000_000, 0) == pytest.approx(0.15)


@pytest.mark.parametrize("provider", list(Provider))
def test_build_client_defaults_to_the_provider_endpoint(
    monkeypatch: pytest.MonkeyPatch, provider: Provider
) -> None:
    """Verifies an unset base URL leaves the client on the real endpoint."""
    monkeypatch.setenv(CREDENTIAL_ENV_VARS[provider], "k")
    monkeypatch.delenv(BASE_URL_ENV_VARS[provider], raising=False)
    seen = capture_post(monkeypatch, ANTHROPIC_BODY | OPENAI_BODY)
    build_client(provider).complete([Message("user", "hi")], "sys")
    assert seen["url"] == DEFAULT_BASE_URLS[provider]


@pytest.mark.parametrize("provider", list(Provider))
def test_build_client_honours_a_base_url_override(
    monkeypatch: pytest.MonkeyPatch, provider: Provider
) -> None:
    """Verifies a proxy or local stub can take the provider's place."""
    monkeypatch.setenv(CREDENTIAL_ENV_VARS[provider], "k")
    monkeypatch.setenv(BASE_URL_ENV_VARS[provider], "http://127.0.0.1:9/v1")
    seen = capture_post(monkeypatch, ANTHROPIC_BODY | OPENAI_BODY)
    build_client(provider).complete([Message("user", "hi")], "sys")
    assert seen["url"] == "http://127.0.0.1:9/v1"
