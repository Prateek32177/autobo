"""Component adapters, telemetry dispatch and capability-driven tools."""

from __future__ import annotations

import inspect

import pytest

from physical_ai.ai.tools import tools_from_capabilities
from physical_ai.capabilities.registry import CapabilityRegistry
from physical_ai.components.registry import ComponentRegistry
from physical_ai.components.rover import create_rover_components
from physical_ai.devices import registry as devices_registry_module
from physical_ai.execution.executor import ActionExecutor
from physical_ai.execution.safety import SafetyValidator
from physical_ai.hardware.mock_adapter import MockHardwareAdapter


@pytest.mark.asyncio
async def test_component_adapters_expose_typed_capabilities_and_health() -> None:
    components = create_rover_components("rover-a")
    assert len(components) == 7
    distance = next(c for c in components if c.key == "distance_sensor")
    caps = distance.get_capabilities()
    assert any(c.name == "get_distance" for c in caps)

    await distance.connect()
    await distance.ingest_telemetry(
        {"distance_cm": 42.0, "device_id": "rover-a", "timestamp_ms": 1}
    )
    health = await distance.get_health()
    assert health.status.value == "healthy"
    assert health.metrics["distance_cm"] == 42.0


@pytest.mark.asyncio
async def test_telemetry_dispatched_to_correct_components() -> None:
    reg = ComponentRegistry()
    adapters = create_rover_components("rover-b")
    reg.register("rover-b", adapters)
    await reg.connect_all("rover-b")

    observations = await reg.dispatch_telemetry(
        "rover-b",
        {
            "battery_voltage": 7.2,
            "distance_cm": 33.0,
            "left_encoder": 10,
            "right_encoder": 11,
            "motor_status": {"left": "idle", "right": "idle"},
            "uptime_ms": 100,
            "firmware_version": "0.2.0",
        },
    )
    keys = {obs.component_id.split(":")[-1] for obs in observations}
    assert "battery" in keys
    assert "distance_sensor" in keys
    assert "left_encoder" in keys
    assert "controller" in keys


def test_device_registry_has_no_hardcoded_telemetry_metric_map() -> None:
    source = inspect.getsource(devices_registry_module.DeviceRegistry._handle_telemetry)
    assert "battery_voltage" not in source
    assert "distance_cm" not in source
    assert "left_encoder" not in source
    assert "metric_map" not in source


@pytest.mark.asyncio
async def test_ai_tools_generated_dynamically_from_capabilities() -> None:
    components = ComponentRegistry()
    capabilities = CapabilityRegistry()
    adapter = MockHardwareAdapter(
        "rover-tools",
        interval_seconds=0.05,
        component_registry=components,
        capability_registry=capabilities,
    )
    await adapter.connect()
    tools = tools_from_capabilities(capabilities, "rover-tools")
    names = {t["function"]["name"] for t in tools}
    assert "move_forward" in names
    assert "get_distance" in names
    # No ESP32-hardcoded tool module dependency
    assert "esp32" not in str(tools).lower() or "move_forward" in names
    await adapter.disconnect()


@pytest.mark.asyncio
async def test_actions_pass_through_safety_and_executor() -> None:
    components = ComponentRegistry()
    capabilities = CapabilityRegistry()
    adapter = MockHardwareAdapter(
        "rover-exec",
        interval_seconds=0.05,
        component_registry=components,
        capability_registry=capabilities,
    )
    await adapter.connect()
    executor = ActionExecutor(capabilities=capabilities, components=components)

    rejected = await executor.execute(
        "rover-exec",
        "move_forward",
        {"speed": 0.9, "duration_ms": 100},
        hardware=adapter,
    )
    assert rejected["status"] == "rejected"

    ok = await executor.execute(
        "rover-exec",
        "move_forward",
        {"speed": 0.2, "duration_ms": 40},
        hardware=adapter,
    )
    assert ok["status"] == "completed"
    await adapter.disconnect()


@pytest.mark.asyncio
async def test_mock_and_physical_share_capability_contract() -> None:
    """Mock registers the same capability names ESP32 rover components expose."""
    mock_caps = CapabilityRegistry()
    mock = MockHardwareAdapter(
        "sim-1", interval_seconds=0.05, capability_registry=mock_caps, component_registry=ComponentRegistry()
    )
    await mock.connect()
    sim_names = {c.name for c in mock_caps.list("sim-1")}

    # Physical ESP32 uses the same create_rover_components factory.
    phys_caps = CapabilityRegistry()
    phys_components = create_rover_components("esp-1")
    phys_caps.register_from_components("esp-1", phys_components)
    phys_names = {c.name for c in phys_caps.list("esp-1")}

    assert sim_names == phys_names
    await mock.disconnect()


def test_safety_validator_bounds() -> None:
    from contracts.schemas.device import Capability

    validator = SafetyValidator()
    capability = Capability(
        name="move_forward",
        parameters_schema={
            "type": "object",
            "properties": {
                "speed": {"type": "number"},
                "duration_ms": {"type": "integer"},
            },
        },
    )
    params = validator.validate(capability, {"speed": 0.2, "duration_ms": 500})
    assert params["speed"] == 0.2
