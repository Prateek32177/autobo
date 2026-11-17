"""Telemetry, heartbeat and diagnostic event contracts."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DiagnosticCode(str, Enum):
    DEVICE_DISCONNECTED = "DEVICE_DISCONNECTED"
    HEARTBEAT_TIMEOUT = "HEARTBEAT_TIMEOUT"
    SENSOR_UNRESPONSIVE = "SENSOR_UNRESPONSIVE"
    SENSOR_DATA_STALE = "SENSOR_DATA_STALE"
    SENSOR_VALUE_INVALID = "SENSOR_VALUE_INVALID"
    MOTOR_RESPONSE_MISSING = "MOTOR_RESPONSE_MISSING"
    BATTERY_VOLTAGE_LOW = "BATTERY_VOLTAGE_LOW"
    ACTION_TIMEOUT = "ACTION_TIMEOUT"
    TASK_VERIFICATION_FAILED = "TASK_VERIFICATION_FAILED"


class Heartbeat(BaseModel):
    device_id: str
    firmware_version: str
    uptime_ms: int
    timestamp: datetime | None = None


class MotorStatus(BaseModel):
    left: str = "idle"
    right: str = "idle"


class TelemetrySample(BaseModel):
    device_id: str
    component_id: str | None = None
    metric_name: str
    metric_value: float | int | str | bool
    timestamp: datetime
    unit: str | None = None


class DeviceTelemetry(BaseModel):
    """Aggregated live telemetry snapshot for a device."""

    device_id: str
    timestamp_ms: int
    battery_voltage: float | None = None
    distance_cm: float | None = None
    left_encoder: int | None = None
    right_encoder: int | None = None
    motor_status: MotorStatus = Field(default_factory=MotorStatus)
    uptime_ms: int | None = None
    firmware_version: str | None = None
    extras: dict[str, Any] = Field(default_factory=dict)


class DiagnosticEvent(BaseModel):
    id: str
    device_id: str
    component_id: str | None = None
    event_code: DiagnosticCode | str
    severity: Severity
    message: str
    observed_values: dict[str, Any] = Field(default_factory=dict)
    expected_values: dict[str, Any] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    source: str = "diagnostics"
    confidence: str | None = None
    timestamp: datetime


class ExecutionEvent(BaseModel):
    id: str
    task_id: str | None = None
    device_id: str | None = None
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime
