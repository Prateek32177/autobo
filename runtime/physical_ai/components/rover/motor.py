from __future__ import annotations

from typing import Any

from contracts.schemas.device import Capability, ComponentType, HealthStatus
from contracts.schemas.health import ComponentObservation, HealthEvidence
from contracts.schemas.telemetry import Severity
from physical_ai.components.base import ComponentAdapter

MOVE_SCHEMA = {
    "type": "object",
    "properties": {
        "speed": {"type": "number", "minimum": 0, "maximum": 0.4},
        "duration_ms": {"type": "integer", "minimum": 0, "maximum": 3000},
    },
}


class MotorComponent(ComponentAdapter):
    component_type = ComponentType.MOTOR
    adapter_type = "dc_motor"

    def __init__(
        self,
        device_id: str,
        *,
        key: str,
        name: str,
        side: str,
        component_id: str | None = None,
    ) -> None:
        self.key = key
        self.name = name
        self.side = side
        super().__init__(device_id, component_id=component_id)
        self._last_command: dict[str, Any] | None = None

    def get_capabilities(self) -> list[Capability]:
        caps = [
            Capability(
                name="stop",
                description="Stop motors",
            ),
        ]
        if self.side == "left":
            # Device-level movement capabilities registered once via left motor + shared set.
            caps.extend(
                [
                    Capability(
                        name="move_forward",
                        description="Move forward with bounded speed/duration",
                        parameters_schema=MOVE_SCHEMA,
                    ),
                    Capability(
                        name="move_backward",
                        description="Move backward with bounded speed/duration",
                        parameters_schema=MOVE_SCHEMA,
                    ),
                    Capability(
                        name="turn_left",
                        description="Turn left in place",
                        parameters_schema=MOVE_SCHEMA,
                    ),
                    Capability(
                        name="turn_right",
                        description="Turn right in place",
                        parameters_schema=MOVE_SCHEMA,
                    ),
                ]
            )
        return caps

    async def ingest_telemetry(self, payload: dict[str, Any]) -> ComponentObservation | None:
        motor_status = payload.get("motor_status") or {}
        if self.side not in motor_status and "motor_status" not in payload:
            return None
        status = motor_status.get(self.side, "idle")
        self._status = HealthStatus.HEALTHY
        return self._observe({"status": status}, raw=payload)

    def record_command(self, action: str, parameters: dict[str, Any] | None = None) -> None:
        self._last_command = {"action": action, "parameters": parameters or {}}

    async def diagnostic_evidence(self) -> list[HealthEvidence]:
        base = await super().diagnostic_evidence()
        if base:
            return base
        if self._last_command and self._metrics.get("status") == "idle":
            # Evidence only — encoder components confirm motion separately.
            return [
                HealthEvidence(
                    code="MOTOR_COMMAND_RECORDED",
                    message="Motor command was issued; verify encoder response",
                    severity=Severity.INFO,
                    observed={"last_command": self._last_command, "status": self._metrics.get("status")},
                    confirmed=True,
                )
            ]
        return []
