"""Protocol contract tests."""

from __future__ import annotations

import json

from contracts.protocol import (
    ProtocolCommand,
    ProtocolHeartbeat,
    ProtocolTelemetry,
    parse_protocol_line,
)


def test_parse_handshake_line() -> None:
    line = json.dumps(
        {
            "type": "handshake",
            "device_id": "rover-001",
            "manufacturer": "physical-ai",
            "board": "esp32",
            "model": "autonomous_rover",
            "firmware_version": "0.2.0",
            "protocol_version": "1.0",
            "supported_components": [
                {"key": "battery", "component_type": "battery"},
            ],
        }
    )
    from contracts.protocol import ProtocolHandshake

    msg = parse_protocol_line(line)
    assert isinstance(msg, ProtocolHandshake)
    assert msg.protocol_version == "1.0"


def test_parse_heartbeat_line() -> None:
    line = json.dumps(
        {
            "type": "heartbeat",
            "device_id": "rover-001",
            "firmware_version": "0.1.0",
            "uptime_ms": 120000,
        }
    )
    msg = parse_protocol_line(line)
    assert isinstance(msg, ProtocolHeartbeat)
    assert msg.device_id == "rover-001"
    assert msg.uptime_ms == 120000


def test_parse_telemetry_line() -> None:
    line = json.dumps(
        {
            "type": "telemetry",
            "device_id": "rover-001",
            "timestamp_ms": 120500,
            "battery_voltage": 7.4,
            "distance_cm": 35,
            "left_encoder": 120,
            "right_encoder": 118,
            "motor_status": {"left": "idle", "right": "idle"},
        }
    )
    msg = parse_protocol_line(line)
    assert isinstance(msg, ProtocolTelemetry)
    assert msg.distance_cm == 35
    assert msg.motor_status.left == "idle"


def test_command_roundtrip() -> None:
    cmd = ProtocolCommand(
        command_id="cmd-001",
        action="move_forward",
        parameters={"speed": 0.15, "duration_ms": 500},
    )
    parsed = parse_protocol_line(cmd.model_dump_json())
    assert isinstance(parsed, ProtocolCommand)
    assert parsed.command_id == "cmd-001"
    assert parsed.parameters["speed"] == 0.15
