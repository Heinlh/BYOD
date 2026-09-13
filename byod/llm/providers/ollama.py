import json
from collections.abc import Iterator
from dataclasses import asdict

import httpx

from byod.llm.base import Message, ProviderError
from byod.llm.providers.http import check, client


class OllamaProvider:
    name = "ollama"
    requires_key = False

    def list_models(self) -> list[str]:
        try:
            with client() as http:
                response = http.get("http://localhost:11434/api/tags", timeout=2)
                check(response, self.name)
                return [str(m["name"]) for m in response.json()["models"]]
        except Exception:
            return []

    def validate(self) -> bool:
        return bool(self.list_models())

    def stream(self, messages: list[Message], system: str, model: str) -> Iterator[str]:
        finished = False
        try:
            with (
                client() as http,
                http.stream(
                    "POST",
                    "http://localhost:11434/api/chat",
                    # Large CPU models can take several minutes to load and prefill.
                    timeout=httpx.Timeout(600, connect=10),
                    json={
                        "model": model,
                        "stream": True,
                        "think": False,
                        "messages": [{"role": "system", "content": system}]
                        + [asdict(m) for m in messages],
                        "options": {"num_predict": 4096, "num_ctx": 16384},
                    },
                ) as response,
            ):
                check(response, self.name)
                for line in response.iter_lines():
                    if not line:
                        continue
                    item = json.loads(line)
                    if "error" in item:
                        raise ProviderError("PROVIDER_RESPONSE", self.name)
                    text = item.get("message", {}).get("content")
                    if text:
                        yield str(text)
                    if item.get("done"):
                        finished = item.get("done_reason") != "length"
            if not finished:
                raise ProviderError("PROVIDER_RESPONSE", self.name)
        except ProviderError:
            raise
        except httpx.TimeoutException:
            raise ProviderError("PROVIDER_TIMEOUT", self.name) from None
        except Exception:
            raise ProviderError("PROVIDER_UNREACHABLE", self.name) from None
