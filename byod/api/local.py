"""User-triggered native file opening, using persisted paths only."""

import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from byod.db.migrations import connect

router = APIRouter(prefix="/api")


def open_local(path: Path) -> None:
    if not path.exists():
        raise HTTPException(404, "File moved or deleted. Re-add it.")
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # noqa: S606 - user-triggered opening of a persisted path
        else:
            executable = "/usr/bin/open" if sys.platform == "darwin" else "/usr/bin/xdg-open"
            subprocess.Popen(  # noqa: S603
                [executable, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
    except OSError:
        raise HTTPException(
            503, "Couldn't open the source. Open it in your file manager."
        ) from None


@router.post("/documents/{document_id}/open")
def open_document(document_id: int, request: Request) -> dict[str, bool]:
    with connect(request.app.state.config) as db:
        row = db.execute("SELECT path FROM documents WHERE id=?", (document_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Document not found. Refresh the document list.")
    open_local(Path(row["path"]))
    return {"opened": True}


@router.post("/settings/reveal")
def reveal_data(request: Request) -> dict[str, bool]:
    open_local(request.app.state.config.data_dir)
    return {"opened": True}
