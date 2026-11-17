"""Action executor — capability → validation → hardware/component path."""

from __future__ import annotations

import uuid
from typing import Any

from contracts.protocol import ProtocolCommand, ProtocolCommandResult, ResultStatus
from physical_ai.capabilities.registry import CapabilityRegistry
from physical_ai.components.registry import ComponentRegistry
from physical_ai.execution.safety import SafetyValidator, SafetyViolation
from physical_ai.hardware.base import HardwareAdapter


class ActionExecutor:
    def __init__(
        self,
        *,
        capabilities: CapabilityRegistry,
        components: ComponentRegistry,
        safety: SafetyValidator | None = None,
    ) -> None:
        self.capabilities = capabilities
        self.components = components
        self.safety = safety or SafetyValidator()

    async def execute(
        self,
        device_id: str,
        capability_name: str,
        parameters: dict[str, Any] | None = None,
        *,
        hardware: HardwareAdapter,
        device_healthy: bool = True,
    ) -> dict[str, Any]:
        capability = self.capabilities.get(device_id, capability_name)
        if capability is None:
            return {
                "status": "failed",
                "message": f"Unknown capability: {capability_name}",
            }

        try:
            validated = self.safety.validate(
                capability, parameters, device_healthy=device_healthy
            )
        except SafetyViolation as exc:
            return {"status": "rejected", "message": str(exc)}

        # Prefer hardware protocol command path for motion/IO actions.
        hardware_actions = {
            "move_forward",
            "move_backward",
            "turn_left",
            "turn_right",
            "stop",
            "read_distance",
            "read_battery",
            "read_encoders",
            "emergency_stop",
        }
        if capability_name in hardware_actions:
            command = ProtocolCommand(
                command_id=f"cmd-{uuid.uuid4().hex[:8]}",
                action=capability_name,
                parameters=validated,
            )
            # Mark motors/encoders when commanding motion.
            if capability_name.startswith("move") or capability_name.startswith("turn"):
                for key in ("left_motor", "right_motor"):
                    motor = self.components.get(device_id, key)
                    if motor is not None and hasattr(motor, "record_command"):
                        motor.record_command(capability_name, validated)  # type: ignore[attr-defined]
                for key in ("left_encoder", "right_encoder"):
                    enc = self.components.get(device_id, key)
                    if enc is not None and hasattr(enc, "expect_motion"):
                        enc.expect_motion(True)  # type: ignore[attr-defined]

            result: ProtocolCommandResult = await hardware.send_command(command)
            return {
                "status": result.status.value,
                "command_id": result.command_id,
                "result": result.model_dump(mode="json"),
            }

        owner_key = self.capabilities.owner(device_id, capability_name)
        adapter = self.components.get(device_id, owner_key) if owner_key else None
        if adapter is None:
            return {"status": "failed", "message": "No component owns this capability"}
        try:
            payload = await adapter.execute(capability_name, validated)
            return {"status": "completed", "result": payload}
        except Exception as exc:
            return {"status": ResultStatus.FAILED.value, "message": str(exc)}
