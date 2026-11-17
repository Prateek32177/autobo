"""USB serial transport using PySerial (ESP32 MVP)."""

from __future__ import annotations

import asyncio
from typing import Any

from physical_ai.hardware.transport.base import (
    TransportAdapter,
    TransportError,
    TransportState,
    TransportTimeout,
)


class SerialTransport(TransportAdapter):
    def __init__(self, port: str, baud_rate: int = 115200, *, read_timeout: float = 1.0) -> None:
        self.port = port
        self.baud_rate = baud_rate
        self.read_timeout = read_timeout
        self._state = TransportState.DISCONNECTED
        self._serial: Any = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        self._state = TransportState.CONNECTING
        try:
            import serial
        except ImportError as exc:
            self._state = TransportState.ERROR
            raise TransportError("pyserial is required for SerialTransport") from exc

        def _open() -> Any:
            return serial.Serial(self.port, self.baud_rate, timeout=self.read_timeout)

        try:
            self._serial = await asyncio.to_thread(_open)
        except Exception as exc:
            self._state = TransportState.ERROR
            raise TransportError(f"Failed to open serial port {self.port}: {exc}") from exc
        self._state = TransportState.CONNECTED

    async def disconnect(self) -> None:
        serial_obj = self._serial
        self._serial = None
        self._state = TransportState.DISCONNECTED
        if serial_obj is not None:
            await asyncio.to_thread(serial_obj.close)

    def state(self) -> TransportState:
        return self._state

    async def write_line(self, line: str) -> None:
        if self._serial is None or self._state != TransportState.CONNECTED:
            raise TransportError("Serial transport not connected")
        payload = (line.rstrip("\n") + "\n").encode("utf-8")

        def _write() -> None:
            self._serial.write(payload)
            self._serial.flush()

        async with self._lock:
            try:
                await asyncio.to_thread(_write)
            except Exception as exc:
                self._state = TransportState.ERROR
                raise TransportError(f"Serial write failed: {exc}") from exc

    async def read_line(self, timeout: float | None = None) -> str:
        if self._serial is None or self._state != TransportState.CONNECTED:
            raise TransportError("Serial transport not connected")

        def _read() -> str:
            raw = self._serial.readline()
            if not raw:
                raise TimeoutError("serial readline empty")
            return raw.decode("utf-8", errors="replace").rstrip("\r\n")

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(_read),
                timeout=timeout if timeout is not None else self.read_timeout + 0.5,
            )
        except TimeoutError as exc:
            raise TransportTimeout("Serial read timed out") from exc
        except Exception as exc:
            if isinstance(exc, TransportTimeout):
                raise
            self._state = TransportState.ERROR
            raise TransportError(f"Serial read failed: {exc}") from exc


def list_serial_ports() -> list[dict[str, Any]]:
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    return [
        {
            "device": info.device,
            "description": info.description,
            "hwid": info.hwid,
            "manufacturer": getattr(info, "manufacturer", None),
        }
        for info in list_ports.comports()
    ]
