"""JSON Lines serial protocol message contracts.

Firmware (ESP32) and the runtime hardware adapter exchange one JSON object
per line at 115200 baud. These models are the shared source of truth.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field

PROTOCOL_VERSION = "1.0"


class MessageType(str, Enum):
    HANDSHAKE = "handshake"
    HANDSHAKE_ACK = "handshake_ack"
    HEARTBEAT = "heartbeat"
    TELEMETRY = "telemetry"
    COMMAND = "command"
    COMMAND_ACK = "command_ack"
    COMMAND_RESULT = "command_result"
    EMERGENCY_STOP = "emergency_stop"
    ERROR = "error"


class ProtocolComponentInfo(BaseModel):
    key: str
    component_type: str
    name: str | None = None


class ProtocolCapabilityInfo(BaseModel):
    name: str
    component_key: str | None = None
    description: str = ""
    parameters_schema: dict[str, Any] = Field(default_factory=dict)


class ProtocolHandshake(BaseModel):
    type: Literal["handshake"] = "handshake"
    device_id: str
    manufacturer: str = "physical-ai"
    board: str = "esp32"
    model: str = "autonomous_rover"
    firmware_version: str
    protocol_version: str = PROTOCOL_VERSION
    supported_components: list[ProtocolComponentInfo] = Field(default_factory=list)
    supported_capabilities: list[ProtocolCapabilityInfo] = Field(default_factory=list)


class ProtocolHandshakeAck(BaseModel):
    type: Literal["handshake_ack"] = "handshake_ack"
    device_id: str
    protocol_version: str = PROTOCOL_VERSION
    status: Literal["accepted", "rejected"] = "accepted"
    reason: str | None = None


class ProtocolHeartbeat(BaseModel):
    type: Literal["heartbeat"] = "heartbeat"
    device_id: str
    firmware_version: str
    uptime_ms: int
    protocol_version: str = PROTOCOL_VERSION


class ProtocolMotorStatus(BaseModel):
    left: str = "idle"
    right: str = "idle"


class ProtocolTelemetry(BaseModel):
    type: Literal["telemetry"] = "telemetry"
    device_id: str
    timestamp_ms: int
    battery_voltage: float
    distance_cm: float
    left_encoder: int
    right_encoder: int
    motor_status: ProtocolMotorStatus = Field(default_factory=ProtocolMotorStatus)
    uptime_ms: int | None = None
    firmware_version: str | None = None
    emergency_stopped: bool = False


class CommandAction(str, Enum):
    MOVE_FORWARD = "move_forward"
    MOVE_BACKWARD = "move_backward"
    TURN_LEFT = "turn_left"
    TURN_RIGHT = "turn_right"
    STOP = "stop"
    READ_DISTANCE = "read_distance"
    READ_BATTERY = "read_battery"
    READ_ENCODERS = "read_encoders"
    EMERGENCY_STOP = "emergency_stop"


class ProtocolCommand(BaseModel):
    type: Literal["command"] = "command"
    command_id: str
    action: CommandAction | str
    parameters: dict[str, Any] = Field(default_factory=dict)


class AckStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ProtocolCommandAck(BaseModel):
    type: Literal["command_ack"] = "command_ack"
    command_id: str
    status: AckStatus
    reason: str | None = None


class ResultStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ProtocolCommandResult(BaseModel):
    type: Literal["command_result"] = "command_result"
    command_id: str
    status: ResultStatus
    left_encoder_delta: int | None = None
    right_encoder_delta: int | None = None
    distance_cm: float | None = None
    battery_voltage: float | None = None
    message: str | None = None


class ProtocolEmergencyStop(BaseModel):
    type: Literal["emergency_stop"] = "emergency_stop"
    command_id: str | None = None
    reason: str = "operator"


class ProtocolError(BaseModel):
    type: Literal["error"] = "error"
    code: str
    message: str
    command_id: str | None = None


ProtocolMessage = Annotated[
    Union[
        ProtocolHandshake,
        ProtocolHandshakeAck,
        ProtocolHeartbeat,
        ProtocolTelemetry,
        ProtocolCommand,
        ProtocolCommandAck,
        ProtocolCommandResult,
        ProtocolEmergencyStop,
        ProtocolError,
    ],
    Field(discriminator="type"),
]


def parse_protocol_line(
    line: str,
) -> (
    ProtocolHandshake
    | ProtocolHandshakeAck
    | ProtocolHeartbeat
    | ProtocolTelemetry
    | ProtocolCommand
    | ProtocolCommandAck
    | ProtocolCommandResult
    | ProtocolEmergencyStop
    | ProtocolError
):
    """Parse a single JSON Lines protocol message."""
    import json

    from pydantic import TypeAdapter, ValidationError

    data = json.loads(line)
    adapter: TypeAdapter[Any] = TypeAdapter(ProtocolMessage)
    try:
        return adapter.validate_python(data)
    except ValidationError as exc:
        raise ValueError(f"Malformed protocol message: {exc}") from exc
