"""Forward-only, transactional migrations and short-lived connections."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import sqlite_vec

from byod.config import Config

MIGRATIONS = [(1, Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))]


@contextmanager
def connect(config: Config) -> Iterator[sqlite3.Connection]:
    db = sqlite3.connect(config.database, timeout=30)
    try:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.enable_load_extension(True)
        try:
            sqlite_vec.load(db)
        finally:
            db.enable_load_extension(False)
        with db:
            yield db
    finally:
        db.close()


def initialize(config: Config) -> None:
    config.initialize_directories()
    with connect(config) as db:
        db.execute("PRAGMA journal_mode = WAL")
        db.execute("BEGIN IMMEDIATE")
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ).fetchone()
        version = db.execute("SELECT version FROM schema_version").fetchone()[0] if exists else 0
        if version > MIGRATIONS[-1][0]:
            raise RuntimeError("Database is newer than this BYOD version. Update BYOD.")
        for target, script in MIGRATIONS:
            if target <= version:
                continue
            # executescript implicitly commits, so execute complete statements instead.
            statement = ""
            for line in script.splitlines(keepends=True):
                statement += line
                if sqlite3.complete_statement(statement):
                    db.execute(statement)
                    statement = ""
            if statement.strip():
                raise RuntimeError("Incomplete database migration.")
            db.execute("UPDATE schema_version SET version = ?", (target,))
