"""FastAPI dependency helpers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from physical_ai.devices.registry import DeviceRegistry
from physical_ai.storage.database import Database


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_registry(request: Request) -> DeviceRegistry:
    return request.app.state.registry


DbDep = Annotated[Database, Depends(get_db)]
RegistryDep = Annotated[DeviceRegistry, Depends(get_registry)]
