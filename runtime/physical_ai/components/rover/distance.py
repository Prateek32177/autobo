from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from contracts.schemas.device import Capability, ComponentType, HealthStatus
from contracts.schemas.health import ComponentObservation, HealthEvidence
from contracts.schemas.telemetry import Severity
from physical_ai.components.base import ComponentAdapter

STALE_SECONDS = 5.0
MIN_CM = 2.0
MAX_CM = 400.0


class DistanceSensorComponent(ComponentAdapter):
    key = "distance_sensor"
    name = "Distance Sensor"
    component_type = ComponentType.DISTANCE_SENSOR
    adapter_type = "distance_sensor"

    def get_capabilities(self) -> list[Capability]:
        return [
            Capability(name="get_distance", description="Read distance sensor"),
            Capability(
                name="get_component_health",
                description="Distance sensor health",
            ),
        ]

    async def ingest_telemetry(self, payload: dict[str, Any]) -> ComponentObservation | None:
        if payload.get("distance_cm") is None:
            return None
        value = float(payload["distance_cm"])
        obs = self._observe({"distance_cm": value}, raw=payload)
        if value < MIN_CM or value > MAX_CM:
            self._status = HealthStatus.UNHEALTHY
        else:
            self._status = HealthStatus.HEALTHY
        return obs

    async def diagnostic_evidence(self) -> list[HealthEvidence]:
        base = await super().diagnostic_evidence()
        if base:
            return base
        evidence: list[HealthEvidence] = []
        value = self._metrics.get("distance_cm")
        if value is None:
            evidence.append(
                HealthEvidence(
                    code="SENSOR_UNRESPONSIVE",
                    message="No distance reading available",
                    severity=Severity.ERROR,
                    confirmed=True,
                )
            )
            self._status = HealthStatus.UNHEALTHY
            return evidence
        if value < MIN_CM or value > MAX_CM:
            evidence.append(
                HealthEvidence(
                    code="SENSOR_VALUE_INVALID",
                    message="Distance reading outside supported range",
                    severity=Severity.ERROR,
                    observed={"distance_cm": value},
                    expected={"min_cm": MIN_CM, "max_cm": MAX_CM},
                    confirmed=True,
                )
            )
            self._status = HealthStatus.UNHEALTHY
        if self._last_reading_at is not None:
            age = (datetime.now(timezone.utc) - self._last_reading_at).total_seconds()
            if age > STALE_SECONDS:
                evidence.append(
                    HealthEvidence(
                        code="SENSOR_DATA_STALE",
                        message="Distance reading is stale",
                        severity=Severity.WARNING,
                        observed={"age_seconds": age},
                        expected={"max_age_seconds": STALE_SECONDS},
                        confirmed=True,
                    )
                )
                self._status = HealthStatus.DEGRADED
        return evidence

    async def execute(self, capability: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        if capability == "get_distance":
            return {"distance_cm": self._metrics.get("distance_cm")}
        if capability == "get_component_health":
            report = await self.get_health()
            return report.model_dump(mode="json")
        return await super().execute(capability, parameters)
