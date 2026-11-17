"""Serial hardware adapter stub for ESP32 (Milestone 2).

Milestone 1 exposes the interface and port discovery helpers so the API and
dashboard can list ports and make connection mode explicit. Live serial I/O
is intentionally not implemented yet.
"""

from __future__ import annotations

from typing import Any

from physical_ai.core.models import ProtocolCommand, ProtocolCommandResult, ResultStatus
from physical_ai.hardware.base import HardwareAdapter


class SerialHardwareAdapter(HardwareAdapter):
    mode = "serial"

    def __init__(self, port: str, baud_rate: int = 115200, device_id: str = "unknown") -> None:
        self.port = port
        self.baud_rate = baud_rate
        self.device_id = device_id
        self._connected = False

    async def connect(self) -> None:
        raise NotImplementedError(
            "Serial ESP32 adapter will be implemented in Milestone 2. "
            "Use connection.type='simulation' for Milestone 1."
        )

    async def disconnect(self) -> None:
        self._connected = False

    async def is_connected(self) -> bool:
        return self._connected

    async def send_command(self, command: ProtocolCommand) -> ProtocolCommandResult:
        return ProtocolCommandResult(
            command_id=command.command_id,
            status=ResultStatus.FAILED,
            message="Serial adapter not available until Milestone 2",
        )

    async def emergency_stop(self, reason: str = "operator") -> None:
        return None


def list_serial_ports() -> list[dict[str, Any]]:
    """List available serial ports (best-effort)."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return []

    ports: list[dict[str, Any]] = []
    for info in list_ports.comports():
        ports.append(
            {
                "device": info.device,
                "description": info.description,
                "hwid": info.hwid,
                "manufacturer": getattr(info, "manufacturer", None),
            }
        )
    return ports
