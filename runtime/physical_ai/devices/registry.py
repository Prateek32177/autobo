"""Device registry — tracks devices, components and live adapters."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from physical_ai.core.models import (
    Capability,
    Component,
    ComponentType,
    ConnectionConfig,
    ConnectionType,
    ConnectivityStatus,
    Device,
    DeviceCreate,
    DeviceSummary,
    DeviceType,
    HealthStatus,
)
from physical_ai.hardware.base import HardwareAdapter
from physical_ai.hardware.mock_adapter import MockHardwareAdapter
from physical_ai.hardware.serial_adapter import SerialHardwareAdapter
from physical_ai.storage.database import Database

ROVER_CAPABILITIES = [
    Capability(name="get_device_health", description="Overall device health"),
    Capability(name="get_component_health", description="Per-component health"),
    Capability(name="get_distance", description="Read distance sensor"),
    Capability(
        name="move_forward",
        description="Move forward with bounded speed/duration",
        parameters_schema={
            "type": "object",
            "properties": {
                "speed": {"type": "number", "minimum": 0, "maximum": 0.4},
                "duration_ms": {"type": "integer", "minimum": 0, "maximum": 3000},
            },
        },
    ),
    Capability(
        name="move_backward",
        description="Move backward with bounded speed/duration",
        parameters_schema={
            "type": "object",
            "properties": {
                "speed": {"type": "number", "minimum": 0, "maximum": 0.4},
                "duration_ms": {"type": "integer", "minimum": 0, "maximum": 3000},
            },
        },
    ),
    Capability(name="turn_left", description="Turn left in place"),
    Capability(name="turn_right", description="Turn right in place"),
    Capability(name="stop", description="Stop motors"),
    Capability(name="run_diagnostics", description="Run deterministic diagnostics"),
]


DEFAULT_ROVER_COMPONENTS: list[tuple[str, str, ComponentType, str]] = [
    ("controller", "ESP32 Controller", ComponentType.CONTROLLER, "esp32_controller"),
    ("distance_sensor", "Distance Sensor", ComponentType.DISTANCE_SENSOR, "distance_sensor"),
    ("left_motor", "Left Motor", ComponentType.MOTOR, "dc_motor"),
    ("right_motor", "Right Motor", ComponentType.MOTOR, "dc_motor"),
    ("left_encoder", "Left Encoder", ComponentType.ENCODER, "wheel_encoder"),
    ("right_encoder", "Right Encoder", ComponentType.ENCODER, "wheel_encoder"),
    ("battery", "Battery", ComponentType.BATTERY, "battery_telemetry"),
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


class DeviceRegistry:
    def __init__(self, db: Database) -> None:
        self.db = db
        self._adapters: dict[str, HardwareAdapter] = {}
        self._latest_telemetry: dict[str, dict[str, Any]] = {}
        self._event_subscribers: list[Any] = []

    def subscribe(self, callback: Any) -> None:
        self._event_subscribers.append(callback)

    async def _broadcast(self, event: dict[str, Any]) -> None:
        for callback in list(self._event_subscribers):
            result = callback(event)
            if hasattr(result, "__await__"):
                await result

    async def register_device(self, payload: DeviceCreate, *, device_id: str | None = None) -> Device:
        now = _utcnow()
        device_id = device_id or f"device-{uuid.uuid4().hex[:8]}"
        connection = payload.connection

        if connection.type == ConnectionType.SERIAL and not connection.port:
            raise ValueError("Serial connection requires a port")

        await self.db.upsert_device(
            {
                "id": device_id,
                "name": payload.name,
                "device_type": payload.device_type.value,
                "connection_type": connection.type.value,
                "connection_config": connection.model_dump(),
                "firmware_version": payload.firmware_version,
                "connectivity_status": ConnectivityStatus.DISCONNECTED.value,
                "health_status": HealthStatus.UNKNOWN.value,
                "last_heartbeat_at": None,
                "created_at": _iso(now),
                "updated_at": _iso(now),
            }
        )

        component_keys = payload.components
        specs = DEFAULT_ROVER_COMPONENTS
        if component_keys:
            specs = [s for s in DEFAULT_ROVER_COMPONENTS if s[0] in component_keys]

        for key, name, ctype, adapter_type in specs:
            await self.db.upsert_component(
                {
                    "id": f"{device_id}:{key}",
                    "device_id": device_id,
                    "name": name,
                    "component_type": ctype.value,
                    "adapter_type": adapter_type,
                    "configuration": {},
                    "health_status": HealthStatus.UNKNOWN.value,
                    "last_reading_at": None,
                    "metrics": {},
                    "created_at": _iso(now),
                }
            )

        return await self.get_device(device_id)

    async def ensure_simulated_rover(self, device_id: str = "rover-sim-001") -> Device:
        existing = await self.db.get_device(device_id)
        if existing is None:
            device = await self.register_device(
                DeviceCreate(
                    name="Simulated Rover",
                    device_type=DeviceType.AUTONOMOUS_ROVER,
                    connection=ConnectionConfig(
                        type=ConnectionType.SIMULATION,
                        simulation_profile="default_rover",
                    ),
                    firmware_version="0.1.0-sim",
                ),
                device_id=device_id,
            )
        else:
            device = await self.get_device(device_id)

        if device_id not in self._adapters or not await self._adapters[device_id].is_connected():
            await self.connect_device(device_id)

        return await self.get_device(device_id)

    async def list_devices(self) -> list[DeviceSummary]:
        rows = await self.db.list_devices()
        summaries: list[DeviceSummary] = []
        for row in rows:
            summaries.append(
                DeviceSummary(
                    id=row["id"],
                    name=row["name"],
                    device_type=DeviceType(row["device_type"]),
                    connection_type=ConnectionType(row["connection_type"]),
                    connectivity_status=ConnectivityStatus(row["connectivity_status"]),
                    health_status=HealthStatus(row["health_status"]),
                    firmware_version=row["firmware_version"],
                    last_heartbeat_at=_parse_dt(row["last_heartbeat_at"]),
                    is_simulation=row["connection_type"] == ConnectionType.SIMULATION.value,
                )
            )
        return summaries

    async def get_device(self, device_id: str) -> Device:
        row = await self.db.get_device(device_id)
        if row is None:
            raise KeyError(f"Device not found: {device_id}")
        components = [
            Component(
                id=c["id"],
                device_id=c["device_id"],
                name=c["name"],
                component_type=ComponentType(c["component_type"]),
                adapter_type=c["adapter_type"],
                configuration=c["configuration"],
                health_status=HealthStatus(c["health_status"]),
                last_reading_at=_parse_dt(c["last_reading_at"]),
                metrics=c["metrics"],
                created_at=_parse_dt(c["created_at"]),
            )
            for c in await self.db.list_components(device_id)
        ]
        return Device(
            id=row["id"],
            name=row["name"],
            device_type=DeviceType(row["device_type"]),
            connection=ConnectionConfig.model_validate(row["connection_config"]),
            firmware_version=row["firmware_version"],
            connectivity_status=ConnectivityStatus(row["connectivity_status"]),
            health_status=HealthStatus(row["health_status"]),
            last_heartbeat_at=_parse_dt(row["last_heartbeat_at"]),
            components=components,
            capabilities=list(ROVER_CAPABILITIES),
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
        )

    async def delete_device(self, device_id: str) -> None:
        if device_id in self._adapters:
            await self.disconnect_device(device_id)
        deleted = await self.db.delete_device(device_id)
        if not deleted:
            raise KeyError(f"Device not found: {device_id}")

    async def connect_device(self, device_id: str) -> Device:
        device = await self.get_device(device_id)
        if device_id in self._adapters and await self._adapters[device_id].is_connected():
            return device

        if device.connection.type == ConnectionType.SIMULATION:
            adapter: HardwareAdapter = MockHardwareAdapter(
                device_id=device_id,
                firmware_version=device.firmware_version or "0.1.0-sim",
            )
        else:
            if not device.connection.port:
                raise ValueError("Serial connection requires a port")
            adapter = SerialHardwareAdapter(
                port=device.connection.port,
                baud_rate=device.connection.baud_rate or 115200,
                device_id=device_id,
            )

        adapter.on_heartbeat(lambda payload: self._handle_heartbeat(device_id, payload))
        adapter.on_telemetry(lambda payload: self._handle_telemetry(device_id, payload))

        await adapter.connect()
        self._adapters[device_id] = adapter
        await self.db.update_device_status(
            device_id,
            connectivity_status=ConnectivityStatus.CONNECTED.value,
            health_status=HealthStatus.HEALTHY.value,
        )
        await self._set_all_components_health(device_id, HealthStatus.HEALTHY)
        await self._broadcast(
            {
                "type": "device_status",
                "device_id": device_id,
                "connectivity_status": ConnectivityStatus.CONNECTED.value,
                "health_status": HealthStatus.HEALTHY.value,
                "mode": adapter.mode,
            }
        )
        return await self.get_device(device_id)

    async def disconnect_device(self, device_id: str) -> Device:
        adapter = self._adapters.pop(device_id, None)
        if adapter is not None:
            await adapter.disconnect()
        await self.db.update_device_status(
            device_id,
            connectivity_status=ConnectivityStatus.DISCONNECTED.value,
            health_status=HealthStatus.DISCONNECTED.value,
        )
        await self._set_all_components_health(device_id, HealthStatus.DISCONNECTED)
        await self._broadcast(
            {
                "type": "device_status",
                "device_id": device_id,
                "connectivity_status": ConnectivityStatus.DISCONNECTED.value,
                "health_status": HealthStatus.DISCONNECTED.value,
            }
        )
        return await self.get_device(device_id)

    def get_adapter(self, device_id: str) -> HardwareAdapter | None:
        return self._adapters.get(device_id)

    def get_latest_telemetry(self, device_id: str) -> dict[str, Any] | None:
        return self._latest_telemetry.get(device_id)

    async def emergency_stop(self, device_id: str | None = None) -> dict[str, Any]:
        targets = [device_id] if device_id else list(self._adapters.keys())
        stopped: list[str] = []
        for did in targets:
            adapter = self._adapters.get(did)
            if adapter is not None:
                await adapter.emergency_stop("api")
                stopped.append(did)
        await self._broadcast({"type": "emergency_stop", "device_ids": stopped})
        return {"stopped": stopped}

    async def _handle_heartbeat(self, device_id: str, payload: dict[str, Any]) -> None:
        now = _utcnow().isoformat()
        await self.db.update_device_status(
            device_id,
            connectivity_status=ConnectivityStatus.CONNECTED.value,
            health_status=HealthStatus.HEALTHY.value,
            firmware_version=payload.get("firmware_version"),
            last_heartbeat_at=now,
        )
        await self._broadcast({"type": "heartbeat", **payload, "received_at": now})

    async def _handle_telemetry(self, device_id: str, payload: dict[str, Any]) -> None:
        now = _utcnow().isoformat()
        self._latest_telemetry[device_id] = {**payload, "received_at": now}

        metric_map = {
            "battery_voltage": (f"{device_id}:battery", "battery_voltage"),
            "distance_cm": (f"{device_id}:distance_sensor", "distance_cm"),
            "left_encoder": (f"{device_id}:left_encoder", "ticks"),
            "right_encoder": (f"{device_id}:right_encoder", "ticks"),
        }
        for metric_name, (component_id, metric_key) in metric_map.items():
            if metric_name in payload:
                await self.db.insert_telemetry(
                    device_id=device_id,
                    component_id=component_id,
                    metric_name=metric_name,
                    metric_value=payload[metric_name],
                    timestamp=now,
                )
                await self._patch_component_metrics(
                    component_id,
                    health=HealthStatus.HEALTHY,
                    last_reading_at=now,
                    metrics={metric_key: payload[metric_name]},
                )

        motor_status = payload.get("motor_status") or {}
        for motor, side in (("left_motor", "left"), ("right_motor", "right")):
            await self._patch_component_metrics(
                f"{device_id}:{motor}",
                health=HealthStatus.HEALTHY,
                last_reading_at=now,
                metrics={"status": motor_status.get(side, "idle")},
            )

        await self._patch_component_metrics(
            f"{device_id}:controller",
            health=HealthStatus.HEALTHY,
            last_reading_at=now,
            metrics={
                "uptime_ms": payload.get("uptime_ms"),
                "firmware_version": payload.get("firmware_version"),
                "mode": payload.get("mode", "simulation"),
            },
        )

        await self._broadcast({"type": "telemetry", **payload, "received_at": now})

    async def _patch_component_metrics(
        self,
        component_id: str,
        *,
        health: HealthStatus,
        last_reading_at: str,
        metrics: dict[str, Any],
    ) -> None:
        device_id = component_id.split(":", 1)[0]
        existing = None
        for component in await self.db.list_components(device_id):
            if component["id"] == component_id:
                existing = component
                break
        if existing is None:
            return
        existing["health_status"] = health.value
        existing["last_reading_at"] = last_reading_at
        merged = dict(existing.get("metrics") or {})
        merged.update(metrics)
        existing["metrics"] = merged
        await self.db.upsert_component(existing)

    async def _set_all_components_health(self, device_id: str, status: HealthStatus) -> None:
        for component in await self.db.list_components(device_id):
            component["health_status"] = status.value
            await self.db.upsert_component(component)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)
