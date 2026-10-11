"""Менеджер WebSocket-подключений: presence, typing, broadcast."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket


@dataclass(slots=True)
class Client:
    socket: WebSocket
    client_id: str
    name: str
    typing_until: float = 0.0


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: dict[str, Client] = {}
        self._typing_tasks: dict[str, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, socket: WebSocket, client_id: str, name: str) -> Client:
        await socket.accept()
        client = Client(socket=socket, client_id=client_id, name=name)
        async with self._lock:
            self._clients[client_id] = client
        await self._send(
            socket,
            {"type": "presence", "users": self.online_users()},
        )
        await self.broadcast(
            {"type": "presence", "users": self.online_users()},
            exclude=client_id,
        )
        return client

    async def disconnect(self, client_id: str) -> None:
        async with self._lock:
            self._clients.pop(client_id, None)
        task = self._typing_tasks.pop(client_id, None)
        if task and not task.done():
            task.cancel()
        await self.broadcast(
            {"type": "presence", "users": self.online_users()},
        )

    def online_users(self) -> list[str]:
        return sorted({client.name for client in self._clients.values()})

    async def broadcast(self, payload: dict[str, Any], exclude: str | None = None) -> None:
        data = json.dumps(payload, ensure_ascii=False)
        for client in list(self._clients.values()):
            if client.client_id == exclude:
                continue
            try:
                await client.socket.send_text(data)
            except Exception:
                await self.disconnect(client.client_id)

    async def send_to(self, client_id: str, payload: dict[str, Any]) -> None:
        client = self._clients.get(client_id)
        if client:
            await self._send(client.socket, payload)

    async def rename(self, client_id: str, name: str) -> None:
        client = self._clients.get(client_id)
        if client is not None:
            client.name = name

    @staticmethod
    async def _send(socket: WebSocket, payload: dict[str, Any]) -> None:
        await socket.send_text(json.dumps(payload, ensure_ascii=False))

    async def typing_start(self, client_id: str) -> None:
        client = self._clients.get(client_id)
        if client is None:
            return
        old = self._typing_tasks.pop(client_id, None)
        if old and not old.done():
            old.cancel()
        self._typing_tasks[client_id] = asyncio.create_task(
            self._typing_broadcast(client_id)
        )

    async def _typing_broadcast(self, client_id: str) -> None:
        try:
            await asyncio.sleep(2.5)
        except asyncio.CancelledError:
            return
        self._typing_tasks.pop(client_id, None)
        await self.broadcast(
            {"type": "typing", "sender": self._clients[client_id].name, "active": False}
            if client_id in self._clients
            else {"type": "typing", "sender": "", "active": False},
            exclude=client_id,
        )


manager = ConnectionManager()
