"""Virtual ESP32 unit tests (no SerialHardwareAdapter)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "firmware" / "virtual_esp32"))

from contracts.protocol import (  # noqa: E402
    ProtocolCommand,
    ProtocolHeartbeat,
    ProtocolTelemetry,
    parse_protocol_line,
)
from device_state import DeviceState, SUPPORTED_ACTIONS  # noqa: E402
from scenarios import Scenario, ScenarioConfig  # noqa: E402
from simulator import VirtualEsp32  # noqa: E402


def test_protocol_compatibility_handshake_shape() -> None:
    state = DeviceState()
    components = [
        {"key": "controller", "component_type": "controller"},
        {"key": "battery", "component_type": "battery"},
    ]
    line = json.dumps(
        {
            "type": "handshake",
            "device_id": state.device_id,
            "manufacturer": state.manufacturer,
            "board": state.board,
            "model": state.model,
            "firmware_version": state.firmware_version,
            "protocol_version": state.protocol_version,
            "supported_components": components,
        }
    )
    msg = parse_protocol_line(line)
    assert msg.type == "handshake"
    assert msg.device_id == "rover-001"
    assert msg.protocol_version == "1.0"


def test_motor_state_transitions_and_encoders() -> None:
    state = DeviceState()
    left, right = state.apply_motion("move_forward", 0.2, 100)
    assert left > 0 and right > 0
    assert state.left_motor == "forward"
    assert state.right_motor == "forward"

    left, right = state.apply_motion("turn_left", 0.2, 100)
    assert left < 0 < right
    assert state.left_motor == "backward"
    assert state.right_motor == "forward"

    state.stop_motors(emergency=True)
    assert state.emergency_stopped is True
    assert state.left_motor == "idle"


def test_supported_actions_match_firmware_set() -> None:
    expected = {
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
    assert SUPPORTED_ACTIONS == expected


def test_low_battery_and_sensor_failure_scenarios() -> None:
    low = ScenarioConfig.from_name(Scenario.LOW_BATTERY.value)
    state = DeviceState()
    low.apply_to_state(state)
    assert state.battery_voltage <= 6.5

    fail = ScenarioConfig.from_name(Scenario.SENSOR_FAILURE.value)
    state2 = DeviceState()
    fail.apply_to_state(state2)
    assert state2.sensor_failed is True
    assert state2.effective_distance() is None


def test_watchdog_trips_without_host_traffic() -> None:
    state = DeviceState()
    state.last_host_monotonic -= 5.0
    state.apply_motion("move_forward", 0.2, 500)
    state.tick_timeouts(watchdog_ms=3000)
    assert state.emergency_stopped is True
    assert state.left_motor == "idle"


class _FakeSerial:
    def __init__(self) -> None:
        self.out: list[bytes] = []
        self.in_lines: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.out.append(data)

    def flush(self) -> None:
        return None

    def readline(self) -> bytes:
        if not self.in_lines:
            return b""
        return self.in_lines.pop(0)

    def close(self) -> None:
        return None


def test_malformed_message_does_not_refresh_watchdog(monkeypatch: pytest.MonkeyPatch) -> None:
    sim = VirtualEsp32("/dev/null", config=ScenarioConfig())
    fake = _FakeSerial()
    sim._serial = fake  # noqa: SLF001
    sim._running = True  # noqa: SLF001
    before = sim.state.last_host_monotonic
    sim.state.last_host_monotonic = before - 1.0
    sim._handle_line("not-json{{{")  # noqa: SLF001
    # Watchdog timestamp must remain old (malformed must not count as host traffic).
    assert sim.state.last_host_monotonic == before - 1.0
    assert any(b"MALFORMED_MESSAGE" in chunk for chunk in fake.out)


def test_unsupported_command_is_rejected() -> None:
    sim = VirtualEsp32("/dev/null", config=ScenarioConfig())
    fake = _FakeSerial()
    sim._serial = fake  # noqa: SLF001
    sim._running = True  # noqa: SLF001
    cmd = ProtocolCommand(command_id="c1", action="fly_away", parameters={})
    sim._handle_command(cmd)  # noqa: SLF001
    joined = b"".join(fake.out).decode()
    assert '"status":"rejected"' in joined or '"status": "rejected"' in joined
    assert "unsupported action" in joined


def test_emergency_stop_command_latches() -> None:
    sim = VirtualEsp32("/dev/null", config=ScenarioConfig())
    fake = _FakeSerial()
    sim._serial = fake  # noqa: SLF001
    sim._running = True  # noqa: SLF001
    cmd = ProtocolCommand(command_id="e1", action="emergency_stop", parameters={})
    sim._handle_command(cmd)  # noqa: SLF001
    assert sim.state.emergency_stopped is True
    assert any(b"command_result" in chunk for chunk in fake.out)


def test_heartbeat_and_telemetry_roundtrip_models() -> None:
    hb = ProtocolHeartbeat(
        device_id="rover-001",
        firmware_version="0.2.0",
        uptime_ms=10,
    )
    tel = ProtocolTelemetry(
        device_id="rover-001",
        timestamp_ms=10,
        battery_voltage=7.4,
        distance_cm=35,
        left_encoder=0,
        right_encoder=0,
        emergency_stopped=False,
    )
    assert parse_protocol_line(hb.model_dump_json()).type == "heartbeat"
    assert parse_protocol_line(tel.model_dump_json()).type == "telemetry"
