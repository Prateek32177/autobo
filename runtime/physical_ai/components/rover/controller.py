from __future__ import annotations

from typing import Any

from contracts.schemas.device import Capability, ComponentType, HealthStatus
from contracts.schemas.health import ComponentObservation, HealthEvidence
from contracts.schemas.telemetry import Severity
from physical_ai.components.base import ComponentAdapter


class ControllerComponent(ComponentAdapter):
    key = "controller"
    name = "ESP32 Controller"
    component_type = ComponentType.CONTROLLER
    adapter_type = "esp32_controller"

    def get_capabilities(self) -> list[Capability]:
        return [
            Capability(
                name="get_device_health",
                description="Overall device/controller health",
            ),
            Capability(
                name="run_diagnostics",
                description="Run deterministic diagnostics",
            ),
        ]

    async def ingest_telemetry(self, payload: dict[str, Any]) -> ComponentObservation | None:
        metrics = {
            "uptime_ms": payload.get("uptime_ms", payload.get("timestamp_ms")),
            "firmware_version": payload.get("firmware_version"),
            "mode": payload.get("mode"),
        }
        if metrics["uptime_ms"] is None and metrics["firmware_version"] is None:
            return None
        return self._observe(metrics, raw=payload)

    async def ingest_heartbeat(self, payload: dict[str, Any]) -> ComponentObservation:
        self._status = HealthStatus.HEALTHY
        return self._observe(
            {
                "uptime_ms": payload.get("uptime_ms"),
                "firmware_version": payload.get("firmware_version"),
                "protocol_version": payload.get("protocol_version"),
            },
            raw=payload,
        )

    async def diagnostic_evidence(self) -> list[HealthEvidence]:
        base = await super().diagnostic_evidence()
        if base:
            return base
        if self._last_reading_at is None:
            return [
                HealthEvidence(
                    code="CONTROLLER_NO_TELEMETRY",
                    message="Controller has not reported telemetry yet",
                    severity=Severity.WARNING,
                    confirmed=True,
                )
            ]
        return []
