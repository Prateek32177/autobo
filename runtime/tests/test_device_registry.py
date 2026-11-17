"""Device registry and storage tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from physical_ai.core.models import ConnectionConfig, ConnectionType, DeviceCreate, DeviceType
from physical_ai.devices.registry import DeviceRegistry
from physical_ai.storage.database import Database


@pytest.fixture
async def registry(tmp_path: Path) -> DeviceRegistry:
    db = Database(tmp_path / "reg.db", telemetry_retention_rows=100)
    await db.connect()
    reg = DeviceRegistry(db)
    yield reg
    for summary in await reg.list_devices():
        adapter = reg.get_adapter(summary.id)
        if adapter is not None:
            await adapter.disconnect()
    await db.close()


@pytest.mark.asyncio
async def test_register_and_get_device(registry: DeviceRegistry) -> None:
    device = await registry.register_device(
        DeviceCreate(
            name="Test Rover",
            device_type=DeviceType.AUTONOMOUS_ROVER,
            connection=ConnectionConfig(type=ConnectionType.SIMULATION),
        ),
        device_id="rover-test-001",
    )
    assert device.id == "rover-test-001"
    assert len(device.components) == 7
    assert device.connection.type == ConnectionType.SIMULATION

    fetched = await registry.get_device("rover-test-001")
    assert fetched.name == "Test Rover"


@pytest.mark.asyncio
async def test_ensure_simulated_rover_connects(registry: DeviceRegistry) -> None:
    device = await registry.ensure_simulated_rover("rover-sim-001")
    assert device.connectivity_status.value == "connected"
    assert device.health_status.value == "healthy"
    assert device.connection.type == ConnectionType.SIMULATION

    adapter = registry.get_adapter("rover-sim-001")
    assert adapter is not None
    assert adapter.mode == "simulation"
    assert await adapter.is_connected()


@pytest.mark.asyncio
async def test_delete_device(registry: DeviceRegistry) -> None:
    await registry.register_device(
        DeviceCreate(
            name="Temp",
            connection=ConnectionConfig(type=ConnectionType.SIMULATION),
        ),
        device_id="temp-001",
    )
    await registry.delete_device("temp-001")
    with pytest.raises(KeyError):
        await registry.get_device("temp-001")


@pytest.mark.asyncio
async def test_serial_requires_port(registry: DeviceRegistry) -> None:
    with pytest.raises(ValueError, match="port"):
        await registry.register_device(
            DeviceCreate(
                name="Serial Rover",
                connection=ConnectionConfig(type=ConnectionType.SERIAL),
            )
        )
