"""FastAPI-приложение: REST, WebSocket и статика."""

from __future__ import annotations

import json
import mimetypes
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import (
    FastAPI,
    File,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import db, utils
from app.config import (
    MAX_MESSAGE_LENGTH,
    MAX_NAME_LENGTH,
    MAX_UPLOAD_BYTES,
    PAGE_SIZE,
    STATIC_DIR,
    UPLOADS_DIR,
    ensure_dirs,
)
from app.ws_manager import manager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    ensure_dirs()
    db.connect()
    db.init_schema()
    yield
    await manager.broadcast({"type": "shutdown"})
    db.close()


app = FastAPI(title="Чат", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/history")
async def history(before: str | None = None, limit: int = PAGE_SIZE) -> dict:
    return {"messages": db.list_messages(before=before, limit=limit)}


@app.post("/api/upload")
async def upload(request: Request, file: UploadFile = File(...)) -> dict:
    sender = (request.query_params.get("name") or "").strip()[:MAX_NAME_LENGTH] or "Гость"
    length_header = request.headers.get("content-length")
    if length_header is None:
        raise HTTPException(status_code=411, detail="Требуется Content-Length")
    try:
        declared = int(length_header)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Некорректный Content-Length") from exc
    if declared > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Файл больше лимита {MAX_UPLOAD_BYTES // (1024 * 1024)} МБ",
        )

    file_id = uuid.uuid4().hex
    stored_name = utils.safe_filename(file.filename or "file", file_id)
    target = UPLOADS_DIR / stored_name
    written = 0
    try:
        with target.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Файл больше лимита {MAX_UPLOAD_BYTES // (1024 * 1024)} МБ",
                    )
                out.write(chunk)
    except HTTPException:
        target.unlink(missing_ok=True)
        raise
    except Exception:
        target.unlink(missing_ok=True)
        raise

    if written == 0:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Пустой файл")

    mime_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
    record = db.add_file(
        stored_name=stored_name,
        original_name=(file.filename or "file")[:255],
        size=written,
        mime_type=mime_type,
    )
    message = db.add_message(
        sender=sender,
        kind="file",
        text=f"Файл: {record['original_name']}",
        file_id=record["id"],
        file_name=record["original_name"],
        file_size=record["size"],
        mime_type=record["mime_type"],
    )
    await manager.broadcast({"type": "message", "message": message})
    return {"file_id": record["id"], "message": message}


@app.get("/files/{file_id}")
async def download(file_id: str) -> FileResponse:
    try:
        uuid.UUID(file_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Файл не найден") from exc
    record = db.get_file(file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Файл не найден")
    path = UPLOADS_DIR / record["stored_name"]
    if not path.is_file() or path.parent != UPLOADS_DIR:
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(
        path,
        media_type=record["mime_type"],
        filename=record["original_name"],
        content_disposition_type="attachment" if not record["mime_type"].startswith("image/") else "inline",
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    client_id = uuid.uuid4().hex
    name = (websocket.query_params.get("name") or "Гость").strip()[:MAX_NAME_LENGTH] or "Гость"
    await manager.connect(websocket, client_id, name)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "detail": "Некорректный JSON"}))
                continue
            kind = payload.get("type")
            if kind == "message":
                text = str(payload.get("text", ""))[:MAX_MESSAGE_LENGTH].strip()
                if not text:
                    continue
                message = db.add_message(sender=name, kind="message", text=text)
                await manager.broadcast({"type": "message", "message": message})
            elif kind == "typing":
                if payload.get("active", True):
                    await manager.typing_start(client_id)
                    await manager.broadcast(
                        {"type": "typing", "sender": name, "active": True},
                        exclude=client_id,
                    )
            elif kind == "presence":
                await websocket.send_text(
                    json.dumps({"type": "presence", "users": manager.online_users()})
                )
            elif kind == "rename":
                new_name = str(payload.get("name", "")).strip()[:MAX_NAME_LENGTH]
                if new_name:
                    name = new_name
                    await manager.rename(client_id, new_name)
                    await manager.broadcast({"type": "presence", "users": manager.online_users()})
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(client_id)
