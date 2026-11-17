"""In-memory transport for mock devices and unit tests."""

from __future__ import annotations

import asyncio

from physical_ai.hardware.transport.base import (
    TransportAdapter,
    TransportError,
    TransportState,
    TransportTimeout,
)


class MemoryTransport(TransportAdapter):
    """Bidirectional line queue pair (host <-> peer)."""

    def __init__(self) -> None:
        self._inbound: asyncio.Queue[str] = asyncio.Queue()
        self._outbound: asyncio.Queue[str] = asyncio.Queue()
        self._state = TransportState.DISCONNECTED
        self._peer: MemoryTransport | None = None

    @classmethod
    def pair(cls) -> tuple[MemoryTransport, MemoryTransport]:
        host = cls()
        peer = cls()
        host._peer = peer
        peer._peer = host
        # Host reads from peer writes: host inbound = peer outbound
        host._inbound = peer._outbound
        peer._inbound = host._outbound
        return host, peer

    async def connect(self) -> None:
        self._state = TransportState.CONNECTED

    async def disconnect(self) -> None:
        self._state = TransportState.DISCONNECTED

    def state(self) -> TransportState:
        return self._state

    async def write_line(self, line: str) -> None:
        if self._state != TransportState.CONNECTED:
            raise TransportError("Transport not connected")
        payload = line.rstrip("\n")
        await self._outbound.put(payload)

    async def read_line(self, timeout: float | None = None) -> str:
        if self._state != TransportState.CONNECTED:
            raise TransportError("Transport not connected")
        try:
            if timeout is None:
                return await self._inbound.get()
            return await asyncio.wait_for(self._inbound.get(), timeout=timeout)
        except TimeoutError as exc:
            raise TransportTimeout(f"read_line timed out after {timeout}s") from exc
