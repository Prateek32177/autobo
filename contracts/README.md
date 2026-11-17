# Contracts

Shared data models and serial protocol definitions for Physical AI.

- `schemas/` — devices, components, telemetry, diagnostics (Pydantic)
- `protocol/` — JSON Lines USB serial messages (Pydantic)
- `examples/` — sample JSON payloads

The runtime imports these as `contracts.*`. `physical_ai._paths` adds the monorepo root to `sys.path` automatically.
