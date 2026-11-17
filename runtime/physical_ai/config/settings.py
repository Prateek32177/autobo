"""Runtime configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Physical AI Runtime"
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
    database_path: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[2] / "data" / "physical_ai.db"
    )
    telemetry_retention_rows: int = 5000
    seed_simulated_device: bool = True
    simulated_device_id: str = "rover-sim-001"
    mock_telemetry_interval_seconds: float = 1.0
    log_level: str = "INFO"


def get_settings() -> Settings:
    return Settings()
