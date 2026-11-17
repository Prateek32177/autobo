"""Backward-compatible serial entrypoint — delegates to Esp32HardwareAdapter."""

from __future__ import annotations

from physical_ai.capabilities.registry import CapabilityRegistry
from physical_ai.components.registry import ComponentRegistry
from physical_ai.hardware.esp32_adapter import Esp32HardwareAdapter
from physical_ai.hardware.transport.serial import list_serial_ports

# Historical name used by M1 DeviceRegistry / tests.
SerialHardwareAdapter = Esp32HardwareAdapter

__all__ = ["Esp32HardwareAdapter", "SerialHardwareAdapter", "list_serial_ports", "CapabilityRegistry", "ComponentRegistry"]
