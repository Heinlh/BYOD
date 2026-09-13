"""Provider contract and fixed public error vocabulary."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class Message:
    role: Literal["user", "assistant"]
    content: str


class LLMProvider(Protocol):
    name: str
    requires_key: bool

    def list_models(self) -> list[str]: ...
    def validate(self) -> bool: ...
    def stream(self, messages: list[Message], system: str, model: str) -> Iterator[str]: ...


class ProviderError(Exception):
    def __init__(self, code: str, provider: str) -> None:
        self.code = code
        self.message = {
            "PROVIDER_AUTH": f"Your {provider} key was rejected. Check it in Settings.",
            "PROVIDER_RATE_LIMIT": f"{provider} is rate limiting. Wait a moment and retry.",
            "PROVIDER_UNREACHABLE": f"Couldn't reach {provider}. Check the connection and retry.",
            "PROVIDER_TIMEOUT": (
                f"{provider} took too long to reply. Choose a smaller model in Settings "
                "or free memory and retry."
            ),
            "PROVIDER_RESPONSE": f"{provider} returned an incomplete response. Retry the question.",
            "NO_PROVIDER": "Choose a provider and model in Settings to ask questions.",
            "KEYCHAIN_UNAVAILABLE": "Couldn't access the OS keychain. Unlock it and retry.",
        }[code]
        super().__init__(self.message)
