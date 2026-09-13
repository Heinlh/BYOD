import json

import httpx
import pytest

from byod.llm.base import LLMProvider, Message, ProviderError
from byod.llm.providers import anthropic, ollama, openai


@pytest.mark.parametrize("kind", ["openai", "anthropic", "ollama"])
def test_provider_stream_contract(kind: str, monkeypatch: pytest.MonkeyPatch) -> None:
    payloads = {
        "openai": (
            'data: {"choices":[{"delta":{"content":"OK"},"finish_reason":"stop"}]}'
            "\n\ndata: [DONE]\n\n"
        ),
        "anthropic": (
            'data: {"type":"content_block_delta",'
            '"delta":{"type":"text_delta","text":"OK"}}\n\n'
            'data: {"type":"message_stop"}\n\n'
        ),
        "ollama": '{"message":{"content":"OK"},"done":true,"done_reason":"stop"}\n',
    }

    def transport(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["stream"] is True
        assert body["model"] == "test-model"
        assert request.url.path in {"/v1/chat/completions", "/v1/messages", "/api/chat"}
        if kind == "ollama":
            assert request.extensions["timeout"]["read"] == 600
        return httpx.Response(200, text=payloads[kind])

    module = {"openai": openai, "anthropic": anthropic, "ollama": ollama}[kind]

    def factory() -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(transport))

    monkeypatch.setattr(module, "client", factory)
    providers: dict[str, LLMProvider] = {
        "openai": openai.OpenAIProvider("test-key"),
        "anthropic": anthropic.AnthropicProvider("test-key"),
        "ollama": ollama.OllamaProvider(),
    }
    provider = providers[kind]
    assert "".join(provider.stream([Message("user", "test")], "system", "test-model")) == "OK"


@pytest.mark.parametrize(
    "status,code",
    [(401, "PROVIDER_AUTH"), (429, "PROVIDER_RATE_LIMIT"), (500, "PROVIDER_UNREACHABLE")],
)
def test_provider_errors_never_echo_bodies(
    status: int, code: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text="sensitive provider body")

    monkeypatch.setattr(
        openai, "client", lambda: httpx.Client(transport=httpx.MockTransport(transport))
    )
    with pytest.raises(ProviderError) as error:
        list(openai.OpenAIProvider("test-key").stream([Message("user", "test")], "system", "model"))
    assert error.value.code == code
    assert "sensitive" not in str(error.value) and "test-key" not in str(error.value)


def test_local_model_timeout_has_actionable_sanitized_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def transport(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("sensitive transport details", request=request)

    monkeypatch.setattr(
        ollama, "client", lambda: httpx.Client(transport=httpx.MockTransport(transport))
    )
    with pytest.raises(ProviderError) as error:
        list(ollama.OllamaProvider().stream([Message("user", "test")], "system", "model"))
    assert error.value.code == "PROVIDER_TIMEOUT"
    assert "smaller model" in error.value.message
    assert "sensitive" not in error.value.message
