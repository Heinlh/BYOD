"""Opt-in installed-bundle check. Uses synthetic data and reports no private content."""

import json
import time
import uuid
from pathlib import Path

import httpx

from byod.config import Config
from byod.db.migrations import connect
from byod.llm.keys import KeyStore


def require(condition: bool) -> None:
    if not condition:
        raise RuntimeError("Installed bundle verification failed")


def verify_bundle(config: Config, url: str, fixtures: Path | None = None) -> dict[str, object]:
    # These imports exercise native DLL collection in the frozen distribution.
    import docx
    import onnxruntime
    import pptx
    import pymupdf
    import tokenizers

    with httpx.Client(base_url=url, trust_env=False, timeout=10) as client:
        require(client.get("/api/health").json() == {"status": "ok"})
        response = client.get("/")
        require(response.status_code == 200 and "/assets/" in response.text)
    with connect(config) as db:
        require(bool(db.execute("SELECT vec_version()").fetchone()[0]))
    service = "byod-package-test-" + uuid.uuid4().hex
    keys = KeyStore(service)
    try:
        keys.set("openai", "synthetic-package-check")
        require(keys.get("openai") == "synthetic-package-check")
    finally:
        keys.delete("openai")
    result: dict[str, object] = {
        "status": "passed",
        "api": True,
        "ui": True,
        "sqlite_vec": True,
        "keychain": True,
        "native_imports": all(
            callable(value)
            for value in [
                docx.Document,
                pptx.Presentation,
                pymupdf.open,
                onnxruntime.InferenceSession,
                tokenizers.Tokenizer,
            ]
        ),
    }
    if fixtures:
        result["document_queries"] = verify_documents(config, url, fixtures)
    return result


def verify_documents(config: Config, url: str, fixtures: Path) -> int:
    from byod.index.embed import Embedder
    from byod.retrieve.search import Retriever

    cases = json.loads((fixtures / "cases.json").read_text(encoding="utf-8"))
    with httpx.Client(base_url=url, trust_env=False, timeout=30) as client:
        response = client.post(
            "/api/workspaces", json={"name": "Package check " + uuid.uuid4().hex}
        )
        response.raise_for_status()
        workspace = response.json()["id"]
        try:
            response = client.post(
                f"/api/workspaces/{workspace}/documents", json={"paths": [str(fixtures)]}
            )
            response.raise_for_status()
            job = response.json()["job_id"]
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline:
                status = client.get(f"/api/jobs/{job}").json()
                if status["state"] in {"done", "failed"}:
                    break
                time.sleep(0.2)
            require(status["state"] == "done")
            retriever = Retriever(config, Embedder(config))
            for case in cases["supported"]:
                matches = retriever.search(workspace, case["query"])
                require(bool(matches))
                require(
                    (matches[0].filename, matches[0].locator) == (case["filename"], case["locator"])
                )
                context, _ = retriever.context(matches)
                require(case["evidence"].lower() in context.lower())
            for query in cases["unsupported"]:
                require(not retriever.search(workspace, query))
            return len(cases["supported"]) + len(cases["unsupported"])
        finally:
            client.delete(f"/api/workspaces/{workspace}").raise_for_status()
