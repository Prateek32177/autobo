"""API integration tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from physical_ai.api.app import create_app
from physical_ai.config.settings import Settings


@pytest.fixture
async def client(tmp_path: Path):
    settings = Settings(
        database_path=tmp_path / "api.db",
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
async def test_health(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_meta_marks_simulation_milestone(client: AsyncClient) -> None:
    response = await client.get("/api/meta")
    assert response.status_code == 200
    body = response.json()
    assert body["milestone"] == 2
    assert body["serial_ready"] is True
    assert body["architecture"]["protocol_session"] is True


@pytest.mark.asyncio
async def test_list_seeded_simulated_device(client: AsyncClient) -> None:
    response = await client.get("/api/devices")
    assert response.status_code == 200
    devices = response.json()
    assert len(devices) >= 1
    sim = next(d for d in devices if d["id"] == "rover-sim-001")
    assert sim["is_simulation"] is True
    assert sim["connection_type"] == "simulation"
    assert sim["connectivity_status"] == "connected"


@pytest.mark.asyncio
async def test_device_health_includes_components(client: AsyncClient) -> None:
    await asyncio.sleep(0.12)
    response = await client.get("/api/devices/rover-sim-001/health")
    assert response.status_code == 200
    body = response.json()
    assert body["is_simulation"] is True
    assert body["connection_mode"] == "simulation"
    assert len(body["components"]) == 7
    assert body["latest_telemetry"] is not None
    assert "battery_voltage" in body["latest_telemetry"]


@pytest.mark.asyncio
async def test_create_and_delete_device(client: AsyncClient) -> None:
    create = await client.post(
        "/api/devices",
        json={
            "name": "Another Sim",
            "device_type": "autonomous_rover",
            "connection": {"type": "simulation", "simulation_profile": "default_rover"},
            "firmware_version": "0.1.0-sim",
        },
    )
    assert create.status_code == 201
    device_id = create.json()["id"]

    detail = await client.get(f"/api/devices/{device_id}")
    assert detail.status_code == 200
    assert detail.json()["connection"]["type"] == "simulation"

    deleted = await client.delete(f"/api/devices/{device_id}")
    assert deleted.status_code == 204


@pytest.mark.asyncio
async def test_emergency_stop(client: AsyncClient) -> None:
    response = await client.post(
        "/api/hardware/emergency-stop",
        json={"device_id": "rover-sim-001"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "rover-sim-001" in body["stopped"]
    assert body["emergency_stopped"] is True
    health = await client.get("/api/devices/rover-sim-001/health")
    assert health.json()["emergency_stopped"] is True
    assert health.json()["latest_telemetry"]["emergency_stopped"] is True


@pytest.mark.asyncio
async def test_emergency_stop_requires_connection(client: AsyncClient) -> None:
    await client.post(
        "/api/hardware/disconnect",
        json={"device_id": "rover-sim-001"},
    )
    response = await client.post(
        "/api/hardware/emergency-stop",
        json={"device_id": "rover-sim-001"},
    )
    assert response.status_code == 409
    assert "not connected" in response.json()["detail"].lower()



@pytest.mark.asyncio
async def test_serial_connect_fails_without_device(client: AsyncClient) -> None:
    create = await client.post(
        "/api/devices",
        json={
            "name": "Real Port Placeholder",
            "connection": {
                "type": "serial",
                "port": "/dev/does-not-exist-physical-ai",
                "baud_rate": 115200,
            },
        },
    )
    assert create.status_code == 201
    device_id = create.json()["id"]
    connect = await client.post("/api/hardware/connect", json={"device_id": device_id})
    assert connect.status_code == 502

