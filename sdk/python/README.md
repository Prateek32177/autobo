# Physical AI SDK

Thin client for the **local** Physical AI runtime. Distinct from the runtime service package (`physical-ai-runtime` / `physical_ai`).

```bash
# from repo root after ./scripts/setup.sh
cd runtime && source .venv/bin/activate
python -c "from physical_ai_sdk import RuntimeClient; print(RuntimeClient().health())"
```

```python
from physical_ai_sdk import RuntimeClient

client = RuntimeClient("http://127.0.0.1:8000")
print(client.health())
print(client.list_devices())
```

Mock simulation is owned by the runtime (seeded device `rover-sim-001`). The SDK does not talk to USB serial directly.
