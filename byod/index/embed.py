"""Lazy ONNX CPU inference with masked mean pooling and L2 normalization."""

import sqlite3
import threading
from typing import Any

import numpy as np
import onnxruntime as ort
from numpy.typing import NDArray

from byod.config import Config
from byod.errors import ByodError
from byod.ingest.chunk import Chunk
from byod.model_files import MODEL_DIMS, MODEL_NAME, MODEL_VERSION, Progress, artifact
from byod.tokenize import TokenCounter

Vector = NDArray[np.float32]


class Embedder:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._session: Any = None
        self._counter: TokenCounter | None = None
        self._lock = threading.Lock()

    def embed(self, texts: list[str], progress: Progress | None = None) -> Vector:
        if not texts:
            return np.empty((0, MODEL_DIMS), dtype=np.float32)
        with self._lock:
            if self._counter is None:
                self._counter = TokenCounter(self.config, progress)
            if self._session is None:
                model = artifact(self.config, weights=True, progress=progress)
                options = ort.SessionOptions()
                options.intra_op_num_threads = 4
                options.inter_op_num_threads = 1
                options.log_severity_level = 4
                self._session = ort.InferenceSession(
                    str(model), sess_options=options, providers=["CPUExecutionProvider"]
                )
            outputs: list[Vector] = []
            for offset in range(0, len(texts), 32):
                encoded = self._counter.tokenizer.encode_batch(texts[offset : offset + 32])
                width = max(len(e.ids) for e in encoded)
                if width > 8192:
                    raise ByodError("BLOCK_TOO_LARGE")
                ids = np.zeros((len(encoded), width), dtype=np.int64)
                mask = np.zeros_like(ids)
                types = np.zeros_like(ids)
                for row, encoding in enumerate(encoded):
                    ids[row, : len(encoding.ids)] = encoding.ids
                    mask[row, : len(encoding.ids)] = 1
                    types[row, : len(encoding.ids)] = encoding.type_ids
                inputs = {"input_ids": ids, "attention_mask": mask, "token_type_ids": types}
                feed = {item.name: inputs[item.name] for item in self._session.get_inputs()}
                hidden = np.asarray(self._session.run(None, feed)[0], dtype=np.float32)
                expanded = mask[..., None].astype(np.float32)
                pooled = (hidden * expanded).sum(axis=1) / np.maximum(expanded.sum(axis=1), 1)
                norm = np.linalg.norm(pooled, axis=1, keepdims=True)
                if not np.isfinite(pooled).all() or np.any(norm < 1e-12):
                    raise ByodError("INGEST_FAILED")
                vectors = np.asarray(pooled / norm, dtype=np.float32)
                if vectors.shape != (len(encoded), MODEL_DIMS):
                    raise ByodError("INGEST_FAILED")
                outputs.append(vectors)
            return np.concatenate(outputs)

    def index_document(
        self, db: sqlite3.Connection, document_id: int, chunks: list[Chunk], progress: Progress
    ) -> None:
        from byod.index.store import SqliteVecStore

        vectors = self.embed([c.text for c in chunks], progress)
        ids = [
            int(row[0])
            for row in db.execute(
                "SELECT id FROM chunks WHERE document_id=? ORDER BY ordinal", (document_id,)
            )
        ]
        SqliteVecStore(db).add(ids, vectors)
        db.execute(
            "UPDATE documents SET status='indexed',embed_model=?,embed_version=? WHERE id=?",
            (MODEL_NAME, MODEL_VERSION, document_id),
        )
