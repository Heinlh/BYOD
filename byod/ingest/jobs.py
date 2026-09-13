"""One worker thread; hashing, parsing and indexing never run in HTTP handlers."""

import copy
import hashlib
import queue
import sqlite3
import threading
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from byod.config import Config
from byod.db.migrations import connect
from byod.errors import ByodError
from byod.ingest.chunk import Chunk, chunk
from byod.ingest.normalize import document_type, parse
from byod.model_files import Progress
from byod.tokenize import TokenCounter

Indexer = Callable[[sqlite3.Connection, int, list[Chunk], Progress], None]


@dataclass
class Job:
    state: str = "queued"
    total: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    current_file: str | None = None
    errors: list[dict[str, str]] = field(default_factory=list)
    download: dict[str, str | int] | None = None


class JobQueue:
    def __init__(self, config: Config, indexer: Indexer | None = None) -> None:
        self.config = config
        self.indexer = indexer
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._queue: queue.Queue[tuple[str, int, list[str], bool] | None] = queue.Queue()
        self._thread = threading.Thread(target=self._work, name="byod-ingest", daemon=True)
        self._thread.start()

    def submit(self, workspace_id: int, paths: list[str], reindex: bool = False) -> str:
        identifier = uuid.uuid4().hex
        with self._lock:
            self._jobs[identifier] = Job()
        self._queue.put((identifier, workspace_id, paths, reindex))
        return identifier

    def snapshot(self, identifier: str) -> dict[str, object] | None:
        with self._lock:
            job = self._jobs.get(identifier)
            return copy.deepcopy(asdict(job)) if job else None

    def close(self) -> None:
        self._queue.put(None)
        self._thread.join()  # Finish the current job before process shutdown.

    def wait(self) -> None:
        self._queue.join()

    def _update(self, identifier: str, **values: object) -> None:
        with self._lock:
            for key, value in values.items():
                setattr(self._jobs[identifier], key, value)

    def _work(self) -> None:
        while True:
            task = self._queue.get()
            try:
                if task is None:
                    return
                identifier, workspace, paths, reindex = task
                self._update(identifier, state="running")
                try:
                    files: list[Path] = []
                    for raw in paths:
                        path = Path(raw).expanduser()
                        # UNC paths may make network calls outside allowed runtime destinations.
                        if str(path).startswith(("\\\\", "//")):
                            raise ByodError("FILE_NOT_FOUND")
                        if path.is_dir():
                            for child in sorted(path.rglob("*")):
                                if child.is_file() and not child.is_symlink():
                                    try:
                                        document_type(child)
                                        files.append(child.resolve())
                                    except ByodError:
                                        continue
                        else:
                            files.append(path.resolve())
                    files = list(dict.fromkeys(files))
                    self._update(identifier, total=len(files))
                    for path in files:
                        self._update(identifier, current_file=path.name)
                        try:
                            skipped = self._ingest(identifier, workspace, path, reindex)
                            with self._lock:
                                self._jobs[identifier].completed += 1
                                self._jobs[identifier].skipped += int(skipped)
                        except Exception as exc:
                            self._record_failure(identifier, path.name, exc)
                    with self._lock:
                        failed = self._jobs[identifier].failed
                    self._update(
                        identifier, state="failed" if failed else "done", current_file=None
                    )
                except Exception as exc:
                    self._record_failure(identifier, "", exc)
                    self._update(identifier, state="failed", current_file=None)
            finally:
                self._queue.task_done()

    def _record_failure(self, identifier: str, filename: str, exc: Exception) -> None:
        error = exc if isinstance(exc, ByodError) else ByodError("INGEST_FAILED")
        with self._lock:
            self._jobs[identifier].failed += 1
            self._jobs[identifier].errors.append(
                {"filename": filename, "code": error.code, "message": error.message}
            )

    def _ingest(self, identifier: str, workspace: int, path: Path, reindex: bool) -> bool:
        kind = document_type(path)
        if not path.is_file():
            raise ByodError("FILE_NOT_FOUND")
        with path.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        with connect(self.config) as db:
            row = db.execute(
                "SELECT id,status,chunk_count FROM documents "
                "WHERE workspace_id=? AND content_hash=?",
                (workspace, digest),
            ).fetchone()
            if row is None and reindex:
                row = db.execute(
                    "SELECT id,status,chunk_count FROM documents WHERE workspace_id=? AND path=?",
                    (workspace, str(path)),
                ).fetchone()
                if row:
                    db.execute(
                        "UPDATE documents SET content_hash=? WHERE id=?", (digest, row["id"])
                    )
            if (
                row
                and not reindex
                and (
                    row["status"] == "indexed" or (self.indexer is None and row["chunk_count"] > 0)
                )
            ):
                db.execute(
                    "UPDATE documents SET path=?,filename=? WHERE id=?",
                    (str(path), path.name, row["id"]),
                )
                return True
            if row:
                document_id = int(row["id"])
                db.execute(
                    "UPDATE documents SET path=?,filename=? WHERE id=?",
                    (str(path), path.name, document_id),
                )
            else:
                cursor = db.execute(
                    "INSERT INTO documents(workspace_id,filename,path,doc_type,content_hash) "
                    "VALUES (?,?,?,?,?)",
                    (workspace, path.name, str(path), kind, digest),
                )
                if cursor.lastrowid is None:
                    raise ByodError("INGEST_FAILED")
                document_id = cursor.lastrowid
        try:
            counter = TokenCounter(
                self.config,
                progress=lambda name, done, total: self._update(
                    identifier, download={"file": name, "completed": done, "total": total}
                ),
            )
            blocks = parse(path)
            chunks = chunk(blocks, kind, counter)
            with path.open("rb") as source:
                if hashlib.file_digest(source, "sha256").hexdigest() != digest:
                    raise ByodError("INGEST_FAILED")
            with connect(self.config) as db:
                if not db.execute("SELECT 1 FROM documents WHERE id=?", (document_id,)).fetchone():
                    return True  # Document/workspace was removed while parsing.
                db.execute("DELETE FROM chunks WHERE document_id=?", (document_id,))
                db.executemany(
                    "INSERT INTO chunks(document_id,ordinal,text,locator,block_type,token_count) "
                    "VALUES (?,?,?,?,?,?)",
                    [
                        (document_id, c.ordinal, c.text, c.locator, c.block_type, c.token_count)
                        for c in chunks
                    ],
                )
                units = blocks[0].unit_count
                db.execute(
                    "UPDATE documents SET chunk_count=?,unit_count=?,error=NULL,"
                    "status='pending',embed_model=NULL,embed_version=NULL,"
                    "ingested_at=datetime('now') WHERE id=?",
                    (len(chunks), units, document_id),
                )
                if self.indexer:
                    self.indexer(
                        db,
                        document_id,
                        chunks,
                        lambda name, done, total: self._update(
                            identifier, download={"file": name, "completed": done, "total": total}
                        ),
                    )
            return False
        except Exception as exc:
            error = exc if isinstance(exc, ByodError) else ByodError("INGEST_FAILED")
            with connect(self.config) as db:
                db.execute("DELETE FROM chunks WHERE document_id=?", (document_id,))
                db.execute(
                    "UPDATE documents SET status='failed',error=?,chunk_count=0,"
                    "embed_model=NULL,embed_version=NULL WHERE id=?",
                    (error.message, document_id),
                )
            raise error from None
