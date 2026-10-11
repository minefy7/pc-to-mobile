#!/usr/bin/env python3
"""Точка входа: печатает локальные адреса и запускает Uvicorn."""

from __future__ import annotations

import sys
import webbrowser

import uvicorn

from app.config import HOST, PORT
from app.utils import lan_urls


def main() -> None:
    urls = lan_urls(PORT)
    print("=" * 46)
    print("  Чат запущен")
    for url in urls:
        label = "Local" if "127.0.0.1" in url else "LAN"
        print(f"  {label}: {url}")
    print("=" * 46)
    print("  Откройте LAN-адрес в браузере телефона. Ctrl+C — остановить.")
    print()

    if "--no-browser" not in sys.argv:
        try:
            webbrowser.open(f"http://127.0.0.1:{PORT}")
        except Exception:
            pass

    uvicorn.run("app.main:app", host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
