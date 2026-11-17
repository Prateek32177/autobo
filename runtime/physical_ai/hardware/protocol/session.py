"""JSON Lines protocol session — framing, handshake, command correlation."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from contracts.protocol import (
    PROTOCOL_VERSION,
    ProtocolCommand,
    ProtocolCommandAck,
    ProtocolCommandResult,
    ProtocolEmergencyStop,
    ProtocolError,
    ProtocolHandshake,
    ProtocolHandshakeAck,
    ProtocolHeartbeat,
    ProtocolTelemetry,
    ResultStatus,
    parse_protocol_line,
)
from physical_ai.hardware.transport.base import (
    TransportAdapter,
    TransportError,
    TransportTimeout,
)

logger = logging.getLogger(__name__)

MessageHandler = Callable[[Any], Awaitable[None]]


class ProtocolSessionError(Exception):
    pass


class ProtocolSession:
    """Host-side protocol session over an arbitrary transport."""

    def __init__(
        self,
        transport: TransportAdapter,
        *,
        expected_protocol_version: str = PROTOCOL_VERSION,
        command_timeout: float = 5.0,
        read_timeout: float = 1.0,
    ) -> None:
        self.transport = transport
        self.expected_protocol_version = expected_protocol_version
        self.command_timeout = command_timeout
        self.read_timeout = read_timeout
        self._reader_task: asyncio.Task[None] | None = None
        self._pending: dict[str, asyncio.Future[ProtocolCommandResult]] = {}
        self._acks: dict[str, ProtocolCommandAck] = {}
        self._handshake: ProtocolHandshake | None = None
        self._on_heartbeat: MessageHandler | None = None
        self._on_telemetry: MessageHandler | None = None
        self._on_error: MessageHandler | None = None
        self._on_malformed: Callable[[str, Exception], Awaitable[None]] | None = None
        self._on_disconnect: Callable[[], Awaitable[None]] | None = None
        self._running = False
        self._loss_notified = False
        self._keepalive_task: asyncio.Task[None] | None = None
        self._keepalive_interval_s = 1.0

    @property
    def handshake(self) -> ProtocolHandshake | None:
        return self._handshake

    def on_heartbeat(self, handler: MessageHandler) -> None:
        self._on_heartbeat = handler

    def on_telemetry(self, handler: MessageHandler) -> None:
        self._on_telemetry = handler

    def on_error(self, handler: MessageHandler) -> None:
        self._on_error = handler

    def on_malformed(self, handler: Callable[[str, Exception], Awaitable[None]]) -> None:
        self._on_malformed = handler

    def on_disconnect(self, handler: Callable[[], Awaitable[None]]) -> None:
        self._on_disconnect = handler

    async def start(self) -> None:
        if self._running:
            return
        if not self.transport.is_connected():
            await self.transport.connect()
        self._running = True
        self._loss_notified = False
        self._reader_task = asyncio.create_task(self._read_loop(), name="protocol-session")
        self._keepalive_task = asyncio.create_task(
            self._keepalive_loop(), name="protocol-keepalive"
        )

    async def stop(self) -> None:
        self._running = False
        if self._keepalive_task is not None:
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass
            self._keepalive_task = None
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None
        for future in self._pending.values():
            if not future.done():
                future.set_result(
                    ProtocolCommandResult(
                        command_id="unknown",
                        status=ResultStatus.CANCELLED,
                        message="Session stopped",
                    )
                )
        self._pending.clear()
        await self.transport.disconnect()

    async def _keepalive_loop(self) -> None:
        """Refresh the device host-watchdog with periodic handshake_ack frames."""
        while self._running:
            try:
                await asyncio.sleep(self._keepalive_interval_s)
                hs = self._handshake
                if hs is None or not self._running:
                    continue
                await self._send_model(
                    ProtocolHandshakeAck(
                        device_id=hs.device_id,
                        protocol_version=self.expected_protocol_version,
                        status="accepted",
                    )
                )
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                # Keepalive failures are non-fatal; read loop owns disconnect.
                continue

    async def perform_handshake(self, timeout: float = 5.0) -> ProtocolHandshake:
        """Wait for device handshake and acknowledge compatible protocol version."""
        deadline = asyncio.get_event_loop().time() + timeout
        while self._handshake is None:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise ProtocolSessionError("Handshake timed out")
            await asyncio.sleep(0.05)
        hs = self._handshake
        if hs.protocol_version != self.expected_protocol_version:
            ack = ProtocolHandshakeAck(
                device_id=hs.device_id,
                protocol_version=self.expected_protocol_version,
                status="rejected",
                reason=f"Unsupported protocol_version={hs.protocol_version}",
            )
            await self._send_model(ack)
            raise ProtocolSessionError(ack.reason or "Protocol version mismatch")
        await self._send_model(
            ProtocolHandshakeAck(
                device_id=hs.device_id,
                protocol_version=self.expected_protocol_version,
                status="accepted",
            )
        )
        return hs

    async def send_command(self, command: ProtocolCommand) -> ProtocolCommandResult:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[ProtocolCommandResult] = loop.create_future()
        self._pending[command.command_id] = future
        try:
            await self._send_model(command)
            return await asyncio.wait_for(future, timeout=self.command_timeout)
        except TimeoutError:
            self._pending.pop(command.command_id, None)
            return ProtocolCommandResult(
                command_id=command.command_id,
                status=ResultStatus.TIMEOUT,
                message="Command timed out waiting for result",
            )
        except TransportError as exc:
            self._pending.pop(command.command_id, None)
            return ProtocolCommandResult(
                command_id=command.command_id,
                status=ResultStatus.FAILED,
                message=str(exc),
            )

    async def emergency_stop(self, reason: str = "operator") -> None:
        await self._send_model(ProtocolEmergencyStop(reason=reason))

    async def _send_model(self, model: Any) -> None:
        line = model.model_dump_json()
        await self.transport.write_line(line)

    async def _read_loop(self) -> None:
        while self._running:
            try:
                line = await self.transport.read_line(timeout=self.read_timeout)
            except TransportTimeout:
                continue
            except TransportError as exc:
                logger.warning("Transport error in protocol session: %s", exc)
                await self._notify_loss()
                break
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("Unexpected protocol read failure: %s", exc)
                await self._notify_loss()
                break

            if not line.strip():
                continue
            try:
                message = parse_protocol_line(line)
            except (ValueError, json.JSONDecodeError) as exc:
                logger.warning("Malformed protocol line ignored: %s", line)
                if self._on_malformed is not None:
                    await self._on_malformed(line, exc)
                continue

            await self._dispatch(message)

    async def _dispatch(self, message: Any) -> None:
        if isinstance(message, ProtocolHandshake):
            self._handshake = message
            return
        if isinstance(message, ProtocolHandshakeAck):
            return
        if isinstance(message, ProtocolHeartbeat):
            if self._on_heartbeat:
                await self._on_heartbeat(message)
            return
        if isinstance(message, ProtocolTelemetry):
            if self._on_telemetry:
                await self._on_telemetry(message)
            return
        if isinstance(message, ProtocolCommandAck):
            self._acks[message.command_id] = message
            return
        if isinstance(message, ProtocolCommandResult):
            future = self._pending.pop(message.command_id, None)
            if future is not None and not future.done():
                future.set_result(message)
            return
        if isinstance(message, ProtocolError):
            if message.command_id and message.command_id in self._pending:
                future = self._pending.pop(message.command_id)
                if not future.done():
                    future.set_result(
                        ProtocolCommandResult(
                            command_id=message.command_id,
                            status=ResultStatus.FAILED,
                            message=message.message,
                        )
                    )
            if self._on_error:
                await self._on_error(message)
            return
        if isinstance(message, ProtocolEmergencyStop):
            return

    async def _notify_loss(self) -> None:
        if self._loss_notified:
            return
        self._loss_notified = True
        self._running = False
        for command_id, future in list(self._pending.items()):
            if not future.done():
                future.set_result(
                    ProtocolCommandResult(
                        command_id=command_id,
                        status=ResultStatus.FAILED,
                        message="Communication lost",
                    )
                )
        self._pending.clear()
        if self._on_disconnect:
            await self._on_disconnect()
