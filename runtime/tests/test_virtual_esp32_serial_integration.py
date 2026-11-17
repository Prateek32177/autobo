"""Integration: Virtual ESP32 ↔ linked PTY ↔ SerialHardwareAdapter (real serial path)."""

from __future__ import annotations

import asyncio
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "firmware" / "virtual_esp32"))

from contracts.protocol import ProtocolCommand, ResultStatus  # noqa: E402
from physical_ai.capabilities.registry import CapabilityRegistry  # noqa: E402
from physical_ai.components.registry import ComponentRegistry  # noqa: E402
from physical_ai.hardware.serial_adapter import SerialHardwareAdapter  # noqa: E402
from pty_pair import open_linked_pty_pair  # noqa: E402
from scenarios import ScenarioConfig  # noqa: E402
from simulator import VirtualEsp32  # noqa: E402


@pytest.fixture
def virtual_serial_pair():
    pair = open_linked_pty_pair()
    sim = VirtualEsp32(
        pair.device_port,
        baud=115200,
        config=ScenarioConfig(heartbeat_interval_s=0.2),
    )
    thread = threading.Thread(target=sim.run, name="virtual-esp32", daemon=True)
    thread.start()
    # Allow the simulator to open its PTY end and begin handshake retries.
    time.sleep(0.5)
    yield pair, sim
    sim._running = False  # noqa: SLF001
    thread.join(timeout=2.0)
    pair.close()


@pytest.mark.asyncio
async def test_serial_adapter_handshake_telemetry_and_commands(virtual_serial_pair) -> None:
    pair, sim = virtual_serial_pair
    components = ComponentRegistry()
    capabilities = CapabilityRegistry()
    # Device id in registry/adapters can differ from firmware device_id;
    # handshake carries rover-001 while adapter key is local.
    adapter = SerialHardwareAdapter(
        device_id="virtual-rover",
        port=pair.host_port,
        baud_rate=115200,
        component_registry=components,
        capability_registry=capabilities,
    )

    telemetry_events: list[dict] = []

    async def on_tel(payload: dict) -> None:
        telemetry_events.append(payload)

    adapter.on_telemetry(on_tel)

    await adapter.connect()
    assert adapter.mode == "serial"
    assert await adapter.is_connected()

    # Wait for live telemetry through the real serial protocol path.
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and not telemetry_events:
        await asyncio.sleep(0.05)
    assert telemetry_events, "expected telemetry via SerialHardwareAdapter"
    assert telemetry_events[0]["mode"] == "serial"
    assert "battery_voltage" in telemetry_events[0]

    result = await adapter.send_command(
        ProtocolCommand(
            command_id="cmd-move-1",
            action="move_forward",
            parameters={"speed": 0.2, "duration_ms": 80},
        )
    )
    assert result.status == ResultStatus.COMPLETED
    assert result.command_id == "cmd-move-1"
    assert result.left_encoder_delta and result.left_encoder_delta > 0

    enc = await adapter.send_command(
        ProtocolCommand(command_id="cmd-enc", action="read_encoders", parameters={})
    )
    assert enc.status == ResultStatus.COMPLETED

    await adapter.emergency_stop("test")
    await asyncio.sleep(0.3)
    assert sim.state.emergency_stopped is True

    await adapter.disconnect()
    assert await adapter.is_connected() is False


@pytest.mark.asyncio
async def test_serial_reconnect_after_disconnect(virtual_serial_pair) -> None:
    pair, _sim = virtual_serial_pair
    adapter = SerialHardwareAdapter(
        device_id="virtual-rover-2",
        port=pair.host_port,
        baud_rate=115200,
    )
    await adapter.connect()
    await adapter.disconnect()

    # Re-open on the same host PTY with a fresh adapter instance.
    adapter2 = SerialHardwareAdapter(
        device_id="virtual-rover-2",
        port=pair.host_port,
        baud_rate=115200,
    )
    # Device may need a moment after prior session stop.
    await asyncio.sleep(0.2)
    await adapter2.connect()
    assert await adapter2.is_connected()
    await adapter2.disconnect()


@pytest.mark.asyncio
async def test_unsupported_command_over_serial(virtual_serial_pair) -> None:
    pair, _sim = virtual_serial_pair
    adapter = SerialHardwareAdapter(
        device_id="virtual-rover-3",
        port=pair.host_port,
        baud_rate=115200,
    )
    await adapter.connect()
    result = await adapter.send_command(
        ProtocolCommand(command_id="bad-1", action="fly_away", parameters={})
    )
    assert result.status == ResultStatus.FAILED
    await adapter.disconnect()
