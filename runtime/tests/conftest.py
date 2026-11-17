"""Pytest fixtures for the Physical AI runtime."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from physical_ai.api.app import create_app
from physical_ai.config.settings import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_path=tmp_path / "test.db",
        seed_simulated_device=True,
        simulated_device_id="rover-sim-001",
        mock_telemetry_interval_seconds=0.05,
        cors_origins=["http://localhost:3000"],
    )


@pytest.fixture
async def app(settings: Settings):
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
