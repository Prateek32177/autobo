from __future__ import annotations

from typing import Any

from contracts.schemas.device import Capability, ComponentType, HealthStatus
from contracts.schemas.health import ComponentObservation, HealthEvidence
from contracts.schemas.telemetry import Severity
from physical_ai.components.base import ComponentAdapter


class EncoderComponent(ComponentAdapter):
    component_type = ComponentType.ENCODER
    adapter_type = "wheel_encoder"

    def __init__(
        self,
        device_id: str,
        *,
        key: str,
        name: str,
        side: str,
        telemetry_field: str,
        component_id: str | None = None,
    ) -> None:
        self.key = key
        self.name = name
        self.side = side
        self.telemetry_field = telemetry_field
        super().__init__(device_id, component_id=component_id)
        self._previous_ticks: int | None = None
        self._expect_motion = False

    def get_capabilities(self) -> list[Capability]:
        return [
            Capability(
                name="get_component_health",
                description=f"{self.name} health and ticks",
            )
        ]

    async def ingest_telemetry(self, payload: dict[str, Any]) -> ComponentObservation | None:
        if self.telemetry_field not in payload:
            return None
        ticks = int(payload[self.telemetry_field])
        delta = 0 if self._previous_ticks is None else ticks - self._previous_ticks
        self._previous_ticks = ticks
        if self._expect_motion and delta == 0:
            self._status = HealthStatus.UNHEALTHY
        else:
            self._status = HealthStatus.HEALTHY
        return self._observe({"ticks": ticks, "delta": delta}, raw=payload)

    def expect_motion(self, expected: bool = True) -> None:
        self._expect_motion = expected

    async def diagnostic_evidence(self) -> list[HealthEvidence]:
        base = await super().diagnostic_evidence()
        if base:
            return base
        if self._expect_motion and self._metrics.get("delta", 0) == 0:
            return [
                HealthEvidence(
                    code="MOTOR_RESPONSE_MISSING",
                    message=f"{self.name} did not register expected movement",
                    severity=Severity.ERROR,
                    observed={"delta": self._metrics.get("delta", 0)},
                    expected={"delta_nonzero": True},
                    confirmed=True,
                )
            ]
        return []
