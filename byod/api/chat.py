from typing import cast

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from byod.db.migrations import connect
from byod.llm.chat import ChatService, citations

router = APIRouter(prefix="/api")


class MessageInput(BaseModel):
    content: str = Field(min_length=1, max_length=16000)
    document_ids: list[int] | None = Field(default=None, max_length=1000)


@router.get("/workspaces/{workspace_id}/chats")
def list_chats(workspace_id: int, request: Request) -> list[dict[str, object]]:
    with connect(request.app.state.config) as db:
        if not db.execute("SELECT 1 FROM workspaces WHERE id=?", (workspace_id,)).fetchone():
            raise HTTPException(404, "Workspace not found. Select another workspace.")
        return [
            dict(row)
            for row in db.execute(
                "SELECT id,title,updated_at FROM chats WHERE workspace_id=? "
                "ORDER BY updated_at DESC,id DESC",
                (workspace_id,),
            )
        ]


@router.post("/workspaces/{workspace_id}/chats", status_code=201)
def create_chat(workspace_id: int, request: Request) -> dict[str, int]:
    with connect(request.app.state.config) as db:
        if not db.execute("SELECT 1 FROM workspaces WHERE id=?", (workspace_id,)).fetchone():
            raise HTTPException(404, "Workspace not found. Select another workspace.")
        cursor = db.execute("INSERT INTO chats(workspace_id) VALUES (?)", (workspace_id,))
        if cursor.lastrowid is None:
            raise HTTPException(500, "Couldn't create chat. Retry.")
        return {"id": cursor.lastrowid}


@router.get("/chats/{chat_id}/messages")
def messages(chat_id: int, request: Request) -> list[dict[str, object]]:
    with connect(request.app.state.config) as db:
        if not db.execute("SELECT 1 FROM chats WHERE id=?", (chat_id,)).fetchone():
            raise HTTPException(404, "Chat not found. Select another chat.")
        result = []
        for row in db.execute(
            "SELECT id,role,content,created_at FROM messages WHERE chat_id=? ORDER BY id",
            (chat_id,),
        ).fetchall():
            item = dict(row)
            item["citations"] = citations(db, row["id"])
            result.append(item)
        return result


@router.post("/chats/{chat_id}/messages")
def post_message(chat_id: int, body: MessageInput, request: Request) -> StreamingResponse:
    if not body.content.strip():
        raise HTTPException(422, "Enter a question.")
    with connect(request.app.state.config) as db:
        row = db.execute("SELECT workspace_id FROM chats WHERE id=?", (chat_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Chat not found. Select another chat.")
        if body.document_ids:
            valid = {
                int(r[0])
                for r in db.execute("SELECT id FROM documents WHERE workspace_id=?", (row[0],))
            }
            if not set(body.document_ids).issubset(valid):
                raise HTTPException(422, "Document filter must belong to this workspace.")
    service = cast(ChatService, request.app.state.chat)
    return StreamingResponse(
        service.stream(chat_id, body.content, body.document_ids),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.delete("/chats/{chat_id}", status_code=204)
def delete_chat(chat_id: int, request: Request) -> Response:
    with connect(request.app.state.config) as db:
        if not db.execute("DELETE FROM chats WHERE id=?", (chat_id,)).rowcount:
            raise HTTPException(404, "Chat not found. Refresh the chat list.")
    return Response(status_code=204)
