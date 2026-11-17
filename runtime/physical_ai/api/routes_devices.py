"""Device and component API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from physical_ai.api.deps import DbDep, RegistryDep
from physical_ai.core.models import Device, DeviceCreate, DeviceSummary

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get("", response_model=list[DeviceSummary])
async def list_devices(registry: RegistryDep) -> list[DeviceSummary]:
    return await registry.list_devices()


@router.post("", response_model=Device, status_code=201)
async def create_device(payload: DeviceCreate, registry: RegistryDep) -> Device:
    try:
        return await registry.register_device(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@router.get("/{device_id}", response_model=Device)
async def get_device(device_id: str, registry: RegistryDep) -> Device:
    try:
        return await registry.get_device(device_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{device_id}", status_code=204)
async def delete_device(device_id: str, registry: RegistryDep) -> None:
    try:
        await registry.delete_device(device_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{device_id}/health")
async def device_health(device_id: str, registry: RegistryDep) -> dict:
    try:
        device = await registry.get_device(device_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    telemetry = registry.get_latest_telemetry(device_id)
    emergency_stopped = device.id in registry._emergency_stopped or bool(
        (telemetry or {}).get("emergency_stopped") or (telemetry or {}).get("stopped")
    )
    return {
        "device_id": device.id,
        "connectivity_status": device.connectivity_status,
        "health_status": device.health_status,
        "firmware_version": device.firmware_version,
        "last_heartbeat_at": device.last_heartbeat_at,
        "is_simulation": device.connection.type.value == "simulation",
        "connection_mode": device.connection.type.value,
        "emergency_stopped": emergency_stopped,
        "components": [
            {
                "id": c.id,
                "name": c.name,
                "component_type": c.component_type,
                "health_status": c.health_status,
                "last_reading_at": c.last_reading_at,
                "metrics": c.metrics,
            }
            for c in device.components
        ],
        "latest_telemetry": telemetry,
    }


@router.get("/{device_id}/components")
async def list_components(device_id: str, registry: RegistryDep) -> list[dict]:
    try:
        device = await registry.get_device(device_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [c.model_dump(mode="json") for c in device.components]


@router.get("/{device_id}/telemetry")
async def list_telemetry(
    device_id: str,
    db: DbDep,
    registry: RegistryDep,
    limit: int = 50,
) -> dict:
    try:
        await registry.get_device(device_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    rows = await db.list_telemetry(device_id, limit=limit)
    return {
        "device_id": device_id,
        "latest": registry.get_latest_telemetry(device_id),
        "history": rows,
    }
