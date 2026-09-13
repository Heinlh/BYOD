"""OS-backed keychain only. No file-based or plaintext fallback."""

import keyring
from keyring.backend import KeyringBackend

from byod.llm.base import ProviderError


class KeyStore:
    def __init__(self, service: str = "byod") -> None:
        self.service = service

    def _backend(self) -> KeyringBackend:
        backend = keyring.get_keyring()
        if type(backend).__module__ not in {
            "keyring.backends.Windows",
            "keyring.backends.macOS",
            "keyring.backends.SecretService",
            "keyring.backends.kwallet",
        }:
            raise ProviderError("KEYCHAIN_UNAVAILABLE", "OS")
        return backend

    def get(self, provider: str) -> str | None:
        if provider not in {"openai", "anthropic"}:
            return None
        try:
            return self._backend().get_password(self.service, provider)
        except Exception:
            raise ProviderError("KEYCHAIN_UNAVAILABLE", "OS") from None

    def configured(self, provider: str) -> bool:
        try:
            return bool(self.get(provider))
        except ProviderError:
            return False

    def set(self, provider: str, secret: str) -> None:
        if provider not in {"openai", "anthropic"}:
            raise ValueError("Unknown key provider")
        try:
            self._backend().set_password(self.service, provider, secret)
        except Exception:
            raise ProviderError("KEYCHAIN_UNAVAILABLE", "OS") from None

    def delete(self, provider: str) -> None:
        if provider not in {"openai", "anthropic"}:
            raise ValueError("Unknown key provider")
        try:
            backend = self._backend()
            if backend.get_password(self.service, provider) is not None:
                backend.delete_password(self.service, provider)
        except Exception:
            raise ProviderError("KEYCHAIN_UNAVAILABLE", "OS") from None
