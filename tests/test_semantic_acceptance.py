import json
from pathlib import Path

from byod.config import Config
from byod.db.migrations import connect, initialize
from byod.db.queries import create_workspace
from byod.index.embed import Embedder
from byod.ingest.jobs import JobQueue
from byod.retrieve.search import Retriever

FIXTURES = Path(__file__).parent / "fixtures" / "queries"


def test_natural_language_queries_across_topics_and_formats(ingest_config: Config) -> None:
    initialize(ingest_config)
    with connect(ingest_config) as db:
        workspace = create_workspace(db, "Cross-topic acceptance")
    embedder = Embedder(ingest_config)
    jobs = JobQueue(ingest_config, embedder.index_document)
    try:
        identifier = jobs.submit(workspace, [str(FIXTURES)])
        jobs.wait()
        status = jobs.snapshot(identifier)
        assert status and status["state"] == "done"
    finally:
        jobs.close()
    cases = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))
    retriever = Retriever(ingest_config, embedder)
    failures = []
    for index, case in enumerate(cases["supported"]):
        results = retriever.search(workspace, case["query"])
        if not results or (results[0].filename, results[0].locator) != (
            case["filename"],
            case["locator"],
        ):
            failures.append(f"supported case {index}: expected source not ranked first")
            continue
        context, included = retriever.context(results)
        assert case["evidence"].lower() in context.lower()
        assert included and results[0].citation in context
        filtered = retriever.search(workspace, case["query"], [results[0].document_id])
        assert filtered and all(r.filename == case["filename"] for r in filtered)
    for index, query in enumerate(cases["unsupported"]):
        if retriever.search(workspace, query):
            failures.append(f"unsupported case {index}: false match")
    assert not failures, "; ".join(failures)
