"""SQLite: инициализация схемы, история сообщений, файлы."""

from __future__ import annotations

import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import DB_PATH, PAGE_SIZE, ensure_dirs


_lock = threading.Lock()
_connection: sqlite3.Connection | None = None


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Открывает (и создаёт при необходимости) соединение с БД."""

    global _connection
    ensure_dirs()
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _connection = conn
    return conn


def init_schema() -> None:
    """Создаёт таблицы, если их ещё нет."""

    if _connection is None:
        connect()
    assert _connection is not None
    with _lock, _connection:
        _connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                sender TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'message',
                text TEXT NOT NULL DEFAULT '',
                file_id TEXT,
                file_name TEXT,
                file_size INTEGER,
                mime_type TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_messages_created
                ON messages(created_at DESC);

            CREATE TABLE IF NOT EXISTS files (
                id TEXT PRIMARY KEY,
                stored_name TEXT NOT NULL,
                original_name TEXT NOT NULL,
                size INTEGER NOT NULL,
                mime_type TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )


def close() -> None:
    global _connection
    if _connection is not None:
        with _lock:
            _connection.close()
        _connection = None


def _conn() -> sqlite3.Connection:
    if _connection is None:
        raise RuntimeError("БД не инициализирована")
    return _connection


def add_message(
    *,
    sender: str,
    kind: str = "message",
    text: str = "",
    file_id: str | None = None,
    file_name: str | None = None,
    file_size: int | None = None,
    mime_type: str | None = None,
) -> dict[str, Any]:
    """Добавляет сообщение (текст или файл) и возвращает его словарём."""

    message_id = uuid.uuid4().hex
    created_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    with _lock, _conn() as conn:
        conn.execute(
            """
            INSERT INTO messages
                (id, sender, kind, text, file_id, file_name, file_size, mime_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                sender,
                kind,
                text,
                file_id,
                file_name,
                file_size,
                mime_type,
                created_at,
            ),
        )
    return {
        "id": message_id,
        "sender": sender,
        "kind": kind,
        "text": text,
        "file_id": file_id,
        "file_name": file_name,
        "file_size": file_size,
        "mime_type": mime_type,
        "created_at": created_at,
    }


def list_messages(before: str | None = None, limit: int = PAGE_SIZE) -> list[dict[str, Any]]:
    """Возвращает последние `limit` сообщений (при `before` — старше указанного id)."""

    limit = max(1, min(limit, 500))
    with _lock:
        if before:
            rows = _conn().execute(
                """
                SELECT * FROM messages
                WHERE (created_at, id) < (
                    SELECT created_at, id FROM messages WHERE id = ?
                )
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (before, limit),
            ).fetchall()
        else:
            rows = _conn().execute(
                "SELECT * FROM messages ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    messages = [_row_to_dict(row) for row in rows]
    messages.reverse()
    return messages


def get_file(file_id: str) -> dict[str, Any] | None:
    with _lock:
        row = _conn().execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
    return _row_to_dict(row) if row else None


def add_file(stored_name: str, original_name: str, size: int, mime_type: str) -> dict[str, Any]:
    file_id = uuid.uuid4().hex
    created_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    with _lock, _conn() as conn:
        conn.execute(
            """
            INSERT INTO files (id, stored_name, original_name, size, mime_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (file_id, stored_name, original_name, size, mime_type, created_at),
        )
    return {
        "id": file_id,
        "stored_name": stored_name,
        "original_name": original_name,
        "size": size,
        "mime_type": mime_type,
        "created_at": created_at,
    }
