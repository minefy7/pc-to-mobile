"""Позволяет запускать сервер через `python -m app`."""

import sys

import uvicorn

from app.config import HOST, PORT
from app.utils import lan_urls


def main() -> None:
    for url in lan_urls(PORT):
        label = "Local" if "127.0.0.1" in url else "LAN"
        print(f"{label}: {url}")
    print(f"Local: http://127.0.0.1:{PORT}")
    uvicorn.run("app.main:app", host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
