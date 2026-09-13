from collections.abc import Iterator
from dataclasses import asdict

from byod.llm.base import Message, ProviderError
from byod.llm.providers.http import check, client, sse


class OpenAIProvider:
    name = "openai"
    requires_key = True
    fallback_models = ["gpt-4.1-mini"]

    def __init__(self, key: str | None) -> None:
        self._key = key

    def _headers(self) -> dict[str, str]:
        if not self._key:
            raise ProviderError("NO_PROVIDER", self.name)
        return {"Authorization": f"Bearer {self._key}"}

    def list_models(self) -> list[str]:
        if not self._key:
            return self.fallback_models.copy()
        try:
            with client() as http:
                response = http.get("https://api.openai.com/v1/models", headers=self._headers())
                check(response, self.name)
                models = [str(item["id"]) for item in response.json()["data"]]
                return sorted(
                    m
                    for m in models
                    if m.startswith(("gpt-", "o1", "o3", "o4"))
                    and not any(
                        tag in m
                        for tag in (
                            "audio",
                            "realtime",
                            "transcribe",
                            "image",
                            "instruct",
                            "search",
                            "deep-research",
                            "tts",
                            "codex",
                        )
                    )
                )
        except ProviderError:
            raise
        except Exception:
            return self.fallback_models.copy()

    def validate(self) -> bool:
        try:
            with client() as http:
                response = http.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=self._headers(),
                    json={
                        "model": self.fallback_models[0],
                        "messages": [{"role": "user", "content": "Reply OK."}],
                        "max_completion_tokens": 1,
                        "store": False,
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
                    "https://api.openai.com/v1/chat/completions",
                    headers=self._headers(),
                    json={
                        "model": model,
                        "stream": True,
                        "store": False,
                        "messages": [{"role": "developer", "content": system}]
                        + [asdict(m) for m in messages],
                    },
                ) as response,
            ):
                check(response, self.name)
                for item in sse(response, self.name):
                    for choice in item.get("choices", []):
                        text = choice.get("delta", {}).get("content")
                        if text:
                            yield str(text)
                        if choice.get("finish_reason") is not None:
                            finished = choice["finish_reason"] == "stop"
            if not finished:
                raise ProviderError("PROVIDER_RESPONSE", self.name)
        except ProviderError:
            raise
        except Exception:
            raise ProviderError("PROVIDER_UNREACHABLE", self.name) from None
