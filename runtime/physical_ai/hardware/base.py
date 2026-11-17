"""Hardware adapter facade — coordinates transport, protocol and components."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from physical_ai.core.models import ProtocolCommand, ProtocolCommandResult

TelemetryHandler = Callable[[dict[str, Any]], Awaitable[None]]
HeartbeatHandler = Callable[[dict[str, Any]], Awaitable[None]]
DisconnectHandler = Callable[[], Awaitable[None]]


class HardwareAdapter(ABC):
    """Device-level hardware integration facade.

    Implementations coordinate connection lifecycle, optional transport /
    protocol session, component registration and emergency stop.

    They must not own low-level byte I/O, message parsing, or
    component-specific telemetry interpretation — those belong to
    TransportAdapter, ProtocolSession and ComponentAdapter respectively.
    """

    mode: str  # "simulation" | "serial"

    def __init__(self) -> None:
        self._telemetry_handler: TelemetryHandler | None = None
        self._heartbeat_handler: HeartbeatHandler | None = None
        self._disconnect_handler: DisconnectHandler | None = None

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

    def on_disconnect(self, handler: DisconnectHandler) -> None:
        self._disconnect_handler = handler

    async def _emit_telemetry(self, payload: dict[str, Any]) -> None:
        if self._telemetry_handler is not None:
            await self._telemetry_handler(payload)

    async def _emit_heartbeat(self, payload: dict[str, Any]) -> None:
        if self._heartbeat_handler is not None:
            await self._heartbeat_handler(payload)

    async def _emit_disconnect(self) -> None:
        if self._disconnect_handler is not None:
            await self._disconnect_handler()
