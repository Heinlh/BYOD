from pathlib import Path
from typing import cast

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from byod.db.migrations import connect
from byod.ingest.jobs import JobQueue

router = APIRouter(prefix="/api")


class PathsInput(BaseModel):
    paths: list[str] = Field(min_length=1, max_length=1000)


@router.get("/workspaces/{workspace_id}/documents")
def documents(workspace_id: int, request: Request) -> list[dict[str, object]]:
    with connect(request.app.state.config) as db:
        if not db.execute("SELECT 1 FROM workspaces WHERE id=?", (workspace_id,)).fetchone():
            raise HTTPException(404, "Workspace not found. Select another workspace.")
        rows = db.execute(
            "SELECT * FROM documents WHERE workspace_id=? ORDER BY filename", (workspace_id,)
        ).fetchall()
        for row in rows:
            if not Path(row["path"]).is_file():
                db.execute("UPDATE documents SET status='missing' WHERE id=?", (row["id"],))
        return [
            dict(row)
            for row in db.execute(
                "SELECT id,filename,doc_type,unit_count,chunk_count,status,error,ingested_at "
                "FROM documents WHERE workspace_id=? ORDER BY filename",
                (workspace_id,),
            )
        ]


@router.post("/workspaces/{workspace_id}/documents", status_code=202)
def add_documents(workspace_id: int, body: PathsInput, request: Request) -> dict[str, str]:
    with connect(request.app.state.config) as db:
        if not db.execute("SELECT 1 FROM workspaces WHERE id=?", (workspace_id,)).fetchone():
            raise HTTPException(404, "Workspace not found. Select another workspace.")
    jobs = cast(JobQueue, request.app.state.jobs)
    return {"job_id": jobs.submit(workspace_id, body.paths)}


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: int, request: Request) -> Response:
    with connect(request.app.state.config) as db:
        if not db.execute("DELETE FROM documents WHERE id=?", (document_id,)).rowcount:
            raise HTTPException(404, "Document not found. Refresh the document list.")
    return Response(status_code=204)


@router.post("/documents/{document_id}/reindex", status_code=202)
def reindex_document(document_id: int, request: Request) -> dict[str, str]:
    with connect(request.app.state.config) as db:
        row = db.execute(
            "SELECT workspace_id,path FROM documents WHERE id=?", (document_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Document not found. Refresh the document list.")
    jobs = cast(JobQueue, request.app.state.jobs)
    return {"job_id": jobs.submit(row["workspace_id"], [row["path"]], reindex=True)}


@router.get("/chunks/{chunk_id}")
def get_chunk(chunk_id: int, request: Request) -> dict[str, object]:
    with connect(request.app.state.config) as db:
        row = db.execute(
            "SELECT c.text,c.locator,d.filename,c.document_id FROM chunks c "
            "JOIN documents d ON d.id=c.document_id WHERE c.id=?",
            (chunk_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Source not found. It may have been removed or re-indexed.")
        return dict(row)


@router.get("/jobs/{job_id}")
def job_status(job_id: str, request: Request) -> dict[str, object]:
    job = cast(JobQueue, request.app.state.jobs).snapshot(job_id)
    if job is None:
        raise HTTPException(404, "Job not found. Re-add the files if BYOD restarted.")
    return job
