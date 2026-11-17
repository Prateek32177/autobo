# SDK quickstart

The installable client package is **`physical-ai-sdk`** (`import physical_ai_sdk`).

It talks to the **local runtime over HTTP**. It does not embed the FastAPI service and does not open USB serial ports itself.

## Install

```bash
./scripts/setup.sh
# or, inside runtime/.venv:
pip install -e ./sdk/python
```

## Use against a running local runtime

```bash
./scripts/start.sh
```

```python
from physical_ai_sdk import RuntimeClient

client = RuntimeClient("http://127.0.0.1:8000")
print(client.ready())
print(client.list_devices())
health = client.get_health("rover-sim-001")
print(health["is_simulation"], health["latest_telemetry"])
```

## Mock hardware

The runtime seeds a **simulated** device (`rover-sim-001`) when `SEED_SIMULATED_DEVICE=true`. Use the dashboard or SDK against that device — no ESP32 required.

## Physical hardware (when available)

1. Flash `firmware/esp32` with PlatformIO.
2. Register a device with `connection.type=serial` and the correct port.
3. Call `client.connect(device_id)` or use the Devices page.

Serial port listing: `client.list_ports()` / `GET /api/hardware/ports`.

## Package boundary

| Package | Import | Role |
|---|---|---|
| `physical-ai-runtime` | `physical_ai` | Local FastAPI service / adapters |
| `physical-ai-sdk` | `physical_ai_sdk` | HTTP client for developers/scripts |
