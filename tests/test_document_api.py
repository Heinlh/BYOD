from pathlib import Path

from fastapi.testclient import TestClient

from byod.app import create_app
from byod.config import Config

FIXTURE = Path(__file__).parent / "fixtures" / "notes.docx"


def test_document_and_workspace_routes(ingest_config: Config) -> None:
    app = create_app(ingest_config)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert client.get("/api/workspaces").json() == []
        assert client.post("/api/workspaces", json={"name": " "}).status_code == 422
        response = client.post("/api/workspaces", json={"name": "Biology"})
        assert response.status_code == 201
        workspace = response.json()["id"]
        assert client.post("/api/workspaces", json={"name": "Biology"}).status_code == 409
        base = f"/api/workspaces/{workspace}/documents"
        assert client.get(base).json() == []
        assert client.post(base, json={"paths": []}).status_code == 422
        response = client.post(base, json={"paths": [str(FIXTURE.resolve())]})
        assert response.status_code == 202
        app.state.jobs.wait()
        assert client.get("/api/jobs/" + response.json()["job_id"]).json()["state"] == "done"
        document = client.get(base).json()[0]["id"]
        assert client.get("/api/workspaces").json()[0]["document_count"] == 1
        assert client.post(f"/api/documents/{document}/reindex").status_code == 202
        app.state.jobs.wait()
        from byod.db.migrations import connect

        with connect(ingest_config) as db:
            chunk_id = db.execute("SELECT id FROM chunks LIMIT 1").fetchone()[0]
        assert client.get(f"/api/chunks/{chunk_id}").json()["filename"] == "notes.docx"
        assert client.delete(f"/api/documents/{document}").status_code == 204
        assert client.get(f"/api/chunks/{chunk_id}").status_code == 404
        assert client.get(base).json() == []
        assert client.delete(f"/api/workspaces/{workspace}").status_code == 204
        for route in ("/api/jobs/absent", "/api/workspaces/999/documents", "/api/chunks/999"):
            assert client.get(route).status_code == 404
        for route in ("/api/documents/999", "/api/workspaces/999"):
            assert client.delete(route).status_code == 404
        assert client.post("/api/documents/999/reindex").status_code == 404
        assert (
            client.post("/api/workspaces/999/documents", json={"paths": ["absent"]}).status_code
            == 404
        )
