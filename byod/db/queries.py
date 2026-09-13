"""Workspace persistence, shared by CLI and API."""

import sqlite3


def create_workspace(db: sqlite3.Connection, name: str) -> int:
    name = name.strip()
    if not name or len(name) > 200:
        raise ValueError("Workspace name must contain 1 to 200 characters.")
    cursor = db.execute("INSERT INTO workspaces(name) VALUES (?)", (name,))
    if cursor.lastrowid is None:
        raise RuntimeError("Workspace creation failed.")
    return cursor.lastrowid


def list_workspaces(db: sqlite3.Connection) -> list[dict[str, object]]:
    return [
        dict(row)
        for row in db.execute(
            "SELECT w.*, count(d.id) AS document_count FROM workspaces w "
            "LEFT JOIN documents d ON d.workspace_id=w.id GROUP BY w.id ORDER BY w.name"
        )
    ]
