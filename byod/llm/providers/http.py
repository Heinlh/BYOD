"""Provider transport helpers with sanitized errors and no proxy/redirect leakage."""

import json
from collections.abc import Iterator
from typing import Any

import httpx

from byod.llm.base import ProviderError


def client() -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(180, connect=10), trust_env=False, follow_redirects=False
    )


def check(response: httpx.Response, name: str) -> None:
    if response.status_code in {401, 403}:
        raise ProviderError("PROVIDER_AUTH", name)
    if response.status_code == 429:
        raise ProviderError("PROVIDER_RATE_LIMIT", name)
    if not 200 <= response.status_code < 300:
        raise ProviderError("PROVIDER_UNREACHABLE", name)


def sse(response: httpx.Response, name: str) -> Iterator[dict[str, Any]]:
    data: list[str] = []
    for line in response.iter_lines():
        if line.startswith("data:"):
            data.append(line[5:].lstrip())
        elif not line and data:
            payload = "\n".join(data)
            data = []
            if payload == "[DONE]":
                return
            item = json.loads(payload)
            if not isinstance(item, dict) or "error" in item or item.get("type") == "error":
                raise ProviderError("PROVIDER_RESPONSE", name)
            yield item
