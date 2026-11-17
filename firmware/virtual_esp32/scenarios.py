"""Configurable failure / behaviour scenarios for the Virtual ESP32."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Scenario(str, Enum):
    NORMAL = "normal"
    HOST_DISCONNECT = "host_disconnect"  # ignore host after N seconds (watchdog fires)
    DEVICE_DISCONNECT = "device_disconnect"  # close serial after N seconds
    HEARTBEAT_TIMEOUT = "heartbeat_timeout"  # stop sending heartbeat/telemetry
    STALE_TELEMETRY = "stale_telemetry"  # send heartbeat only (no telemetry)
    MALFORMED_JSON = "malformed_json"  # emit a bad line once after start
    UNSUPPORTED_COMMAND = "unsupported_command"  # no special emit; host can send bad cmds
    COMMAND_TIMEOUT = "command_timeout"  # ACK commands but never send results
    LOW_BATTERY = "low_battery"
    SENSOR_FAILURE = "sensor_failure"


@dataclass
class ScenarioConfig:
    scenario: Scenario = Scenario.NORMAL
    # Shared knobs
    battery_voltage: float = 7.4
    distance_cm: float = 35.0
    delay_before_fault_s: float = 2.0
    heartbeat_interval_s: float = 1.0
    motor_timeout_ms: int = 1500
    watchdog_ms: int = 3000
    # When True, malformed inbound JSON does not refresh host watchdog (protocol rule).
    malformed_keeps_watchdog_alive: bool = False

    @classmethod
    def from_name(cls, name: str, **overrides: object) -> ScenarioConfig:
        scenario = Scenario(name)
        cfg = cls(scenario=scenario)
        if scenario == Scenario.LOW_BATTERY:
            cfg.battery_voltage = 6.5
        if scenario == Scenario.SENSOR_FAILURE:
            pass  # applied to DeviceState.sensor_failed
        for key, value in overrides.items():
            if hasattr(cfg, key) and value is not None:
                setattr(cfg, key, value)
        return cfg

    def apply_to_state(self, state: object) -> None:
        state.battery_voltage = self.battery_voltage  # type: ignore[attr-defined]
        state.distance_cm = self.distance_cm  # type: ignore[attr-defined]
        if self.scenario == Scenario.SENSOR_FAILURE:
            state.sensor_failed = True  # type: ignore[attr-defined]
        if self.scenario == Scenario.LOW_BATTERY:
            state.battery_voltage = min(state.battery_voltage, 6.5)  # type: ignore[attr-defined]
