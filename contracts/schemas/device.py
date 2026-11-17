"""Shared device and component data contracts."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DeviceType(str, Enum):
    AUTONOMOUS_ROVER = "autonomous_rover"
    GENERIC = "generic"


class ConnectionType(str, Enum):
    SIMULATION = "simulation"
    SERIAL = "serial"


class ConnectivityStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    DISCONNECTED = "disconnected"


class ComponentType(str, Enum):
    CONTROLLER = "controller"
    DISTANCE_SENSOR = "distance_sensor"
    MOTOR = "motor"
    ENCODER = "encoder"
    BATTERY = "battery"
    CAMERA = "camera"


class ConnectionConfig(BaseModel):
    type: ConnectionType
    port: str | None = None
    baud_rate: int | None = Field(default=115200, ge=9600, le=921600)
    simulation_profile: str | None = "default_rover"


class Capability(BaseModel):
    name: str
    description: str = ""
    parameters_schema: dict[str, Any] = Field(default_factory=dict)
    permission_level: str = "standard"


class Component(BaseModel):
    id: str
    device_id: str
    name: str
    component_type: ComponentType
    adapter_type: str
    configuration: dict[str, Any] = Field(default_factory=dict)
    health_status: HealthStatus = HealthStatus.UNKNOWN
    last_reading_at: datetime | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class Device(BaseModel):
    id: str
    name: str
    device_type: DeviceType
    connection: ConnectionConfig
    firmware_version: str | None = None
    connectivity_status: ConnectivityStatus = ConnectivityStatus.DISCONNECTED
    health_status: HealthStatus = HealthStatus.UNKNOWN
    last_heartbeat_at: datetime | None = None
    components: list[Component] = Field(default_factory=list)
    capabilities: list[Capability] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    device_type: DeviceType = DeviceType.AUTONOMOUS_ROVER
    connection: ConnectionConfig
    firmware_version: str | None = "0.1.0-sim"
    components: list[str] | None = None


class DeviceSummary(BaseModel):
    id: str
    name: str
    device_type: DeviceType
    connection_type: ConnectionType
    connectivity_status: ConnectivityStatus
    health_status: HealthStatus
    firmware_version: str | None = None
    last_heartbeat_at: datetime | None = None
    is_simulation: bool
