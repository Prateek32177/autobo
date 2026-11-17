"""Capability registry — definitions owned independently of AI/hardware specifics."""

from __future__ import annotations

from contracts.schemas.device import Capability
from physical_ai.components.base import ComponentAdapter


class CapabilityRegistry:
    def __init__(self) -> None:
        self._by_device: dict[str, dict[str, Capability]] = {}
        self._owners: dict[str, dict[str, str]] = {}  # device -> capability -> component key

    def clear(self, device_id: str) -> None:
        self._by_device.pop(device_id, None)
        self._owners.pop(device_id, None)

    def register_from_components(self, device_id: str, adapters: list[ComponentAdapter]) -> None:
        caps: dict[str, Capability] = {}
        owners: dict[str, str] = {}
        for adapter in adapters:
            for capability in adapter.get_capabilities():
                # First registration wins for shared names (e.g. stop).
                if capability.name not in caps:
                    caps[capability.name] = capability
                    owners[capability.name] = adapter.key
        self._by_device[device_id] = caps
        self._owners[device_id] = owners

    def register(self, device_id: str, capability: Capability, *, owner_key: str) -> None:
        self._by_device.setdefault(device_id, {})[capability.name] = capability
        self._owners.setdefault(device_id, {})[capability.name] = owner_key

    def list(self, device_id: str) -> list[Capability]:
        return list(self._by_device.get(device_id, {}).values())

    def get(self, device_id: str, name: str) -> Capability | None:
        return self._by_device.get(device_id, {}).get(name)

    def owner(self, device_id: str, name: str) -> str | None:
        return self._owners.get(device_id, {}).get(name)

    def has(self, device_id: str, name: str) -> bool:
        return name in self._by_device.get(device_id, {})
