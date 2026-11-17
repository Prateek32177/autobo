"""Safety policy validation for capability invocations."""

from __future__ import annotations

from typing import Any

from contracts.schemas.device import Capability


class SafetyViolation(Exception):
    pass


class SafetyValidator:
    MAX_SPEED = 0.4
    MAX_DURATION_MS = 3000

    def validate(
        self,
        capability: Capability,
        parameters: dict[str, Any] | None,
        *,
        device_healthy: bool = True,
    ) -> dict[str, Any]:
        if not device_healthy:
            raise SafetyViolation("Device is not healthy enough to execute actions")

        params = dict(parameters or {})
        schema = capability.parameters_schema or {}
        properties = schema.get("properties", {})

        if "speed" in properties or "speed" in params:
            speed = float(params.get("speed", 0.15))
            if speed < 0 or speed > self.MAX_SPEED:
                raise SafetyViolation(f"speed {speed} exceeds max {self.MAX_SPEED}")
            params["speed"] = speed

        if "duration_ms" in properties or "duration_ms" in params:
            duration = int(params.get("duration_ms", 500))
            if duration < 0 or duration > self.MAX_DURATION_MS:
                raise SafetyViolation(
                    f"duration_ms {duration} exceeds max {self.MAX_DURATION_MS}"
                )
            params["duration_ms"] = duration

        return params
