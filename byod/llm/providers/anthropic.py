from collections.abc import Iterator
from dataclasses import asdict

from byod.llm.base import Message, ProviderError
from byod.llm.providers.http import check, client, sse


class AnthropicProvider:
    name = "anthropic"
    requires_key = True
    fallback_models = ["claude-haiku-4-5-20251001"]

    def __init__(self, key: str | None) -> None:
        self._key = key

    def _headers(self) -> dict[str, str]:
        if not self._key:
            raise ProviderError("NO_PROVIDER", self.name)
        return {"x-api-key": self._key, "anthropic-version": "2023-06-01"}

    def list_models(self) -> list[str]:
        if not self._key:
            return self.fallback_models.copy()
        try:
            with client() as http:
                response = http.get("https://api.anthropic.com/v1/models", headers=self._headers())
                check(response, self.name)
                return [str(item["id"]) for item in response.json()["data"]]
        except ProviderError:
            raise
        except Exception:
            return self.fallback_models.copy()

    def validate(self) -> bool:
        try:
            with client() as http:
                response = http.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=self._headers(),
                    json={
                        "model": self.fallback_models[0],
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "Reply OK."}],
                    },
                )
                check(response, self.name)
                return True
        except Exception:
            return False

    def stream(self, messages: list[Message], system: str, model: str) -> Iterator[str]:
        finished = False
        try:
            with (
                client() as http,
                http.stream(
                    "POST",
                    "https://api.anthropic.com/v1/messages",
                    headers=self._headers(),
                    json={
                        "model": model,
                        "stream": True,
                        "system": system,
                        "messages": [asdict(m) for m in messages],
                        "max_tokens": 4096,
                    },
                ) as response,
            ):
                check(response, self.name)
                for item in sse(response, self.name):
                    if item.get("type") == "content_block_delta":
                        delta = item.get("delta", {})
                        if delta.get("type") == "text_delta":
                            yield str(delta["text"])
                    if item.get("type") == "message_stop":
                        finished = True
                    if (
                        item.get("type") == "message_delta"
                        and item.get("delta", {}).get("stop_reason") == "max_tokens"
                    ):
                        raise ProviderError("PROVIDER_RESPONSE", self.name)
            if not finished:
                raise ProviderError("PROVIDER_RESPONSE", self.name)
        except ProviderError:
            raise
        except Exception:
            raise ProviderError("PROVIDER_UNREACHABLE", self.name) from None
