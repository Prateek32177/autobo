"""Liveness and readiness endpoint tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from physical_ai.api.app import create_app
from physical_ai.config.settings import Settings


@pytest.fixture
async def client(tmp_path: Path):
    settings = Settings(
        database_path=tmp_path / "ready.db",
        seed_simulated_device=True,
        simulated_device_id="rover-sim-001",
        mock_telemetry_interval_seconds=0.05,
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.mark.asyncio
async def test_health_and_ready(client: AsyncClient) -> None:
    health = await client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    api_health = await client.get("/api/health")
    assert api_health.status_code == 200

    ready = await client.get("/ready")
    assert ready.status_code == 200
    body = ready.json()
    assert body["ready"] is True
    assert body["database"] == "ok"
