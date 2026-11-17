"""Deterministic simulated rover state for the Virtual ESP32."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


SUPPORTED_ACTIONS = frozenset(
    {
        "move_forward",
        "move_backward",
        "turn_left",
        "turn_right",
        "stop",
        "emergency_stop",
        "read_distance",
        "read_battery",
        "read_encoders",
    }
)

COMPONENTS = (
    ("controller", "controller", "ESP32 Controller"),
    ("distance_sensor", "distance_sensor", "Distance Sensor"),
    ("left_motor", "motor", "Left Motor"),
    ("right_motor", "motor", "Right Motor"),
    ("left_encoder", "encoder", "Left Encoder"),
    ("right_encoder", "encoder", "Right Encoder"),
    ("battery", "battery", "Battery"),
)


@dataclass
class DeviceState:
    device_id: str = "rover-001"
    manufacturer: str = "physical-ai"
    board: str = "esp32"
    model: str = "autonomous_rover"
    firmware_version: str = "0.2.0"
    protocol_version: str = "1.0"

    battery_voltage: float = 7.4
    distance_cm: float = 35.0
    left_encoder: int = 0
    right_encoder: int = 0
    left_motor: str = "idle"
    right_motor: str = "idle"

    emergency_stopped: bool = False
    motors_active: bool = False
    motor_deadline_ms: int = 0
    sensor_failed: bool = False

    started_monotonic: float = field(default_factory=time.monotonic)
    last_host_monotonic: float = field(default_factory=time.monotonic)

    def uptime_ms(self) -> int:
        return int((time.monotonic() - self.started_monotonic) * 1000)

    def touch_host(self) -> None:
        self.last_host_monotonic = time.monotonic()

    def host_silent_ms(self) -> int:
        return int((time.monotonic() - self.last_host_monotonic) * 1000)

    def stop_motors(self, *, emergency: bool = False) -> None:
        self.left_motor = "idle"
        self.right_motor = "idle"
        self.motors_active = False
        self.motor_deadline_ms = 0
        if emergency:
            self.emergency_stopped = True

    def clear_emergency(self) -> None:
        self.emergency_stopped = False

    def apply_motion(self, action: str, speed: float, duration_ms: int) -> tuple[int, int]:
        speed = max(0.0, min(speed, 0.4))
        duration_ms = max(0, min(duration_ms, 3000))
        ticks = int(speed * duration_ms / 10.0)

        if action == "move_forward":
            left_delta = right_delta = ticks
            self.left_motor = self.right_motor = "forward"
        elif action == "move_backward":
            left_delta = right_delta = -ticks
            self.left_motor = self.right_motor = "backward"
        elif action == "turn_left":
            left_delta = -ticks
            right_delta = ticks
            self.left_motor = "backward"
            self.right_motor = "forward"
        elif action == "turn_right":
            left_delta = ticks
            right_delta = -ticks
            self.left_motor = "forward"
            self.right_motor = "backward"
        else:
            return 0, 0

        self.left_encoder += left_delta
        self.right_encoder += right_delta
        self.motors_active = duration_ms > 0
        self.motor_deadline_ms = self.uptime_ms() + min(duration_ms, 1500)
        return left_delta, right_delta

    def tick_timeouts(self, *, motor_timeout_ms: int = 1500, watchdog_ms: int = 3000) -> None:
        now = self.uptime_ms()
        if self.motors_active and self.motor_deadline_ms and now >= self.motor_deadline_ms:
            self.stop_motors()
        if self.host_silent_ms() > watchdog_ms:
            self.stop_motors(emergency=True)
        # Gentle drain so idle telemetry visibly changes (uptime also changes).
        self.battery_voltage = max(6.0, round(self.battery_voltage - 0.00002, 5))

    def effective_distance(self) -> float | None:
        if self.sensor_failed:
            return None
        return self.distance_cm
