"""Operational component registry — live adapters, not DB metadata alone."""

from __future__ import annotations

from typing import Any

from contracts.schemas.health import ComponentHealthReport, ComponentObservation
from physical_ai.components.base import ComponentAdapter


class ComponentRegistry:
    def __init__(self) -> None:
        self._by_device: dict[str, dict[str, ComponentAdapter]] = {}

    def register(self, device_id: str, adapters: list[ComponentAdapter]) -> None:
        self._by_device[device_id] = {adapter.key: adapter for adapter in adapters}

    def unregister(self, device_id: str) -> None:
        self._by_device.pop(device_id, None)

    def list(self, device_id: str) -> list[ComponentAdapter]:
        return list(self._by_device.get(device_id, {}).values())

    def get(self, device_id: str, key: str) -> ComponentAdapter | None:
        return self._by_device.get(device_id, {}).get(key)

    async def connect_all(self, device_id: str) -> None:
        for adapter in self.list(device_id):
            await adapter.connect()

    async def disconnect_all(self, device_id: str) -> None:
        for adapter in self.list(device_id):
            await adapter.disconnect()

    async def dispatch_telemetry(
        self, device_id: str, payload: dict[str, Any]
    ) -> list[ComponentObservation]:
        observations: list[ComponentObservation] = []
        for adapter in self.list(device_id):
            obs = await adapter.ingest_telemetry(payload)
            if obs is not None:
                observations.append(obs)
        return observations

    async def health_reports(self, device_id: str) -> list[ComponentHealthReport]:
        reports: list[ComponentHealthReport] = []
        for adapter in self.list(device_id):
            reports.append(await adapter.get_health())
        return reports

    def metadata(self, device_id: str) -> list[dict[str, Any]]:
        return [adapter.to_metadata() for adapter in self.list(device_id)]
