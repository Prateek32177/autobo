"""Helpers to create a virtual serial PTY pair for host ↔ Virtual ESP32."""

from __future__ import annotations

import os
import pty
import select
import threading
import tty
from dataclasses import dataclass


@dataclass
class LinkedPtyPair:
    """Two named slave TTYs bridged together (true independent ends).

    - Host / ``SerialHardwareAdapter`` opens ``host_port``
    - Virtual ESP32 opens ``device_port``

    Masters are bridged; slave FDs are retained as holders so macOS accepts
    writes to a master before/after a client opens the peer (no EIO). Clients
    may still open the same slave paths (verified with pyserial on Darwin).
    """

    host_port: str
    device_port: str
    _stop: threading.Event
    _thread: threading.Thread
    _fds: tuple[int, int, int, int]

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)
        for fd in self._fds:
            try:
                os.close(fd)
            except OSError:
                pass


def open_linked_pty_pair() -> LinkedPtyPair:
    """Create two PTYs and bridge their masters so each slave is a serial endpoint."""
    host_master, host_slave = pty.openpty()
    device_master, device_slave = pty.openpty()
    for fd in (host_master, device_master):
        try:
            tty.setraw(fd)
        except Exception:  # noqa: BLE001
            pass

    stop = threading.Event()

    def _bridge() -> None:
        while not stop.is_set():
            try:
                readable, _, _ = select.select([host_master, device_master], [], [], 0.05)
            except (OSError, ValueError):
                break
            for src, dst in (
                (host_master, device_master),
                (device_master, host_master),
            ):
                if src not in readable:
                    continue
                try:
                    data = os.read(src, 4096)
                except OSError:
                    # Client hangup / transient error — keep pair for reconnect.
                    continue
                if not data:
                    continue
                try:
                    os.write(dst, data)
                except OSError:
                    continue

    thread = threading.Thread(target=_bridge, name="pty-bridge", daemon=True)
    thread.start()
    return LinkedPtyPair(
        host_port=os.ttyname(host_slave),
        device_port=os.ttyname(device_slave),
        _stop=stop,
        _thread=thread,
        _fds=(host_master, host_slave, device_master, device_slave),
    )
