"""Standardized health and observation models for component adapters."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from contracts.schemas.device import HealthStatus
from contracts.schemas.telemetry import Severity


class HealthEvidence(BaseModel):
    code: str
    message: str
    severity: Severity = Severity.INFO
    observed: dict[str, Any] = Field(default_factory=dict)
    expected: dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = True


class ComponentHealthReport(BaseModel):
    component_id: str
    status: HealthStatus
    metrics: dict[str, Any] = Field(default_factory=dict)
    evidence: list[HealthEvidence] = Field(default_factory=list)
    last_reading_at: datetime | None = None
    message: str | None = None


class ComponentObservation(BaseModel):
    component_id: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime
    raw: dict[str, Any] = Field(default_factory=dict)
