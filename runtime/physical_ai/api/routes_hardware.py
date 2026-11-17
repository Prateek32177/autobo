"""Hardware connection and emergency-stop routes."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from fastapi import APIRouter, HTTPException

from physical_ai.api.deps import RegistryDep
from physical_ai.core.models import Device
from physical_ai.hardware.serial_adapter import list_serial_ports

router = APIRouter(prefix="/api/hardware", tags=["hardware"])


class ConnectRequest(BaseModel):
    device_id: str = Field(min_length=1)


class DisconnectRequest(BaseModel):
    device_id: str = Field(min_length=1)


class EmergencyStopRequest(BaseModel):
    device_id: str | None = None


@router.get("/ports")
async def get_ports() -> dict:
    return {
        "ports": list_serial_ports(),
        "note": "ESP32 USB serial transport is available. Simulation remains the default local mode.",
    }


class InvokeRequest(BaseModel):
    device_id: str = Field(min_length=1)
    capability: str = Field(min_length=1)
    parameters: dict[str, Any] | None = None


@router.post("/connect", response_model=Device)
async def connect(payload: ConnectRequest, registry: RegistryDep) -> Device:
    try:
        return await registry.connect_device(payload.device_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/invoke")
async def invoke_capability(payload: InvokeRequest, registry: RegistryDep) -> dict:
    try:
        await registry.get_device(payload.device_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await registry.invoke_capability(
        payload.device_id,
        payload.capability,
        payload.parameters,
    )



@router.post("/disconnect", response_model=Device)
async def disconnect(payload: DisconnectRequest, registry: RegistryDep) -> Device:
    try:
        return await registry.disconnect_device(payload.device_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/emergency-stop")
async def emergency_stop(
    registry: RegistryDep,
    payload: EmergencyStopRequest | None = None,
) -> dict:
    device_id = payload.device_id if payload else None
    try:
        return await registry.emergency_stop(device_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
