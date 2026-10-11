"""Настройки приложения: пути, порт, лимиты."""

from __future__ import annotations

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT_DIR / "static"
UPLOADS_DIR = ROOT_DIR / "uploads"
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "chat.db"

HOST: str = os.environ.get("CHAT_HOST", "0.0.0.0")
PORT: int = int(os.environ.get("CHAT_PORT", "8000"))
MAX_UPLOAD_MB: int = int(os.environ.get("CHAT_MAX_UPLOAD_MB", "200"))
MAX_UPLOAD_BYTES: int = MAX_UPLOAD_MB * 1024 * 1024
PAGE_SIZE: int = int(os.environ.get("CHAT_PAGE_SIZE", "50"))
TYPING_TIMEOUT: float = float(os.environ.get("CHAT_TYPING_TIMEOUT", "2.5"))
MAX_NAME_LENGTH: int = 40
MAX_MESSAGE_LENGTH: int = 4000


def ensure_dirs() -> None:
    """Создаёт каталоги, необходимые для работы сервера."""

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
