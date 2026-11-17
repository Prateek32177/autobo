"""Component adapter contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from contracts.schemas.device import Capability, ComponentType, HealthStatus
from contracts.schemas.health import (
    ComponentHealthReport,
    ComponentObservation,
    HealthEvidence,
)
from contracts.schemas.telemetry import Severity


class ComponentAdapter(ABC):
    """Operational adapter for a single physical/logical component."""

    key: str
    name: str
    component_type: ComponentType
    adapter_type: str

    def __init__(self, device_id: str, *, component_id: str | None = None) -> None:
        self.device_id = device_id
        self.component_id = component_id or f"{device_id}:{self.key}"
        self._metrics: dict[str, Any] = {}
        self._last_reading_at: datetime | None = None
        self._status = HealthStatus.UNKNOWN
        self._connected = False

    async def connect(self) -> None:
        self._connected = True
        self._status = HealthStatus.UNKNOWN

    async def disconnect(self) -> None:
        self._connected = False
        self._status = HealthStatus.DISCONNECTED

    @abstractmethod
    def get_capabilities(self) -> list[Capability]:
        ...

    async def collect_metrics(self) -> dict[str, Any]:
        return dict(self._metrics)

    async def get_health(self) -> ComponentHealthReport:
        evidence = await self.diagnostic_evidence()
        return ComponentHealthReport(
            component_id=self.component_id,
            status=self._status,
            metrics=dict(self._metrics),
            evidence=evidence,
            last_reading_at=self._last_reading_at,
        )

    async def diagnostic_evidence(self) -> list[HealthEvidence]:
        if not self._connected:
            return [
                HealthEvidence(
                    code="COMPONENT_DISCONNECTED",
                    message=f"{self.name} is disconnected",
                    severity=Severity.ERROR,
                    confirmed=True,
                )
            ]
        return []

    async def run_diagnostics(self) -> list[HealthEvidence]:
        return await self.diagnostic_evidence()

    async def ingest_telemetry(self, payload: dict[str, Any]) -> ComponentObservation | None:
        """Interpret device telemetry relevant to this component. Return None if N/A."""
        return None

    async def execute(self, capability: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError(f"{self.key} does not execute capability '{capability}'")

    def _observe(self, metrics: dict[str, Any], *, raw: dict[str, Any] | None = None) -> ComponentObservation:
        now = datetime.now(timezone.utc)
        self._metrics.update(metrics)
        self._last_reading_at = now
        if self._status in (HealthStatus.UNKNOWN, HealthStatus.DISCONNECTED):
            self._status = HealthStatus.HEALTHY
        return ComponentObservation(
            component_id=self.component_id,
            metrics=dict(metrics),
            timestamp=now,
            raw=raw or {},
        )

    def to_metadata(self) -> dict[str, Any]:
        return {
            "id": self.component_id,
            "device_id": self.device_id,
            "name": self.name,
            "component_type": self.component_type.value,
            "adapter_type": self.adapter_type,
            "health_status": self._status.value,
            "last_reading_at": self._last_reading_at.isoformat() if self._last_reading_at else None,
            "metrics": dict(self._metrics),
        }
