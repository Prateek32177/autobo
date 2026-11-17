"""SQLite persistence for devices, components, telemetry and diagnostics."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    device_type TEXT NOT NULL,
    connection_type TEXT NOT NULL,
    connection_config TEXT NOT NULL,
    firmware_version TEXT,
    connectivity_status TEXT NOT NULL DEFAULT 'disconnected',
    health_status TEXT NOT NULL DEFAULT 'unknown',
    last_heartbeat_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS components (
    id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    name TEXT NOT NULL,
    component_type TEXT NOT NULL,
    adapter_type TEXT NOT NULL,
    configuration TEXT NOT NULL DEFAULT '{}',
    health_status TEXT NOT NULL DEFAULT 'unknown',
    last_reading_at TEXT,
    metrics TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    component_id TEXT,
    metric_name TEXT NOT NULL,
    metric_value TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS diagnostic_events (
    id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    component_id TEXT,
    event_code TEXT NOT NULL,
    severity TEXT NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    message TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    objective TEXT NOT NULL,
    status TEXT NOT NULL,
    plan_json TEXT,
    result_json TEXT,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS execution_events (
    id TEXT PRIMARY KEY,
    task_id TEXT,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    timestamp TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_telemetry_device_time
    ON telemetry(device_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_components_device
    ON components(device_id);
CREATE INDEX IF NOT EXISTS idx_diagnostics_device_time
    ON diagnostic_events(device_id, timestamp DESC);
"""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: Path, telemetry_retention_rows: int = 5000) -> None:
        self.path = path
        self.telemetry_retention_rows = telemetry_retention_rows
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA foreign_keys = ON")
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database is not connected")
        return self._conn

    # --- devices ---

    async def upsert_device(self, device: dict[str, Any]) -> None:
        now = _utcnow()
        await self.conn.execute(
            """
            INSERT INTO devices (
                id, name, device_type, connection_type, connection_config,
                firmware_version, connectivity_status, health_status,
                last_heartbeat_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                device_type=excluded.device_type,
                connection_type=excluded.connection_type,
                connection_config=excluded.connection_config,
                firmware_version=excluded.firmware_version,
                connectivity_status=excluded.connectivity_status,
                health_status=excluded.health_status,
                last_heartbeat_at=excluded.last_heartbeat_at,
                updated_at=excluded.updated_at
            """,
            (
                device["id"],
                device["name"],
                device["device_type"],
                device["connection_type"],
                json.dumps(device["connection_config"]),
                device.get("firmware_version"),
                device.get("connectivity_status", "disconnected"),
                device.get("health_status", "unknown"),
                device.get("last_heartbeat_at"),
                device.get("created_at", now),
                now,
            ),
        )
        await self.conn.commit()

    async def get_device(self, device_id: str) -> dict[str, Any] | None:
        cursor = await self.conn.execute(
            "SELECT * FROM devices WHERE id = ?", (device_id,)
        )
        row = await cursor.fetchone()
        return self._device_row(row) if row else None

    async def list_devices(self) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(
            "SELECT * FROM devices ORDER BY created_at ASC"
        )
        rows = await cursor.fetchall()
        return [self._device_row(row) for row in rows]

    async def delete_device(self, device_id: str) -> bool:
        cursor = await self.conn.execute(
            "DELETE FROM devices WHERE id = ?", (device_id,)
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def update_device_status(
        self,
        device_id: str,
        *,
        connectivity_status: str | None = None,
        health_status: str | None = None,
        firmware_version: str | None = None,
        last_heartbeat_at: str | None = None,
    ) -> None:
        device = await self.get_device(device_id)
        if device is None:
            return
        if connectivity_status is not None:
            device["connectivity_status"] = connectivity_status
        if health_status is not None:
            device["health_status"] = health_status
        if firmware_version is not None:
            device["firmware_version"] = firmware_version
        if last_heartbeat_at is not None:
            device["last_heartbeat_at"] = last_heartbeat_at
        await self.upsert_device(device)

    # --- components ---

    async def upsert_component(self, component: dict[str, Any]) -> None:
        await self.conn.execute(
            """
            INSERT INTO components (
                id, device_id, name, component_type, adapter_type,
                configuration, health_status, last_reading_at, metrics, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                component_type=excluded.component_type,
                adapter_type=excluded.adapter_type,
                configuration=excluded.configuration,
                health_status=excluded.health_status,
                last_reading_at=excluded.last_reading_at,
                metrics=excluded.metrics
            """,
            (
                component["id"],
                component["device_id"],
                component["name"],
                component["component_type"],
                component["adapter_type"],
                json.dumps(component.get("configuration", {})),
                component.get("health_status", "unknown"),
                component.get("last_reading_at"),
                json.dumps(component.get("metrics", {})),
                component.get("created_at", _utcnow()),
            ),
        )
        await self.conn.commit()

    async def list_components(self, device_id: str) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(
            "SELECT * FROM components WHERE device_id = ? ORDER BY name ASC",
            (device_id,),
        )
        rows = await cursor.fetchall()
        return [self._component_row(row) for row in rows]

    async def delete_components_for_device(self, device_id: str) -> None:
        await self.conn.execute(
            "DELETE FROM components WHERE device_id = ?", (device_id,)
        )
        await self.conn.commit()

    # --- telemetry ---

    async def insert_telemetry(
        self,
        *,
        device_id: str,
        metric_name: str,
        metric_value: Any,
        timestamp: str | None = None,
        component_id: str | None = None,
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO telemetry (device_id, component_id, metric_name, metric_value, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                device_id,
                component_id,
                metric_name,
                json.dumps(metric_value),
                timestamp or _utcnow(),
            ),
        )
        await self._prune_telemetry()
        await self.conn.commit()

    async def list_telemetry(
        self,
        device_id: str,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(
            """
            SELECT * FROM telemetry
            WHERE device_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (device_id, limit),
        )
        rows = await cursor.fetchall()
        return [self._telemetry_row(row) for row in rows]

    async def _prune_telemetry(self) -> None:
        await self.conn.execute(
            """
            DELETE FROM telemetry
            WHERE id NOT IN (
                SELECT id FROM telemetry ORDER BY id DESC LIMIT ?
            )
            """,
            (self.telemetry_retention_rows,),
        )

    # --- diagnostics ---

    async def insert_diagnostic_event(self, event: dict[str, Any]) -> None:
        await self.conn.execute(
            """
            INSERT INTO diagnostic_events (
                id, device_id, component_id, event_code, severity,
                evidence_json, message, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["id"],
                event["device_id"],
                event.get("component_id"),
                event["event_code"],
                event["severity"],
                json.dumps(event.get("evidence_json", {})),
                event["message"],
                event.get("timestamp", _utcnow()),
            ),
        )
        await self.conn.commit()

    async def list_diagnostic_events(
        self,
        *,
        device_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if device_id:
            cursor = await self.conn.execute(
                """
                SELECT * FROM diagnostic_events
                WHERE device_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (device_id, limit),
            )
        else:
            cursor = await self.conn.execute(
                """
                SELECT * FROM diagnostic_events
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )
        rows = await cursor.fetchall()
        return [self._diagnostic_row(row) for row in rows]

    # --- row helpers ---

    @staticmethod
    def _device_row(row: aiosqlite.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "device_type": row["device_type"],
            "connection_type": row["connection_type"],
            "connection_config": json.loads(row["connection_config"]),
            "firmware_version": row["firmware_version"],
            "connectivity_status": row["connectivity_status"],
            "health_status": row["health_status"],
            "last_heartbeat_at": row["last_heartbeat_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _component_row(row: aiosqlite.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "device_id": row["device_id"],
            "name": row["name"],
            "component_type": row["component_type"],
            "adapter_type": row["adapter_type"],
            "configuration": json.loads(row["configuration"]),
            "health_status": row["health_status"],
            "last_reading_at": row["last_reading_at"],
            "metrics": json.loads(row["metrics"]),
            "created_at": row["created_at"],
        }

    @staticmethod
    def _telemetry_row(row: aiosqlite.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "device_id": row["device_id"],
            "component_id": row["component_id"],
            "metric_name": row["metric_name"],
            "metric_value": json.loads(row["metric_value"]),
            "timestamp": row["timestamp"],
        }

    @staticmethod
    def _diagnostic_row(row: aiosqlite.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "device_id": row["device_id"],
            "component_id": row["component_id"],
            "event_code": row["event_code"],
            "severity": row["severity"],
            "evidence_json": json.loads(row["evidence_json"]),
            "message": row["message"],
            "timestamp": row["timestamp"],
        }
