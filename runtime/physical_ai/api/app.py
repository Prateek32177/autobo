"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from physical_ai.api.routes_devices import router as devices_router
from physical_ai.api.routes_diagnostics import router as diagnostics_router
from physical_ai.api.routes_hardware import router as hardware_router
from physical_ai.api.routes_ws import manager as ws_manager
from physical_ai.api.routes_ws import router as ws_router
from physical_ai.config.settings import Settings, get_settings
from physical_ai.devices.registry import DeviceRegistry
from physical_ai.storage.database import Database

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    db = Database(settings.database_path, settings.telemetry_retention_rows)
    await db.connect()
    registry = DeviceRegistry(db)
    registry.subscribe(ws_manager.broadcast)

    app.state.db = db
    app.state.registry = registry

    if settings.seed_simulated_device:
        device = await registry.ensure_simulated_rover(settings.simulated_device_id)
        logger.info(
            "Seeded simulated device %s (mode=%s)",
            device.id,
            device.connection.type.value,
        )

    yield

    # Disconnect adapters cleanly.
    for summary in await registry.list_devices():
        adapter = registry.get_adapter(summary.id)
        if adapter is not None:
            await adapter.disconnect()
    await db.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(devices_router)
    app.include_router(hardware_router)
    app.include_router(diagnostics_router)
    app.include_router(ws_router)

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": settings.app_name,
            "version": "0.1.0",
            "bind": f"{settings.host}:{settings.port}",
        }

    @app.get("/api/meta")
    async def meta() -> dict[str, Any]:
        return {
            "milestone": 1,
            "hardware_modes": ["simulation", "serial"],
            "serial_ready": False,
            "ai_ready": False,
            "note": "Milestone 1 uses an explicitly simulated device by default.",
        }

    return app


app = create_app()
