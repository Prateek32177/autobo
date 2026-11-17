"""Dynamic AI tool definitions generated from registered capabilities."""

from __future__ import annotations

from typing import Any

from physical_ai.capabilities.registry import CapabilityRegistry


def tools_from_capabilities(registry: CapabilityRegistry, device_id: str) -> list[dict[str, Any]]:
    """Build provider-agnostic tool descriptors from CapabilityRegistry.

    The AI engine must not hardcode ESP32/rover functions; it consumes this list.
    """
    tools: list[dict[str, Any]] = []
    for capability in registry.list(device_id):
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": capability.name,
                    "description": capability.description or capability.name,
                    "parameters": capability.parameters_schema
                    or {"type": "object", "properties": {}},
                },
                "permission_level": capability.permission_level,
                "owner_component": registry.owner(device_id, capability.name),
            }
        )
    return tools
