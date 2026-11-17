from __future__ import annotations

from typing import Any

from contracts.schemas.device import Capability, ComponentType, HealthStatus
from contracts.schemas.health import ComponentObservation, HealthEvidence
from contracts.schemas.telemetry import Severity
from physical_ai.components.base import ComponentAdapter

LOW_VOLTAGE = 6.8


class BatteryComponent(ComponentAdapter):
    key = "battery"
    name = "Battery"
    component_type = ComponentType.BATTERY
    adapter_type = "battery_telemetry"

    def get_capabilities(self) -> list[Capability]:
        return [
            Capability(name="get_component_health", description="Battery health"),
        ]

    async def ingest_telemetry(self, payload: dict[str, Any]) -> ComponentObservation | None:
        if "battery_voltage" not in payload:
            return None
        voltage = float(payload["battery_voltage"])
        obs = self._observe({"battery_voltage": voltage}, raw=payload)
        self._status = HealthStatus.DEGRADED if voltage < LOW_VOLTAGE else HealthStatus.HEALTHY
        return obs

    async def diagnostic_evidence(self) -> list[HealthEvidence]:
        base = await super().diagnostic_evidence()
        if base:
            return base
        voltage = self._metrics.get("battery_voltage")
        if voltage is None:
            return [
                HealthEvidence(
                    code="BATTERY_NO_READING",
                    message="No battery voltage reading",
                    severity=Severity.WARNING,
                    confirmed=True,
                )
            ]
        if voltage < LOW_VOLTAGE:
            return [
                HealthEvidence(
                    code="BATTERY_VOLTAGE_LOW",
                    message="Battery voltage below configured threshold",
                    severity=Severity.WARNING,
                    observed={"battery_voltage": voltage},
                    expected={"min_voltage": LOW_VOLTAGE},
                    confirmed=True,
                )
            ]
        return []
