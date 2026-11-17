"""HTTP client for the local Physical AI FastAPI runtime."""

from __future__ import annotations

from typing import Any

import httpx


class RuntimeClientError(RuntimeError):
    pass


class RuntimeClient:
    """Connects to a locally running Physical AI runtime (default localhost)."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000", *, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{path}"
        try:
            response = httpx.request(method, url, timeout=self.timeout, **kwargs)
        except httpx.HTTPError as exc:
            raise RuntimeClientError(f"Runtime unreachable at {url}: {exc}") from exc
        if response.status_code >= 400:
            raise RuntimeClientError(f"{method} {path} failed: {response.status_code} {response.text}")
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def ready(self) -> dict[str, Any]:
        return self._request("GET", "/ready")

    def meta(self) -> dict[str, Any]:
        return self._request("GET", "/api/meta")

    def list_devices(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/devices")

    def get_device(self, device_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/devices/{device_id}")

    def get_health(self, device_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/devices/{device_id}/health")

    def connect(self, device_id: str) -> dict[str, Any]:
        return self._request("POST", "/api/hardware/connect", json={"device_id": device_id})

    def disconnect(self, device_id: str) -> dict[str, Any]:
        return self._request("POST", "/api/hardware/disconnect", json={"device_id": device_id})

    def emergency_stop(self, device_id: str | None = None) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/hardware/emergency-stop",
            json={"device_id": device_id},
        )

    def list_ports(self) -> dict[str, Any]:
        return self._request("GET", "/api/hardware/ports")
