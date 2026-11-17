"""Simulated hardware adapter for Milestone 1 (no physical ESP32 required)."""

from __future__ import annotations

import asyncio
import math
import time
from typing import Any

from physical_ai.core.models import (
    AckStatus,
    CommandAction,
    ProtocolCommand,
    ProtocolCommandAck,
    ProtocolCommandResult,
    ResultStatus,
)
from physical_ai.hardware.base import HardwareAdapter


class MockHardwareAdapter(HardwareAdapter):
    """Emits periodic heartbeat + telemetry for a simulated rover."""

    mode = "simulation"

    def __init__(
        self,
        device_id: str,
        *,
        firmware_version: str = "0.1.0-sim",
        interval_seconds: float = 1.0,
    ) -> None:
        self.device_id = device_id
        self.firmware_version = firmware_version
        self.interval_seconds = interval_seconds
        self._connected = False
        self._task: asyncio.Task[None] | None = None
        self._started_at = time.monotonic()
        self._left_encoder = 0
        self._right_encoder = 0
        self._motor_left = "idle"
        self._motor_right = "idle"
        self._tick = 0
        self._stopped = False

    async def connect(self) -> None:
        if self._connected:
            return
        self._connected = True
        self._stopped = False
        self._started_at = time.monotonic()
        self._task = asyncio.create_task(self._loop(), name=f"mock-{self.device_id}")

    async def disconnect(self) -> None:
        self._connected = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def is_connected(self) -> bool:
        return self._connected

    async def send_command(self, command: ProtocolCommand) -> ProtocolCommandResult:
        if not self._connected:
            return ProtocolCommandResult(
                command_id=command.command_id,
                status=ResultStatus.FAILED,
                message="Device not connected",
            )

        action = (
            command.action.value
            if isinstance(command.action, CommandAction)
            else str(command.action)
        )
        params = command.parameters or {}

        # Acknowledge conceptually (callers may log ack separately).
        _ = ProtocolCommandAck(
            command_id=command.command_id,
            status=AckStatus.ACCEPTED,
        )

        if action in ("stop", "emergency_stop"):
            self._motor_left = "idle"
            self._motor_right = "idle"
            self._stopped = True
            return ProtocolCommandResult(
                command_id=command.command_id,
                status=ResultStatus.COMPLETED,
                left_encoder_delta=0,
                right_encoder_delta=0,
            )

        if action == "read_distance":
            return ProtocolCommandResult(
                command_id=command.command_id,
                status=ResultStatus.COMPLETED,
                distance_cm=self._distance_cm(),
            )

        if action == "read_battery":
            return ProtocolCommandResult(
                command_id=command.command_id,
                status=ResultStatus.COMPLETED,
                battery_voltage=self._battery_voltage(),
            )

        if action == "read_encoders":
            return ProtocolCommandResult(
                command_id=command.command_id,
                status=ResultStatus.COMPLETED,
                left_encoder_delta=0,
                right_encoder_delta=0,
            )

        speed = float(params.get("speed", 0.15))
        duration_ms = int(params.get("duration_ms", 500))
        # Safety bounds (also enforced later by SafetyValidator in M5).
        speed = max(0.0, min(speed, 0.4))
        duration_ms = max(0, min(duration_ms, 3000))

        left_delta, right_delta = 0, 0
        if action == "move_forward":
            self._motor_left = "forward"
            self._motor_right = "forward"
            left_delta = right_delta = int(speed * duration_ms / 10)
        elif action == "move_backward":
            self._motor_left = "backward"
            self._motor_right = "backward"
            left_delta = right_delta = -int(speed * duration_ms / 10)
        elif action == "turn_left":
            self._motor_left = "backward"
            self._motor_right = "forward"
            left_delta = -int(speed * duration_ms / 15)
            right_delta = int(speed * duration_ms / 15)
        elif action == "turn_right":
            self._motor_left = "forward"
            self._motor_right = "backward"
            left_delta = int(speed * duration_ms / 15)
            right_delta = -int(speed * duration_ms / 15)
        else:
            return ProtocolCommandResult(
                command_id=command.command_id,
                status=ResultStatus.FAILED,
                message=f"Unsupported action: {action}",
            )

        await asyncio.sleep(duration_ms / 1000.0)
        self._left_encoder += left_delta
        self._right_encoder += right_delta
        self._motor_left = "idle"
        self._motor_right = "idle"
        self._stopped = False

        return ProtocolCommandResult(
            command_id=command.command_id,
            status=ResultStatus.COMPLETED,
            left_encoder_delta=left_delta,
            right_encoder_delta=right_delta,
        )

    async def emergency_stop(self, reason: str = "operator") -> None:
        self._motor_left = "idle"
        self._motor_right = "idle"
        self._stopped = True

    def snapshot(self) -> dict[str, Any]:
        uptime_ms = int((time.monotonic() - self._started_at) * 1000)
        return {
            "type": "telemetry",
            "device_id": self.device_id,
            "timestamp_ms": uptime_ms,
            "battery_voltage": self._battery_voltage(),
            "distance_cm": self._distance_cm(),
            "left_encoder": self._left_encoder,
            "right_encoder": self._right_encoder,
            "motor_status": {
                "left": self._motor_left,
                "right": self._motor_right,
            },
            "firmware_version": self.firmware_version,
            "uptime_ms": uptime_ms,
            "mode": self.mode,
            "stopped": self._stopped,
        }

    async def _loop(self) -> None:
        try:
            while self._connected:
                uptime_ms = int((time.monotonic() - self._started_at) * 1000)
                await self._emit_heartbeat(
                    {
                        "type": "heartbeat",
                        "device_id": self.device_id,
                        "firmware_version": self.firmware_version,
                        "uptime_ms": uptime_ms,
                        "mode": self.mode,
                    }
                )
                await self._emit_telemetry(self.snapshot())
                self._tick += 1
                await asyncio.sleep(self.interval_seconds)
        except asyncio.CancelledError:
            raise

    def _battery_voltage(self) -> float:
        # Gentle simulated drain + small ripple.
        base = 7.6 - (self._tick * 0.0002)
        ripple = 0.02 * math.sin(self._tick / 5.0)
        return round(max(6.5, base + ripple), 3)

    def _distance_cm(self) -> float:
        # Oscillating obstacle distance for demo telemetry.
        return round(40 + 15 * math.sin(self._tick / 8.0), 1)
