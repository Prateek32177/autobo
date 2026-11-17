"""Factory for ESP32 autonomous rover component adapters."""

from __future__ import annotations

from physical_ai.components.base import ComponentAdapter
from physical_ai.components.rover.battery import BatteryComponent
from physical_ai.components.rover.controller import ControllerComponent
from physical_ai.components.rover.distance import DistanceSensorComponent
from physical_ai.components.rover.encoder import EncoderComponent
from physical_ai.components.rover.motor import MotorComponent


def create_rover_components(device_id: str) -> list[ComponentAdapter]:
    return [
        ControllerComponent(device_id),
        DistanceSensorComponent(device_id),
        MotorComponent(device_id, key="left_motor", name="Left Motor", side="left"),
        MotorComponent(device_id, key="right_motor", name="Right Motor", side="right"),
        EncoderComponent(
            device_id,
            key="left_encoder",
            name="Left Encoder",
            side="left",
            telemetry_field="left_encoder",
        ),
        EncoderComponent(
            device_id,
            key="right_encoder",
            name="Right Encoder",
            side="right",
            telemetry_field="right_encoder",
        ),
        BatteryComponent(device_id),
    ]
