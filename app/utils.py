"""Вспомогательные функции: безопасные имена файлов и LAN IP."""

from __future__ import annotations

import fcntl
import re
import socket
import struct
import uuid
from pathlib import Path


SAFE_NAME_RE = re.compile(r"[^\w.-]+", re.UNICODE)


def safe_filename(raw_name: str, file_id: str | None = None) -> str:
    """Возвращает имя вида `<uuid>-<sanitized>.<ext>` для записи на диск."""

    file_id = file_id or uuid.uuid4().hex
    name = Path(raw_name or "file").name
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    stem = SAFE_NAME_RE.sub("_", stem).strip("._") or "file"
    if len(stem.encode("utf-8")) > 120:  # держим имя в пределах 255 байт
        encoded = stem.encode("utf-8")[:120].decode("utf-8", "ignore")
        stem = encoded or "file"
    ext = SAFE_NAME_RE.sub("", ext.lower())[:32]
    suffix = f".{ext}" if ext else ""
    return f"{file_id}-{stem[:80]}{suffix}"


def lan_addresses() -> list[str]:
    """Возвращает локальные IPv4-адреса через SIOCGIFADDR (Linux)."""

    addresses: set[str] = set()
    try:
        import struct as _struct

        max_possible = 32
        for index in range(1, max_possible + 1):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    request = _struct.pack("256s", f"eth{index}".encode("utf-8")[:15])
                    response = fcntl.ioctl(
                        sock.fileno(),
                        0x8915,  # SIOCGIFADDR
                        request,
                    )
                    ip = socket.inet_ntoa(response[20:24])
                    if ip and not ip.startswith("127."):
                        addresses.add(ip)
                finally:
                    sock.close()
            except OSError:
                continue
    except Exception:
        pass

    # Более надёжный вариант — перечислить все интерфейсы через getaddrinfo.
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127."):
                addresses.add(ip)
    except OSError:
        pass

    # Фоллбэк: hostname -I (inetutils) или gethostbyname.
    if not addresses:
        try:
            import subprocess

            out = subprocess.run(
                ["hostname", "-I"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            for token in out.stdout.split():
                if token and not token.startswith("127."):
                    addresses.add(token)
        except (OSError, subprocess.SubprocessError):
            pass
    if not addresses:
        try:
            ip = socket.gethostbyname(socket.gethostname())
            if ip and not ip.startswith("127."):
                addresses.add(ip)
        except OSError:
            pass

    return sorted(addresses)


def lan_urls(port: int) -> list[str]:
    """Полные URL для открытия с телефона."""

    return [f"http://{ip}:{port}" for ip in lan_addresses()] or [
        f"http://127.0.0.1:{port}"
    ]
