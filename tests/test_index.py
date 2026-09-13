from pathlib import Path

import numpy as np
import pytest

from byod.config import Config
from byod.db.migrations import connect, initialize
from byod.db.queries import create_workspace
from byod.index.embed import Embedder
from byod.index.store import SqliteVecStore
from byod.ingest.jobs import JobQueue
from byod.model_files import MODEL_DIMS, MODEL_NAME, MODEL_VERSION

FIXTURES = Path(__file__).parent / "fixtures"


def test_real_embeddings_are_normalized_and_semantic(ingest_config: Config) -> None:
    embedder = Embedder(ingest_config)
    vectors = embedder.embed(
        [
            "Plants convert sunlight to sugar through photosynthesis.",
            "How do plants use sunlight to produce chemical energy?",
            "A judge interprets the law during a criminal trial.",
        ]
    )
    assert vectors.shape == (3, MODEL_DIMS)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-5)
    assert float(vectors[0] @ vectors[1]) > float(vectors[0] @ vectors[2])
    assert embedder.embed([]).shape == (0, MODEL_DIMS)


def test_vec_store_filters_and_deletion(ingest_config: Config) -> None:
    initialize(ingest_config)
    vectors = np.zeros((3, MODEL_DIMS), dtype=np.float32)
    vectors[0, 0] = 1
    vectors[1, 1] = 1
    vectors[2, 0] = -1
    with connect(ingest_config) as db:
        store = SqliteVecStore(db)
        store.add([1, 2, 3], vectors)
        results = store.search(vectors[0], 20)
        assert [r[0] for r in results] == [1, 2, 3]
        assert results[0][1] == pytest.approx(0)
        assert [r[0] for r in store.search(vectors[0], 20, [2, 3])] == [2, 3]
        assert store.search(vectors[0], 20, []) == []
        store.delete([1, 2, 3])
        assert store.search(vectors[0], 20) == []
        with pytest.raises(ValueError):
            store.add([1], np.zeros((1, 2), dtype=np.float32))


def test_real_ingestion_populates_one_vector_per_chunk(ingest_config: Config) -> None:
    initialize(ingest_config)
    with connect(ingest_config) as db:
        workspace = create_workspace(db, "Biology")
    jobs = JobQueue(ingest_config, Embedder(ingest_config).index_document)
    try:
        identifier = jobs.submit(workspace, [str(FIXTURES / "lecture.pptx")])
        jobs.wait()
        status = jobs.snapshot(identifier)
        assert status and status["state"] == "done"
        with connect(ingest_config) as db:
            count = db.execute("SELECT count(*) FROM chunks").fetchone()[0]
            assert count > 0
            assert db.execute("SELECT count(*) FROM chunk_vectors").fetchone()[0] == count
            document = db.execute("SELECT * FROM documents").fetchone()
            assert document["status"] == "indexed"
            assert document["embed_model"] == MODEL_NAME
            assert document["embed_version"] == MODEL_VERSION
        identifier = jobs.submit(workspace, [str(FIXTURES / "lecture.pptx")], reindex=True)
        jobs.wait()
        status = jobs.snapshot(identifier)
        assert status and status["state"] == "done"
        with connect(ingest_config) as db:
            assert db.execute("SELECT count(*) FROM chunk_vectors").fetchone()[0] == count
    finally:
        jobs.close()
