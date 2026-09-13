import json
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from byod.app import create_app
from byod.config import Config
from byod.db.migrations import connect
from byod.llm.base import LLMProvider, Message, ProviderError
from byod.llm.keys import KeyStore

FIXTURE = Path(__file__).parent / "fixtures" / "lecture.pptx"


class StubProvider:
    name = "ollama"
    requires_key = False

    def __init__(self) -> None:
        self.accept_key = True
        self.fail = False
        self.calls = 0
        self.last_messages: list[Message] = []

    def list_models(self) -> list[str]:
        return ["test-model"]

    def validate(self) -> bool:
        return self.accept_key

    def stream(self, messages: list[Message], system: str, model: str) -> Iterator[str]:
        self.calls += 1
        self.last_messages = messages
        if self.fail:
            raise ProviderError("PROVIDER_RATE_LIMIT", "ollama")
        marker = system.split("EXCERPTS:\n", 1)[1].splitlines()[0]
        yield "Plants convert sunlight into chemical energy. "
        yield marker
        yield " [unknown.pdf, p. 999]"


@pytest.fixture
def test_keys() -> Iterator[KeyStore]:
    # A real OS keychain namespace isolated from the user's BYOD credentials.
    keys = KeyStore("byod-test-" + uuid.uuid4().hex)
    try:
        yield keys
    finally:
        for provider in ("openai", "anthropic"):
            keys.delete(provider)


def test_settings_keychain_and_validation_privacy(
    ingest_config: Config, test_keys: KeyStore
) -> None:
    stub = StubProvider()

    def factory(name: str, key: str | None) -> LLMProvider:
        return stub

    app = create_app(ingest_config, keys=test_keys, provider_factory=factory)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.get("/api/settings")
        assert response.status_code == 200
        assert response.json()["retrieval_min_score"] == 0.70
        assert client.put("/api/settings", json={"model": "test-model"}).status_code == 422
        assert client.put("/api/settings", json={"provider": "invalid"}).status_code == 422
        assert (
            client.put("/api/settings", json={"provider": "ollama", "model": "absent"}).status_code
            == 422
        )
        assert (
            client.put(
                "/api/settings", json={"provider": "ollama", "model": "test-model"}
            ).status_code
            == 200
        )
        assert client.get("/api/settings").json()["active"]["provider"] == "ollama"
        workspace = client.post("/api/workspaces", json={"name": "Biology"}).json()["id"]
        assert (
            client.put(
                "/api/settings",
                json={"workspace_id": workspace, "provider": "openai", "model": "test-model"},
            ).status_code
            == 200
        )
        assert (
            client.get(f"/api/settings?workspace_id={workspace}").json()["active"]["provider"]
            == "openai"
        )
        assert client.get("/api/settings?workspace_id=999").status_code == 404
        assert client.put("/api/settings", json={"workspace_id": 999}).status_code == 404
        secret = "test-only-" + uuid.uuid4().hex
        response = client.put("/api/settings/key", json={"provider": "openai", "key": secret})
        assert response.json() == {"valid": True}
        assert test_keys.get("openai") == secret
        assert secret not in client.get("/api/settings").text
        assert secret not in (ingest_config.data_dir / "config.json").read_text()
        assert secret.encode() not in ingest_config.database.read_bytes()
        stub.accept_key = False
        assert client.put(
            "/api/settings/key", json={"provider": "openai", "key": "invalid"}
        ).json() == {"valid": False}
        assert (
            test_keys.get("openai") == secret
        )  # Invalid replacement never overwrites the saved key.
        response = client.put("/api/settings/key", json={"provider": secret, "key": secret})
        assert response.status_code == 422 and secret not in response.text
        assert client.delete("/api/settings/key/openai").status_code == 204
        assert test_keys.get("openai") is None
        assert client.delete("/api/settings/key/invalid").status_code == 422


def test_chat_stream_persistence_citations_and_errors(
    ingest_config: Config, test_keys: KeyStore
) -> None:
    stub = StubProvider()

    def factory(name: str, key: str | None) -> LLMProvider:
        return stub

    app = create_app(ingest_config, keys=test_keys, provider_factory=factory)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        workspace = client.post("/api/workspaces", json={"name": "Biology"}).json()["id"]
        route = f"/api/workspaces/{workspace}/chats"
        assert client.get(route).json() == []
        response = client.post(route)
        assert response.status_code == 201
        chat = response.json()["id"]
        message_route = f"/api/chats/{chat}/messages"
        assert client.get(message_route).json() == []
        assert client.post(message_route, json={"content": " "}).status_code == 422
        assert (
            client.post(
                message_route, json={"content": "question", "document_ids": [999]}
            ).status_code
            == 422
        )
        response = client.post(message_route, json={"content": "How does photosynthesis work?"})
        assert "Nothing in this workspace matches" in response.text
        assert stub.calls == 0
        client.post(
            f"/api/workspaces/{workspace}/documents", json={"paths": [str(FIXTURE.resolve())]}
        )
        app.state.jobs.wait()
        response = client.post(message_route, json={"content": "How does photosynthesis work?"})
        assert "NO_PROVIDER" in response.text
        client.put("/api/settings", json={"provider": "ollama", "model": "test-model"})
        response = client.post(message_route, json={"content": "How does photosynthesis work?"})
        assert response.status_code == 200
        frames = [
            (part.splitlines()[0][7:], json.loads(part.splitlines()[1][6:]))
            for part in response.text.strip().split("\n\n")
        ]
        assert frames[0][0] == "context" and frames[-1][0] == "done"
        resolved = frames[-1][1]["citations"]
        assert resolved and all(c["filename"] == "lecture.pptx" for c in resolved)
        for citation in resolved:
            assert client.get(f"/api/chunks/{citation['chunk_id']}").status_code == 200
        history = client.get(message_route).json()
        assert history[-1]["citations"] == resolved
        assert client.get(route).json()[0]["title"] != "Untitled"
        with connect(ingest_config) as db:
            for i in range(12):
                db.execute(
                    "INSERT INTO messages(chat_id,role,content) VALUES (?,'user',?)",
                    (chat, f"Previous question {i}"),
                )
        client.post(message_route, json={"content": "How does photosynthesis work?"})
        assert len(stub.last_messages) == 10
        stub.fail = True
        response = client.post(message_route, json={"content": "How does photosynthesis work?"})
        assert "PROVIDER_RATE_LIMIT" in response.text and "event: done" not in response.text
        assert client.get("/api/chats/999/messages").status_code == 404
        assert client.post("/api/chats/999/messages", json={"content": "test"}).status_code == 404
        assert client.get("/api/workspaces/999/chats").status_code == 404
        assert client.post("/api/workspaces/999/chats").status_code == 404
        assert client.delete("/api/chats/999").status_code == 404
    with TestClient(
        create_app(ingest_config, keys=test_keys, provider_factory=factory),
        base_url="http://127.0.0.1",
    ) as client:
        assert client.get(message_route).json()
        assert client.delete(f"/api/chats/{chat}").status_code == 204
        assert client.get(message_route).status_code == 404
