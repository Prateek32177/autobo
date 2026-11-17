"""In-process simulated ESP32 peer speaking JSON Lines over MemoryTransport."""

from __future__ import annotations

import asyncio
import math
import time
from typing import Any

from contracts.protocol import (
    PROTOCOL_VERSION,
    AckStatus,
    CommandAction,
    ProtocolCapabilityInfo,
    ProtocolCommand,
    ProtocolCommandAck,
    ProtocolCommandResult,
    ProtocolComponentInfo,
    ProtocolEmergencyStop,
    ProtocolHandshake,
    ProtocolHeartbeat,
    ProtocolTelemetry,
    ResultStatus,
    parse_protocol_line,
)
from physical_ai.hardware.transport.memory import MemoryTransport


class SimulatedEsp32Peer:
    """Device-side peer used by MockHardwareAdapter (not USB serial)."""

    def __init__(
        self,
        transport: MemoryTransport,
        *,
        device_id: str,
        firmware_version: str = "0.1.0-sim",
        interval_seconds: float = 1.0,
    ) -> None:
        self.transport = transport
        self.device_id = device_id
        self.firmware_version = firmware_version
        self.interval_seconds = interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._started_at = time.monotonic()
        self._left_encoder = 0
        self._right_encoder = 0
        self._motor_left = "idle"
        self._motor_right = "idle"
        self._tick = 0
        self._stopped = False

    async def start(self) -> None:
        if self._running:
            return
        await self.transport.connect()
        self._running = True
        self._started_at = time.monotonic()
        self._task = asyncio.create_task(self._run(), name=f"sim-peer-{self.device_id}")

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self.transport.disconnect()

    async def _run(self) -> None:
        await self._send_handshake()
        try:
            while self._running:
                await self._pump_commands(timeout=0.05)
                uptime_ms = int((time.monotonic() - self._started_at) * 1000)
                await self._write(
                    ProtocolHeartbeat(
                        device_id=self.device_id,
                        firmware_version=self.firmware_version,
                        uptime_ms=uptime_ms,
                        protocol_version=PROTOCOL_VERSION,
                    )
                )
                await self._write(self._telemetry(uptime_ms))
                self._tick += 1
                await asyncio.sleep(self.interval_seconds)
        except asyncio.CancelledError:
            raise

    async def _pump_commands(self, timeout: float) -> None:
        try:
            line = await self.transport.read_line(timeout=timeout)
        except Exception:
            return
        try:
            message = parse_protocol_line(line)
        except ValueError:
            return
        if isinstance(message, ProtocolEmergencyStop):
            self._motor_left = "idle"
            self._motor_right = "idle"
            self._stopped = True
            return
        if isinstance(message, ProtocolCommand):
            await self._handle_command(message)

    async def _handle_command(self, command: ProtocolCommand) -> None:
        await self._write(
            ProtocolCommandAck(command_id=command.command_id, status=AckStatus.ACCEPTED)
        )
        action = (
            command.action.value
            if isinstance(command.action, CommandAction)
            else str(command.action)
        )
        params = command.parameters or {}

        if action in ("stop", "emergency_stop"):
            self._motor_left = "idle"
            self._motor_right = "idle"
            self._stopped = True
            await self._write(
                ProtocolCommandResult(
                    command_id=command.command_id,
                    status=ResultStatus.COMPLETED,
                    left_encoder_delta=0,
                    right_encoder_delta=0,
                )
            )
            return

        if action == "read_distance":
            await self._write(
                ProtocolCommandResult(
                    command_id=command.command_id,
                    status=ResultStatus.COMPLETED,
                    distance_cm=self._distance_cm(),
                )
            )
            return

        if action == "read_battery":
            await self._write(
                ProtocolCommandResult(
                    command_id=command.command_id,
                    status=ResultStatus.COMPLETED,
                    battery_voltage=self._battery_voltage(),
                )
            )
            return

        if action == "read_encoders":
            await self._write(
                ProtocolCommandResult(
                    command_id=command.command_id,
                    status=ResultStatus.COMPLETED,
                    left_encoder_delta=0,
                    right_encoder_delta=0,
                )
            )
            return

        speed = max(0.0, min(float(params.get("speed", 0.15)), 0.4))
        duration_ms = max(0, min(int(params.get("duration_ms", 500)), 3000))
        left_delta = right_delta = 0
        if action == "move_forward":
            self._motor_left = self._motor_right = "forward"
            left_delta = right_delta = int(speed * duration_ms / 10)
        elif action == "move_backward":
            self._motor_left = self._motor_right = "backward"
            left_delta = right_delta = -int(speed * duration_ms / 10)
        elif action == "turn_left":
            self._motor_left, self._motor_right = "backward", "forward"
            left_delta = -int(speed * duration_ms / 15)
            right_delta = int(speed * duration_ms / 15)
        elif action == "turn_right":
            self._motor_left, self._motor_right = "forward", "backward"
            left_delta = int(speed * duration_ms / 15)
            right_delta = -int(speed * duration_ms / 15)
        else:
            await self._write(
                ProtocolCommandResult(
                    command_id=command.command_id,
                    status=ResultStatus.FAILED,
                    message=f"Unsupported action: {action}",
                )
            )
            return

        await asyncio.sleep(duration_ms / 1000.0)
        self._left_encoder += left_delta
        self._right_encoder += right_delta
        self._motor_left = self._motor_right = "idle"
        self._stopped = False
        await self._write(
            ProtocolCommandResult(
                command_id=command.command_id,
                status=ResultStatus.COMPLETED,
                left_encoder_delta=left_delta,
                right_encoder_delta=right_delta,
            )
        )

    async def _send_handshake(self) -> None:
        components = [
            ProtocolComponentInfo(key="controller", component_type="controller", name="ESP32 Controller"),
            ProtocolComponentInfo(key="distance_sensor", component_type="distance_sensor"),
            ProtocolComponentInfo(key="left_motor", component_type="motor"),
            ProtocolComponentInfo(key="right_motor", component_type="motor"),
            ProtocolComponentInfo(key="left_encoder", component_type="encoder"),
            ProtocolComponentInfo(key="right_encoder", component_type="encoder"),
            ProtocolComponentInfo(key="battery", component_type="battery"),
        ]
        capabilities = [
            ProtocolCapabilityInfo(name="get_distance"),
            ProtocolCapabilityInfo(name="move_forward"),
            ProtocolCapabilityInfo(name="move_backward"),
            ProtocolCapabilityInfo(name="turn_left"),
            ProtocolCapabilityInfo(name="turn_right"),
            ProtocolCapabilityInfo(name="stop"),
            ProtocolCapabilityInfo(name="run_diagnostics"),
        ]
        await self._write(
            ProtocolHandshake(
                device_id=self.device_id,
                manufacturer="physical-ai",
                board="esp32",
                model="autonomous_rover",
                firmware_version=self.firmware_version,
                protocol_version=PROTOCOL_VERSION,
                supported_components=components,
                supported_capabilities=capabilities,
            )
        )

    def _telemetry(self, uptime_ms: int) -> ProtocolTelemetry:
        return ProtocolTelemetry(
            device_id=self.device_id,
            timestamp_ms=uptime_ms,
            battery_voltage=self._battery_voltage(),
            distance_cm=self._distance_cm(),
            left_encoder=self._left_encoder,
            right_encoder=self._right_encoder,
            motor_status={"left": self._motor_left, "right": self._motor_right},
            uptime_ms=uptime_ms,
            firmware_version=self.firmware_version,
        )

    async def _write(self, model: Any) -> None:
        await self.transport.write_line(model.model_dump_json())

    def _battery_voltage(self) -> float:
        base = 7.6 - (self._tick * 0.0002)
        ripple = 0.02 * math.sin(self._tick / 5.0)
        return round(max(6.5, base + ripple), 3)

    def _distance_cm(self) -> float:
        return round(40 + 15 * math.sin(self._tick / 8.0), 1)
