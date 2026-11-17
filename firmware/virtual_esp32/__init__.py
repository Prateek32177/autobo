"""Virtual ESP32 protocol simulator (serial/PTY peer)."""

from .device_state import DeviceState
from .scenarios import Scenario, ScenarioConfig
from .simulator import VirtualEsp32

__all__ = ["DeviceState", "Scenario", "ScenarioConfig", "VirtualEsp32"]
