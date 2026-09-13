"""sqlite-vec implementation behind a format-independent vector store protocol."""

import json
import sqlite3
from typing import Protocol

import numpy as np

from byod.index.embed import Vector
from byod.model_files import MODEL_DIMS, MODEL_NAME, MODEL_VERSION


def stale_index(db: sqlite3.Connection, workspace_id: int | None = None) -> bool:
    sql = (
        "SELECT 1 FROM documents WHERE (embed_model IS NOT NULL OR status='indexed') "
        "AND (embed_model IS NOT ? OR embed_version IS NOT ?)"
    )
    params: list[object] = [MODEL_NAME, MODEL_VERSION]
    if workspace_id is not None:
        sql += " AND workspace_id=?"
        params.append(workspace_id)
    return db.execute(sql + " LIMIT 1", params).fetchone() is not None


class VectorStore(Protocol):
    def add(self, chunk_ids: list[int], vectors: Vector) -> None: ...
    def search(
        self, vector: Vector, k: int, chunk_ids: list[int] | None = None
    ) -> list[tuple[int, float]]: ...
    def delete(self, chunk_ids: list[int]) -> None: ...


class SqliteVecStore:
    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def add(self, chunk_ids: list[int], vectors: Vector) -> None:
        if vectors.shape != (len(chunk_ids), MODEL_DIMS) or not np.isfinite(vectors).all():
            raise ValueError("Invalid vector dimensions or values")
        self.db.executemany(
            "INSERT INTO chunk_vectors(chunk_id,embedding) VALUES (?,?)",
            [
                (identifier, vector.astype("<f4").tobytes())
                for identifier, vector in zip(chunk_ids, vectors, strict=True)
            ],
        )

    def search(
        self, vector: Vector, k: int, chunk_ids: list[int] | None = None
    ) -> list[tuple[int, float]]:
        if k <= 0 or chunk_ids == []:
            return []
        if vector.shape != (MODEL_DIMS,) or not np.isfinite(vector).all():
            raise ValueError("Invalid query vector")
        sql = "SELECT chunk_id,distance FROM chunk_vectors WHERE embedding MATCH ? AND k=?"
        params: list[object] = [vector.astype("<f4").tobytes(), k]
        if chunk_ids is not None:
            sql += " AND chunk_id IN (SELECT value FROM json_each(?))"
            params.append(json.dumps(chunk_ids))
        sql += " ORDER BY distance"
        return [(int(row[0]), float(row[1])) for row in self.db.execute(sql, params)]

    def delete(self, chunk_ids: list[int]) -> None:
        self.db.executemany("DELETE FROM chunk_vectors WHERE chunk_id=?", [(i,) for i in chunk_ids])
