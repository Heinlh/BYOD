import sqlite3
import struct
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from byod.app import create_app
from byod.config import Config, Preferences, Selection
from byod.db.migrations import connect, initialize
from byod.db.queries import create_workspace, list_workspaces


def test_initialization_is_repeatable(tmp_path: Path) -> None:
    config = Config(tmp_path)
    initialize(config)
    with connect(config) as db:
        create_workspace(db, "Course")
    initialize(config)
    with connect(config) as db:
        assert list_workspaces(db)[0]["name"] == "Course"
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert db.execute("SELECT version FROM schema_version").fetchone()[0] == 1


def test_workspace_cascade_removes_vectors_and_history(tmp_path: Path) -> None:
    config = Config(tmp_path)
    initialize(config)
    with connect(config) as db:
        ws = create_workspace(db, "Course")
        db.execute(
            "INSERT INTO documents(id,workspace_id,filename,path,doc_type,content_hash) "
            "VALUES (1,?, 'fixture','fixture','pdf','hash')",
            (ws,),
        )
        db.execute("INSERT INTO chunks VALUES (1,1,0,'fixture','p. 1','body',20)")
        db.execute(
            "INSERT INTO chunk_vectors VALUES (?, ?)", (1, struct.pack("768f", *([0.1] * 768)))
        )
        db.execute("INSERT INTO chats(id,workspace_id) VALUES (1,?)", (ws,))
        db.execute("INSERT INTO messages(id,chat_id,role,content) VALUES (1,1,'assistant','test')")
        db.execute("INSERT INTO citations VALUES (1,1,1)")
        db.execute("DELETE FROM workspaces WHERE id=?", (ws,))
        for table in ("documents", "chunks", "chunk_vectors", "chats", "messages", "citations"):
            assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0  # noqa: S608


def test_transaction_rollback_and_constraints(tmp_path: Path) -> None:
    config = Config(tmp_path)
    initialize(config)
    with pytest.raises(sqlite3.IntegrityError), connect(config) as db:
        create_workspace(db, "Course")
        create_workspace(db, "Course")
    with connect(config) as db:
        assert list_workspaces(db) == []
        with pytest.raises(ValueError):
            create_workspace(db, " ")


def test_health_and_local_request_protection(tmp_path: Path) -> None:
    with TestClient(create_app(Config(tmp_path)), base_url="http://127.0.0.1") as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        assert client.get("/api/health", headers={"host": "evil.example"}).status_code == 403
        assert (
            client.get("/api/health", headers={"origin": "https://evil.example"}).status_code == 403
        )
        assert client.get("/api/health", headers={"origin": "http://127.0.0.1"}).status_code == 200
        assert client.get("/api/health", headers={"host": "[invalid"}).status_code == 403
        assert client.post("/api/documents/999/open").status_code == 404
        policy = client.get("/api/health").headers["content-security-policy"]
        assert "frame-ancestors 'none'" in policy
    log = (tmp_path / "logs" / "byod.log").read_text(encoding="utf-8")
    assert "Application started" in log and "Application stopped" in log
    assert "evil.example" not in log


def test_missing_native_source_is_actionable(tmp_path: Path) -> None:
    config = Config(tmp_path)
    with TestClient(create_app(config), base_url="http://127.0.0.1") as client:
        with connect(config) as db:
            workspace = create_workspace(db, "Missing source")
            db.execute(
                "INSERT INTO documents(id,workspace_id,filename,path,doc_type,content_hash) "
                "VALUES (1,?,'missing.pdf',?,'pdf','hash')",
                (workspace, str(tmp_path / "missing.pdf")),
            )
        response = client.post("/api/documents/1/open")
        assert response.status_code == 404
        assert "Re-add" in response.json()["detail"]


def test_only_valid_non_secret_preferences_are_persisted(tmp_path: Path) -> None:
    config = Config(tmp_path)
    assert config.preferences().retrieval_min_score == 0.70
    config.save_preferences(Preferences(retrieval_min_score=0.75))
    assert config.preferences().retrieval_min_score == 0.75
    with pytest.raises(ValueError):
        Preferences(retrieval_min_score=1.1)
    with pytest.raises(ValueError):
        Preferences.model_validate({"key": "disallowed"})


def test_deleted_workspace_does_not_leak_provider_selection_to_reused_id(tmp_path: Path) -> None:
    config = Config(tmp_path)
    with TestClient(create_app(config), base_url="http://127.0.0.1") as client:
        workspace = client.post("/api/workspaces", json={"name": "Old course"}).json()["id"]
        with config.edit_preferences() as prefs:
            prefs.workspaces[str(workspace)] = Selection(provider="ollama", model="old-model")
        assert client.delete(f"/api/workspaces/{workspace}").status_code == 204
        assert str(workspace) not in config.preferences().workspaces
        new = client.post("/api/workspaces", json={"name": "New course"}).json()["id"]
        assert config.preferences().selection(new).provider is None
