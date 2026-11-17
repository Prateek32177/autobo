"""Runtime configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RUNTIME_ROOT = Path(__file__).resolve().parents[2]


def _default_database_path() -> Path:
    return _RUNTIME_ROOT / "data" / "physical_ai.db"


def _env_files() -> tuple[str, ...]:
    candidates = [
        _REPO_ROOT / ".env",
        _RUNTIME_ROOT / ".env",
        Path.cwd() / ".env",
    ]
    return tuple(str(path) for path in candidates if path.is_file())


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_files() or (".env",),
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
    database_path: Path = Field(default_factory=_default_database_path)
    telemetry_retention_rows: int = 5000
    seed_simulated_device: bool = True
    simulated_device_id: str = "rover-sim-001"
    mock_telemetry_interval_seconds: float = 1.0
    log_level: str = "INFO"


def get_settings() -> Settings:
    return Settings()
