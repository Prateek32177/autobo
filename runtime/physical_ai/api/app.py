"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
    registry.mock_interval_seconds = settings.mock_telemetry_interval_seconds
    registry.subscribe(ws_manager.broadcast)

    app.state.db = db
    app.state.registry = registry
    app.state.ready = True

    if settings.seed_simulated_device:
        device = await registry.ensure_simulated_rover(settings.simulated_device_id)
        logger.info(
            "Seeded simulated device %s (mode=%s)",
            device.id,
            device.connection.type.value,
        )

    yield

    app.state.ready = False
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
        version="0.2.0",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.ready = False

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

    def _health_payload() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": settings.app_name,
            "version": "0.2.0",
            "bind": f"{settings.host}:{settings.port}",
        }

    @app.get("/health")
    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        """Liveness — process is up."""
        return _health_payload()

    @app.get("/ready")
    @app.get("/api/ready")
    async def ready(request: Request) -> JSONResponse:
        """Readiness — DB connected and app finished startup."""
        db: Database | None = getattr(request.app.state, "db", None)
        is_ready = bool(getattr(request.app.state, "ready", False))
        db_ok = False
        detail = "starting"
        if is_ready and db is not None:
            try:
                await db.conn.execute("SELECT 1")
                db_ok = True
                detail = "ready"
            except Exception as exc:  # noqa: BLE001
                is_ready = False
                detail = f"database error: {exc}"
        payload = {
            "ready": is_ready and db_ok,
            "database": "ok" if db_ok else "unavailable",
            "detail": detail,
            "service": settings.app_name,
            "simulation_seed": settings.seed_simulated_device,
        }
        status_code = 200 if payload["ready"] else 503
        return JSONResponse(payload, status_code=status_code)

    @app.get("/api/meta")
    async def meta() -> dict[str, Any]:
        return {
            "milestone": 2,
            "hardware_modes": ["simulation", "serial"],
            "serial_ready": True,
            "ai_ready": False,
            "llm_configured": False,
            "architecture": {
                "transport": True,
                "protocol_session": True,
                "component_adapters": True,
                "capability_registry": True,
                "action_executor": True,
            },
            "features": {
                "overview": True,
                "devices": True,
                "live_telemetry": True,
                "diagnostics_events_api": True,
                "diagnostics_rules": False,
                "ai_playground": False,
                "llm_settings": False,
            },
            "note": (
                "Local-first runtime. Default device is an explicit simulation. "
                "ESP32 serial path is implemented in software; no board required to start."
            ),
        }

    return app


app = create_app()
