"""WebSocket live stream smoke test."""

from __future__ import annotations

import json
from pathlib import Path

from starlette.testclient import TestClient

from physical_ai.api.app import create_app
from physical_ai.config.settings import Settings


def test_websocket_sends_connected_frame(tmp_path: Path) -> None:
    settings = Settings(
        database_path=tmp_path / "ws.db",
        seed_simulated_device=True,
        simulated_device_id="rover-sim-001",
        mock_telemetry_interval_seconds=0.05,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as websocket:
            message = websocket.receive_text()
            payload = json.loads(message)
            assert payload["type"] == "connected"
