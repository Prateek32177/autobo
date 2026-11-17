"""Mock hardware adapter tests."""

from __future__ import annotations

import asyncio

import pytest

from physical_ai.core.models import ProtocolCommand, ResultStatus
from physical_ai.hardware.mock_adapter import MockHardwareAdapter


@pytest.mark.asyncio
async def test_mock_emits_telemetry() -> None:
    adapter = MockHardwareAdapter("rover-sim-001", interval_seconds=0.05)
    events: list[dict] = []

    async def on_tel(payload: dict) -> None:
        events.append(payload)

    adapter.on_telemetry(on_tel)
    await adapter.connect()
    await asyncio.sleep(0.12)
    await adapter.disconnect()

    assert len(events) >= 1
    assert events[0]["device_id"] == "rover-sim-001"
    assert events[0]["mode"] == "simulation"
    assert "battery_voltage" in events[0]
    assert "distance_cm" in events[0]


@pytest.mark.asyncio
async def test_mock_move_forward_updates_encoders() -> None:
    adapter = MockHardwareAdapter("rover-sim-001", interval_seconds=1.0)
    await adapter.connect()
    result = await adapter.send_command(
        ProtocolCommand(
            command_id="cmd-1",
            action="move_forward",
            parameters={"speed": 0.2, "duration_ms": 50},
        )
    )
    await adapter.disconnect()

    assert result.status == ResultStatus.COMPLETED
    assert result.left_encoder_delta and result.left_encoder_delta > 0
    assert result.right_encoder_delta and result.right_encoder_delta > 0


@pytest.mark.asyncio
async def test_mock_emergency_stop() -> None:
    adapter = MockHardwareAdapter("rover-sim-001")
    await adapter.connect()
    await adapter.emergency_stop()
    snap = adapter.snapshot()
    await adapter.disconnect()
    assert snap["stopped"] is True
    assert snap["motor_status"]["left"] == "idle"
