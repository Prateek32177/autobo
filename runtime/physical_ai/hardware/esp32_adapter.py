"""ESP32 hardware adapter — SerialTransport + JSON Lines ProtocolSession."""

from __future__ import annotations

from contracts.protocol import (
    ProtocolCommand,
    ProtocolCommandResult,
    ProtocolHeartbeat,
    ProtocolTelemetry,
    ResultStatus,
)
from physical_ai.capabilities.registry import CapabilityRegistry
from physical_ai.components.registry import ComponentRegistry
from physical_ai.components.rover import create_rover_components
from physical_ai.hardware.base import HardwareAdapter
from physical_ai.hardware.protocol.session import ProtocolSession, ProtocolSessionError
from physical_ai.hardware.transport.base import TransportAdapter
from physical_ai.hardware.transport.serial import SerialTransport


class Esp32HardwareAdapter(HardwareAdapter):
    mode = "serial"

    def __init__(
        self,
        device_id: str,
        *,
        port: str | None = None,
        baud_rate: int = 115200,
        transport: TransportAdapter | None = None,
        component_registry: ComponentRegistry | None = None,
        capability_registry: CapabilityRegistry | None = None,
        skip_handshake: bool = False,
    ) -> None:
        super().__init__()
        if transport is None and not port:
            raise ValueError("Esp32HardwareAdapter requires port or transport")
        self.device_id = device_id
        self.port = port
        self.baud_rate = baud_rate
        self._transport = transport or SerialTransport(port=port or "", baud_rate=baud_rate)
        self.component_registry = component_registry or ComponentRegistry()
        self.capability_registry = capability_registry or CapabilityRegistry()
        self.skip_handshake = skip_handshake
        self._session: ProtocolSession | None = None
        self._connected = False

    async def connect(self) -> None:
        if self._connected:
            return

        adapters = create_rover_components(self.device_id)
        self.component_registry.register(self.device_id, adapters)
        self.capability_registry.register_from_components(self.device_id, adapters)
        await self.component_registry.connect_all(self.device_id)

        self._session = ProtocolSession(self._transport, command_timeout=5.0, read_timeout=1.0)
        self._session.on_heartbeat(self._on_protocol_heartbeat)
        self._session.on_telemetry(self._on_protocol_telemetry)
        self._session.on_disconnect(self._on_comm_loss)

        await self._session.start()
        if not self.skip_handshake:
            try:
                await self._session.perform_handshake(timeout=5.0)
            except ProtocolSessionError:
                await self.disconnect()
                raise
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False
        if self._session is not None:
            await self._session.stop()
            self._session = None
        await self.component_registry.disconnect_all(self.device_id)
        self.capability_registry.clear(self.device_id)
        self.component_registry.unregister(self.device_id)

    async def is_connected(self) -> bool:
        return self._connected

    async def send_command(self, command: ProtocolCommand) -> ProtocolCommandResult:
        if not self._connected or self._session is None:
            return ProtocolCommandResult(
                command_id=command.command_id,
                status=ResultStatus.FAILED,
                message="Device not connected",
            )
        return await self._session.send_command(command)

    async def emergency_stop(self, reason: str = "operator") -> None:
        if self._session is not None:
            await self._session.emergency_stop(reason)

    async def _on_protocol_heartbeat(self, message: ProtocolHeartbeat) -> None:
        payload = message.model_dump()
        payload["mode"] = self.mode
        controller = self.component_registry.get(self.device_id, "controller")
        if controller is not None and hasattr(controller, "ingest_heartbeat"):
            await controller.ingest_heartbeat(payload)  # type: ignore[attr-defined]
        await self._emit_heartbeat(payload)

    async def _on_protocol_telemetry(self, message: ProtocolTelemetry) -> None:
        payload = message.model_dump()
        payload["mode"] = self.mode
        motor = payload.get("motor_status")
        if hasattr(motor, "model_dump"):
            payload["motor_status"] = motor.model_dump()
        await self.component_registry.dispatch_telemetry(self.device_id, payload)
        await self._emit_telemetry(payload)

    async def _on_comm_loss(self) -> None:
        self._connected = False
        await self.component_registry.disconnect_all(self.device_id)
        await self._emit_disconnect()
