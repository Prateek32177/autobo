"""Device registry — identity, lifecycle and hardware integration wiring."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from physical_ai.capabilities.registry import CapabilityRegistry
from physical_ai.components.registry import ComponentRegistry
from physical_ai.core.models import (
    ConnectionConfig,
    ConnectionType,
    ConnectivityStatus,
    Device,
    DeviceCreate,
    DeviceSummary,
    DeviceType,
    HealthStatus,
    Component,
    ComponentType,
)
from physical_ai.execution.executor import ActionExecutor
from physical_ai.hardware.base import HardwareAdapter
from physical_ai.hardware.esp32_adapter import Esp32HardwareAdapter
from physical_ai.hardware.mock_adapter import MockHardwareAdapter
from physical_ai.hardware.protocol.session import ProtocolSessionError
from physical_ai.hardware.transport.base import TransportError
from physical_ai.storage.database import Database

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
    def __init__(
        self,
        db: Database,
        *,
        component_registry: ComponentRegistry | None = None,
        capability_registry: CapabilityRegistry | None = None,
    ) -> None:
        self.db = db
        self.components = component_registry or ComponentRegistry()
        self.capabilities = capability_registry or CapabilityRegistry()
        self.executor = ActionExecutor(
            capabilities=self.capabilities,
            components=self.components,
        )
        self.mock_interval_seconds = 1.0
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
            await self.register_device(
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

        live = {c["id"]: c for c in self.components.metadata(device_id)}
        components: list[Component] = []
        for c in await self.db.list_components(device_id):
            live_meta = live.get(c["id"])
            components.append(
                Component(
                    id=c["id"],
                    device_id=c["device_id"],
                    name=c["name"],
                    component_type=ComponentType(c["component_type"]),
                    adapter_type=c["adapter_type"],
                    configuration=c["configuration"],
                    health_status=HealthStatus(
                        (live_meta or c).get("health_status", c["health_status"])
                    ),
                    last_reading_at=_parse_dt(
                        (live_meta or {}).get("last_reading_at") or c["last_reading_at"]
                    ),
                    metrics=(live_meta or {}).get("metrics") or c["metrics"],
                    created_at=_parse_dt(c["created_at"]),
                )
            )

        capabilities = self.capabilities.list(device_id)
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
            capabilities=capabilities,
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
                interval_seconds=self.mock_interval_seconds,
                component_registry=self.components,
                capability_registry=self.capabilities,
            )
        else:
            if not device.connection.port:
                raise ValueError("Serial connection requires a port")
            adapter = Esp32HardwareAdapter(
                device_id=device_id,
                port=device.connection.port,
                baud_rate=device.connection.baud_rate or 115200,
                component_registry=self.components,
                capability_registry=self.capabilities,
            )

        adapter.on_heartbeat(lambda payload: self._handle_heartbeat(device_id, payload))
        adapter.on_telemetry(lambda payload: self._handle_telemetry(device_id, payload))
        adapter.on_disconnect(lambda: self._handle_disconnect(device_id))

        try:
            await adapter.connect()
        except (TransportError, ProtocolSessionError, OSError) as exc:
            raise ConnectionError(str(exc)) from exc
        self._adapters[device_id] = adapter
        await self.db.update_device_status(
            device_id,
            connectivity_status=ConnectivityStatus.CONNECTED.value,
            health_status=HealthStatus.HEALTHY.value,
        )
        await self._persist_component_metadata(device_id)
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
        for component in await self.db.list_components(device_id):
            component["health_status"] = HealthStatus.DISCONNECTED.value
            await self.db.upsert_component(component)
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

    async def invoke_capability(
        self,
        device_id: str,
        capability: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        adapter = self._adapters.get(device_id)
        if adapter is None:
            return {"status": "failed", "message": "Device not connected"}
        device = await self.get_device(device_id)
        healthy = device.health_status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)
        return await self.executor.execute(
            device_id,
            capability,
            parameters,
            hardware=adapter,
            device_healthy=healthy,
        )

    async def _handle_heartbeat(self, device_id: str, payload: dict[str, Any]) -> None:
        now = _utcnow().isoformat()
        await self.db.update_device_status(
            device_id,
            connectivity_status=ConnectivityStatus.CONNECTED.value,
            health_status=HealthStatus.HEALTHY.value,
            firmware_version=payload.get("firmware_version"),
            last_heartbeat_at=now,
        )
        await self._persist_component_metadata(device_id)
        await self._broadcast({"type": "heartbeat", **payload, "received_at": now})

    async def _handle_telemetry(self, device_id: str, payload: dict[str, Any]) -> None:
        """Persist observations already interpreted by component adapters."""
        now = _utcnow().isoformat()
        self._latest_telemetry[device_id] = {**payload, "received_at": now}

        for meta in self.components.metadata(device_id):
            for metric_name, metric_value in (meta.get("metrics") or {}).items():
                await self.db.insert_telemetry(
                    device_id=device_id,
                    component_id=meta["id"],
                    metric_name=metric_name,
                    metric_value=metric_value,
                    timestamp=now,
                )
            await self.db.upsert_component(
                {
                    "id": meta["id"],
                    "device_id": device_id,
                    "name": meta["name"],
                    "component_type": meta["component_type"],
                    "adapter_type": meta["adapter_type"],
                    "configuration": {},
                    "health_status": meta["health_status"],
                    "last_reading_at": meta.get("last_reading_at"),
                    "metrics": meta.get("metrics") or {},
                    "created_at": now,
                }
            )

        await self._broadcast({"type": "telemetry", **payload, "received_at": now})

    async def _handle_disconnect(self, device_id: str) -> None:
        await self.db.update_device_status(
            device_id,
            connectivity_status=ConnectivityStatus.DISCONNECTED.value,
            health_status=HealthStatus.DISCONNECTED.value,
        )
        await self._broadcast(
            {
                "type": "device_status",
                "device_id": device_id,
                "connectivity_status": ConnectivityStatus.DISCONNECTED.value,
                "health_status": HealthStatus.DISCONNECTED.value,
                "reason": "communication_lost",
            }
        )

    async def _persist_component_metadata(self, device_id: str) -> None:
        now = _utcnow().isoformat()
        for meta in self.components.metadata(device_id):
            await self.db.upsert_component(
                {
                    "id": meta["id"],
                    "device_id": device_id,
                    "name": meta["name"],
                    "component_type": meta["component_type"],
                    "adapter_type": meta["adapter_type"],
                    "configuration": {},
                    "health_status": meta["health_status"],
                    "last_reading_at": meta.get("last_reading_at"),
                    "metrics": meta.get("metrics") or {},
                    "created_at": now,
                }
            )


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)
