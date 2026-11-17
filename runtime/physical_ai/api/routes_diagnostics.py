"""Diagnostics API — history + placeholder run endpoint for Milestone 1."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from physical_ai.api.deps import DbDep, RegistryDep

router = APIRouter(tags=["diagnostics"])


@router.get("/api/devices/{device_id}/diagnostics")
async def device_diagnostics(
    device_id: str,
    db: DbDep,
    registry: RegistryDep,
    limit: int = 50,
) -> dict:
    try:
        await registry.get_device(device_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    events = await db.list_diagnostic_events(device_id=device_id, limit=limit)
    return {
        "device_id": device_id,
        "events": events,
        "note": "Deterministic diagnostic rules land in Milestone 3.",
    }


@router.post("/api/devices/{device_id}/diagnostics/run")
async def run_diagnostics(device_id: str, registry: RegistryDep) -> dict:
    try:
        device = await registry.get_device(device_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "device_id": device_id,
        "status": "skipped",
        "message": "Diagnostic engine arrives in Milestone 3. Device is reachable.",
        "health_status": device.health_status,
        "connection_mode": device.connection.type.value,
    }


@router.get("/api/diagnostics/events")
async def list_events(db: DbDep, limit: int = 50) -> dict:
    events = await db.list_diagnostic_events(limit=limit)
    return {"events": events}
