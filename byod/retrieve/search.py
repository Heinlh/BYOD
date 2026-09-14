"""Filter before vector search; assemble source-located context within a token cap."""

import json
import time
from dataclasses import dataclass
from pathlib import Path

from byod.config import Config
from byod.db.migrations import connect
from byod.errors import ByodError
from byod.index.embed import Embedder
from byod.index.store import SqliteVecStore, stale_index
from byod.tokenize import TokenCounter


@dataclass(frozen=True)
class SearchResult:
    chunk_id: int
    document_id: int
    filename: str
    locator: str
    ordinal: int
    text: str
    token_count: int
    score: float

    @property
    def citation(self) -> str:
        return f"[{self.filename}, {self.locator}]"


class Retriever:
    def __init__(self, config: Config, embedder: Embedder) -> None:
        self.config = config
        self.embedder = embedder

    def search(
        self,
        workspace_id: int,
        query: str,
        document_ids: list[int] | None = None,
        doc_type: str | None = None,
        k: int = 20,
        stats: dict[str, float] | None = None,
    ) -> list[SearchResult]:
        """`stats`, when given, receives phase seconds and counts only, never text."""
        stats = {} if stats is None else stats
        if not query.strip() or document_ids == []:
            return []
        started = time.perf_counter()
        with connect(self.config) as db:
            if not db.execute("SELECT 1 FROM workspaces WHERE id=?", (workspace_id,)).fetchone():
                raise ValueError("Workspace not found")
            for row in db.execute(
                "SELECT id,path FROM documents WHERE workspace_id=? AND status='indexed'",
                (workspace_id,),
            ).fetchall():
                if not Path(row["path"]).is_file():
                    db.execute("UPDATE documents SET status='missing' WHERE id=?", (row["id"],))
            if stale_index(db, workspace_id):
                raise ByodError("STALE_INDEX")
            sql = (
                "SELECT c.id FROM chunks c JOIN documents d ON d.id=c.document_id "
                "WHERE d.workspace_id=? AND d.status='indexed'"
            )
            params: list[object] = [workspace_id]
            if document_ids is not None:
                sql += " AND d.id IN (SELECT value FROM json_each(?))"
                params.append(json.dumps(document_ids))
            if doc_type is not None:
                sql += " AND d.doc_type=?"
                params.append(doc_type)
            candidates = [int(row[0]) for row in db.execute(sql, params)]
        stats["candidates"] = time.perf_counter() - started
        stats["candidate_count"] = len(candidates)
        if not candidates:
            return []
        started = time.perf_counter()
        vector = self.embedder.embed([query])[0]
        stats["embed"] = time.perf_counter() - started
        started = time.perf_counter()
        with connect(self.config) as db:
            # Candidate IDs, vector results, and source text share one read snapshot.
            # Refresh the candidates after inference to account for concurrent writes.
            db.execute("BEGIN")
            if stale_index(db, workspace_id):
                raise ByodError("STALE_INDEX")
            candidates = [int(row[0]) for row in db.execute(sql, params)]
            stats["candidates"] += time.perf_counter() - started
            started = time.perf_counter()
            ranked = SqliteVecStore(db).search(vector, k, candidates)
            stats["search"] = time.perf_counter() - started
            started = time.perf_counter()
            rows = {
                int(row["id"]): row
                for row in db.execute(
                    "SELECT c.*,d.filename FROM chunks c JOIN documents d ON d.id=c.document_id "
                    "WHERE c.id IN (SELECT value FROM json_each(?))",
                    (json.dumps([identifier for identifier, _ in ranked]),),
                )
            }
        minimum_score = self.config.preferences().retrieval_min_score
        result = []
        for chunk_id, distance in ranked:
            score = max(-1.0, min(1.0, 1 - distance * distance / 2))
            if score < minimum_score or chunk_id not in rows:
                continue
            row = rows[chunk_id]
            result.append(
                SearchResult(
                    chunk_id,
                    int(row["document_id"]),
                    row["filename"],
                    row["locator"],
                    int(row["ordinal"]),
                    row["text"],
                    int(row["token_count"]),
                    score,
                )
            )
        stats["hydrate"] = time.perf_counter() - started
        return result

    def context(
        self, results: list[SearchResult], budget: int = 8000
    ) -> tuple[str, list[SearchResult]]:
        if not results:
            return "", []
        counter = TokenCounter(self.config)
        document_order = list(dict.fromkeys(r.document_id for r in results))
        ordered = sorted(results, key=lambda r: (document_order.index(r.document_id), -r.ordinal))
        included: list[SearchResult] = []
        sections: list[str] = []
        for result in ordered:
            section = f"{result.citation}\n{result.text}"
            if counter.count("\n\n".join(sections + [section])) > budget:
                continue
            sections.append(section)
            included.append(result)
        return "\n\n".join(sections), included
