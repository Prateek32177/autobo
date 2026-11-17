"""Transport adapter — byte/line I/O only."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum


class TransportState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class TransportError(Exception):
    """Communication failure at the transport layer."""


class TransportTimeout(TransportError):
    """Read/write timed out."""


class TransportAdapter(ABC):
    """Low-level message/byte transport.

    Implementations must not parse protocol semantics.
    Extensible for future GPIO/I2C/SPI/network transports.
    """

    @abstractmethod
    async def connect(self) -> None:
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        ...

    @abstractmethod
    def state(self) -> TransportState:
        ...

    @abstractmethod
    async def write_line(self, line: str) -> None:
        """Write one newline-terminated logical message (caller may omit ``\\n``)."""

    @abstractmethod
    async def read_line(self, timeout: float | None = None) -> str:
        """Read one line (without trailing newline). Raises TransportTimeout on timeout."""

    def is_connected(self) -> bool:
        return self.state() == TransportState.CONNECTED
