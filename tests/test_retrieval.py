import json
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from byod.cli import bench
from byod.config import Config
from byod.db.migrations import connect, initialize
from byod.db.queries import create_workspace
from byod.errors import ByodError
from byod.index.embed import Embedder
from byod.ingest.jobs import JobQueue
from byod.llm.base import Message, ProviderError
from byod.retrieve.search import Retriever
from byod.tokenize import TokenCounter

FIXTURES = Path(__file__).parent / "fixtures"


def test_real_retrieval_filters_context_and_stale_index(ingest_config: Config) -> None:
    initialize(ingest_config)
    with connect(ingest_config) as db:
        workspace = create_workspace(db, "Biology")
        empty_workspace = create_workspace(db, "Other")
    embedder = Embedder(ingest_config)
    jobs = JobQueue(ingest_config, embedder.index_document)
    try:
        identifier = jobs.submit(
            workspace, [str(FIXTURES / "lecture.pptx"), str(FIXTURES / "reading.pdf")]
        )
        jobs.wait()
        state = jobs.snapshot(identifier)
        assert state and state["state"] == "done"
    finally:
        jobs.close()
    retriever = Retriever(ingest_config, embedder)
    results = retriever.search(workspace, "How does photosynthesis convert sunlight to energy?")
    assert results and all(r.score >= 0.70 and r.locator for r in results)
    assert len({r.document_id for r in results}) == 2
    document = results[0].document_id
    filtered = retriever.search(workspace, "photosynthesis", [document])
    assert filtered and all(r.document_id == document for r in filtered)
    typed = retriever.search(workspace, "photosynthesis", doc_type="pptx")
    assert typed and all(r.filename == "lecture.pptx" for r in typed)
    assert retriever.search(empty_workspace, "photosynthesis") == []
    assert retriever.search(workspace, "photosynthesis", [9999]) == []
    assert retriever.search(workspace, "photosynthesis", []) == []
    assert retriever.search(workspace, "  ") == []
    assert retriever.search(workspace, "What is the syntax of a Rust lifetime parameter?") == []
    text, included = retriever.context(results, budget=800)
    assert included and TokenCounter(ingest_config).count(text) <= 800
    assert all(r.citation in text for r in included)
    for document_id in {r.document_id for r in included}:
        ordinals = [r.ordinal for r in included if r.document_id == document_id]
        assert ordinals == sorted(ordinals, reverse=True)
    assert retriever.context(results, budget=1) == ("", [])
    with connect(ingest_config) as db:
        db.execute("UPDATE documents SET embed_version='old' WHERE id=?", (document,))
    with pytest.raises(ByodError) as error:
        retriever.search(workspace, "photosynthesis")
    assert error.value.code == "STALE_INDEX"


def test_missing_source_is_excluded(ingest_config: Config) -> None:
    initialize(ingest_config)
    source = ingest_config.data_dir / "lecture.pptx"
    shutil.copyfile(FIXTURES / "lecture.pptx", source)
    with connect(ingest_config) as db:
        workspace = create_workspace(db, "Biology")
    embedder = Embedder(ingest_config)
    jobs = JobQueue(ingest_config, embedder.index_document)
    try:
        jobs.submit(workspace, [str(source)])
        jobs.wait()
        source.unlink()
        assert Retriever(ingest_config, embedder).search(workspace, "photosynthesis") == []
        with connect(ingest_config) as db:
            assert db.execute("SELECT status FROM documents").fetchone()[0] == "missing"
    finally:
        jobs.close()


def test_search_cli_gate(ingest_config: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    command = [sys.executable, "-m", "byod.cli", "--data-dir", str(ingest_config.data_dir)]
    subprocess.run(  # noqa: S603
        command + ["add", "Biology", str(FIXTURES / "lecture.pptx")],
        capture_output=True,
        check=True,
        timeout=60,
    )
    search = command + ["debug", "search", "Biology", "photosynthesis"]
    result = subprocess.run(search, capture_output=True, check=True, timeout=30)  # noqa: S603
    ranked = json.loads(result.stdout)
    assert ranked and all(r["locator"] and isinstance(r["score"], float) for r in ranked)
    result = subprocess.run(  # noqa: S603
        search + ["--doc", "99999"],
        capture_output=True,
        check=True,
        timeout=30,
    )
    assert json.loads(result.stdout) == []
    benchmark = command + ["debug", "bench", "Biology", "photosynthesis", "--runs", "3", "--no-llm"]
    result = subprocess.run(benchmark, capture_output=True, check=True, timeout=60)  # noqa: S603
    report = json.loads(result.stdout)
    assert report["runs"] == 3 and report["scope"] == "workspace"
    assert report["candidates"] > 0 and report["chunks"] > 0 and report["context_tokens"] > 0
    assert set(report["ms"]) == {"candidates", "embed", "search", "assembly", "retrieval"}
    assert all(0 <= phase["median"] <= phase["p95"] for phase in report["ms"].values())
    assert b"photosynthesis" not in result.stdout.lower()  # Neither query nor chunk text.

    class UnavailableProvider:
        def stream(self, messages: list[Message], system: str, model: str) -> Iterator[str]:
            raise ProviderError("PROVIDER_TIMEOUT", "ollama")
            yield ""  # pragma: no cover

    monkeypatch.setattr("byod.cli.provider_for", lambda *_: UnavailableProvider())
    with ingest_config.edit_preferences() as preferences:
        preferences.active.provider = "ollama"
        preferences.active.model = "test"
    with connect(ingest_config) as db:
        workspace = int(db.execute("SELECT id FROM workspaces").fetchone()[0])
    timed = bench(ingest_config, workspace, "photosynthesis", None, 1, True)
    assert isinstance(timed["ms"], dict)
    assert "ttft" not in timed["ms"]
    assert timed["ms"]["provider_failed_wait"]["samples"] == 1
    assert timed["provider_errors"] == ["PROVIDER_TIMEOUT", "PROVIDER_TIMEOUT"]
