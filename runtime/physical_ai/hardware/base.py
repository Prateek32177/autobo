"""Hardware adapter protocol — shared by mock and future serial adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from physical_ai.core.models import ProtocolCommand, ProtocolCommandResult


TelemetryHandler = Callable[[dict[str, Any]], Awaitable[None]]
HeartbeatHandler = Callable[[dict[str, Any]], Awaitable[None]]


class HardwareAdapter(ABC):
    """Abstract hardware transport.

    Implementations must make simulation vs real hardware explicit via
    ``mode`` and must never silently fall back between them.
    """

    mode: str  # "simulation" | "serial"

    @abstractmethod
    async def connect(self) -> None:
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        ...

    @abstractmethod
    async def is_connected(self) -> bool:
        ...

    @abstractmethod
    async def send_command(self, command: ProtocolCommand) -> ProtocolCommandResult:
        ...

    @abstractmethod
    async def emergency_stop(self, reason: str = "operator") -> None:
        ...

    def on_telemetry(self, handler: TelemetryHandler) -> None:
        self._telemetry_handler = handler

    def on_heartbeat(self, handler: HeartbeatHandler) -> None:
        self._heartbeat_handler = handler

    async def _emit_telemetry(self, payload: dict[str, Any]) -> None:
        handler = getattr(self, "_telemetry_handler", None)
        if handler is not None:
            await handler(payload)

    async def _emit_heartbeat(self, payload: dict[str, Any]) -> None:
        handler = getattr(self, "_heartbeat_handler", None)
        if handler is not None:
            await handler(payload)
