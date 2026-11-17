"""Simulated hardware adapter — same contracts as physical ESP32, no USB serial."""

from __future__ import annotations

from typing import Any

from contracts.protocol import ProtocolCommand, ProtocolCommandResult, ProtocolHeartbeat, ProtocolTelemetry
from physical_ai.capabilities.registry import CapabilityRegistry
from physical_ai.components.registry import ComponentRegistry
from physical_ai.components.rover import create_rover_components
from physical_ai.hardware.base import HardwareAdapter
from physical_ai.hardware.protocol.session import ProtocolSession
from physical_ai.hardware.sim_peer import SimulatedEsp32Peer
from physical_ai.hardware.transport.memory import MemoryTransport


class MockHardwareAdapter(HardwareAdapter):
    """In-process simulation using MemoryTransport + ProtocolSession + rover components."""

    mode = "simulation"

    def __init__(
        self,
        device_id: str,
        *,
        firmware_version: str = "0.1.0-sim",
        interval_seconds: float = 1.0,
        component_registry: ComponentRegistry | None = None,
        capability_registry: CapabilityRegistry | None = None,
    ) -> None:
        super().__init__()
        self.device_id = device_id
        self.firmware_version = firmware_version
        self.interval_seconds = interval_seconds
        self.component_registry = component_registry or ComponentRegistry()
        self.capability_registry = capability_registry or CapabilityRegistry()
        self._host_transport: MemoryTransport | None = None
        self._peer: SimulatedEsp32Peer | None = None
        self._session: ProtocolSession | None = None
        self._connected = False
        self._stopped = False

    async def connect(self) -> None:
        if self._connected:
            return

        adapters = create_rover_components(self.device_id)
        self.component_registry.register(self.device_id, adapters)
        self.capability_registry.register_from_components(self.device_id, adapters)
        await self.component_registry.connect_all(self.device_id)

        host, peer_transport = MemoryTransport.pair()
        self._host_transport = host
        self._peer = SimulatedEsp32Peer(
            peer_transport,
            device_id=self.device_id,
            firmware_version=self.firmware_version,
            interval_seconds=self.interval_seconds,
        )
        self._session = ProtocolSession(host, command_timeout=5.0, read_timeout=0.2)
        self._session.on_heartbeat(self._on_protocol_heartbeat)
        self._session.on_telemetry(self._on_protocol_telemetry)
        self._session.on_disconnect(self._emit_disconnect)

        await self._peer.start()
        await self._session.start()
        await self._session.perform_handshake(timeout=3.0)
        self._connected = True
        self._stopped = False

    async def disconnect(self) -> None:
        self._connected = False
        if self._session is not None:
            await self._session.stop()
            self._session = None
        if self._peer is not None:
            await self._peer.stop()
            self._peer = None
        await self.component_registry.disconnect_all(self.device_id)
        self.capability_registry.clear(self.device_id)
        self.component_registry.unregister(self.device_id)
        self._host_transport = None

    async def is_connected(self) -> bool:
        return self._connected

    async def send_command(self, command: ProtocolCommand) -> ProtocolCommandResult:
        if not self._connected or self._session is None:
            from contracts.protocol import ResultStatus

            return ProtocolCommandResult(
                command_id=command.command_id,
                status=ResultStatus.FAILED,
                message="Device not connected",
            )
        return await self._session.send_command(command)

    async def emergency_stop(self, reason: str = "operator") -> None:
        self._stopped = True
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
        # motor_status may be a model
        motor = payload.get("motor_status")
        if hasattr(motor, "model_dump"):
            payload["motor_status"] = motor.model_dump()
        await self.component_registry.dispatch_telemetry(self.device_id, payload)
        await self._emit_telemetry(payload)

    def snapshot(self) -> dict[str, Any]:
        """Compatibility helper for tests — latest component-derived view."""
        battery = self.component_registry.get(self.device_id, "battery")
        distance = self.component_registry.get(self.device_id, "distance_sensor")
        left_enc = self.component_registry.get(self.device_id, "left_encoder")
        right_enc = self.component_registry.get(self.device_id, "right_encoder")
        left_motor = self.component_registry.get(self.device_id, "left_motor")
        right_motor = self.component_registry.get(self.device_id, "right_motor")
        return {
            "type": "telemetry",
            "device_id": self.device_id,
            "battery_voltage": (battery._metrics if battery else {}).get("battery_voltage"),
            "distance_cm": (distance._metrics if distance else {}).get("distance_cm"),
            "left_encoder": (left_enc._metrics if left_enc else {}).get("ticks"),
            "right_encoder": (right_enc._metrics if right_enc else {}).get("ticks"),
            "motor_status": {
                "left": (left_motor._metrics if left_motor else {}).get("status", "idle"),
                "right": (right_motor._metrics if right_motor else {}).get("status", "idle"),
            },
            "firmware_version": self.firmware_version,
            "mode": self.mode,
            "stopped": self._stopped,
        }
