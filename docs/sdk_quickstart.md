# SDK quickstart

The installable Python SDK is introduced incrementally. Milestone 1 focuses on the runtime API.

Target developer experience (later milestones):

```python
from physical_ai import Device

rover = Device.connect(port="/dev/cu.usbmodem001")
print(await rover.health.check())
result = await rover.agent.run("Move forward for one second and stop.")
```

Until the SDK package is published, use the local FastAPI endpoints under `/api/*`.
