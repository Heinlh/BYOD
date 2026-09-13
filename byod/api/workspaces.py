import sqlite3

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from byod.db.migrations import connect
from byod.db.queries import create_workspace, list_workspaces

router = APIRouter(prefix="/api")


class WorkspaceInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)


@router.get("/workspaces")
def workspaces(request: Request) -> list[dict[str, object]]:
    with connect(request.app.state.config) as db:
        return list_workspaces(db)


@router.post("/workspaces", status_code=201)
def add_workspace(body: WorkspaceInput, request: Request) -> dict[str, object]:
    try:
        with connect(request.app.state.config) as db:
            identifier = create_workspace(db, body.name)
            return {"id": identifier, "name": body.name.strip()}
    except ValueError:
        raise HTTPException(422, "Enter a workspace name.") from None
    except sqlite3.IntegrityError:
        raise HTTPException(
            409, "A workspace with this name exists. Choose another name."
        ) from None


@router.delete("/workspaces/{workspace_id}", status_code=204)
def delete_workspace(workspace_id: int, request: Request) -> Response:
    with connect(request.app.state.config) as db:
        if not db.execute("DELETE FROM workspaces WHERE id=?", (workspace_id,)).rowcount:
            raise HTTPException(404, "Workspace not found. Select another workspace.")
    with request.app.state.config.edit_preferences() as preferences:
        preferences.workspaces.pop(str(workspace_id), None)
    return Response(status_code=204)
