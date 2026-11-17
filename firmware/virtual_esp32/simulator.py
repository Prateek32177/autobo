#!/usr/bin/env python3
"""Virtual ESP32 — protocol-level peer over a real serial/PTY endpoint.

Speaks the same JSON Lines protocol as firmware/esp32/src/main.cpp.
Connects to SerialHardwareAdapter / Esp32HardwareAdapter via a virtual serial pair.
Does NOT use MockHardwareAdapter.
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Any

# Allow importing contracts from the monorepo root when run as a script.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from contracts.protocol import (  # noqa: E402
    PROTOCOL_VERSION,
    AckStatus,
    ProtocolCommandAck,
    ProtocolCommandResult,
    ProtocolError,
    ProtocolHandshake,
    ProtocolHandshakeAck,
    ProtocolHeartbeat,
    ProtocolTelemetry,
    ResultStatus,
    parse_protocol_line,
)
from contracts.protocol.messages import ProtocolCapabilityInfo, ProtocolComponentInfo  # noqa: E402

try:
    from .device_state import COMPONENTS, SUPPORTED_ACTIONS, DeviceState
    from .scenarios import Scenario, ScenarioConfig
except ImportError:  # running as `python simulator.py`
    from device_state import COMPONENTS, SUPPORTED_ACTIONS, DeviceState
    from scenarios import Scenario, ScenarioConfig

logger = logging.getLogger("virtual_esp32")


class VirtualEsp32:
    def __init__(self, port: str, *, baud: int = 115200, config: ScenarioConfig | None = None) -> None:
        self.port = port
        self.baud = baud
        self.config = config or ScenarioConfig()
        self.state = DeviceState(
            battery_voltage=self.config.battery_voltage,
            distance_cm=self.config.distance_cm,
        )
        self.config.apply_to_state(self.state)
        self._serial = None
        self._running = False
        self._started_at = time.monotonic()
        self._last_heartbeat_at = 0.0
        self._malformed_emitted = False
        self._suppress_outbound = False
        self._drop_results = self.config.scenario == Scenario.COMMAND_TIMEOUT
        self._ignore_host = False
        self._handshake_acked = False

    def open(self) -> None:
        import serial

        self._serial = serial.Serial(self.port, self.baud, timeout=0.05)
        self._running = True
        self._started_at = time.monotonic()
        self.state.started_monotonic = self._started_at
        self.state.touch_host()
        logger.info("Virtual ESP32 opened %s @ %s baud (scenario=%s)", self.port, self.baud, self.config.scenario.value)
        self._send_handshake()
        if self.config.scenario != Scenario.HEARTBEAT_TIMEOUT:
            self._send_heartbeat()
            if self.config.scenario != Scenario.STALE_TELEMETRY:
                self._send_telemetry()

    def close(self) -> None:
        self._running = False
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:  # noqa: BLE001
                pass
            self._serial = None
        logger.info("Virtual ESP32 closed")

    def run(self) -> None:
        self.open()
        try:
            while self._running:
                self._poll_inbound()
                self._apply_scenario_clock()
                self.state.tick_timeouts(
                    motor_timeout_ms=self.config.motor_timeout_ms,
                    watchdog_ms=self.config.watchdog_ms,
                )
                self._maybe_emit_periodic()
                time.sleep(0.01)
        finally:
            self.close()

    # --- outbound ---

    def _write_line(self, payload: dict[str, Any] | str) -> None:
        if self._serial is None or self._suppress_outbound:
            return
        line = payload if isinstance(payload, str) else json.dumps(payload, separators=(",", ":"))
        data = (line.rstrip("\n") + "\n").encode("utf-8")
        self._serial.write(data)
        self._serial.flush()

    def _send_model(self, model: Any) -> None:
        self._write_line(json.loads(model.model_dump_json()))

    def _send_handshake(self) -> None:
        components = [
            ProtocolComponentInfo(key=k, component_type=t, name=n) for k, t, n in COMPONENTS
        ]
        capabilities = [
            ProtocolCapabilityInfo(name=action) for action in sorted(SUPPORTED_ACTIONS)
        ]
        self._send_model(
            ProtocolHandshake(
                device_id=self.state.device_id,
                manufacturer=self.state.manufacturer,
                board=self.state.board,
                model=self.state.model,
                firmware_version=self.state.firmware_version,
                protocol_version=self.state.protocol_version,
                supported_components=components,
                supported_capabilities=capabilities,
            )
        )

    def _send_heartbeat(self) -> None:
        self._send_model(
            ProtocolHeartbeat(
                device_id=self.state.device_id,
                firmware_version=self.state.firmware_version,
                uptime_ms=self.state.uptime_ms(),
                protocol_version=PROTOCOL_VERSION,
            )
        )
        self._last_heartbeat_at = time.monotonic()

    def _send_telemetry(self) -> None:
        distance = self.state.effective_distance()
        # Contracts require a float; sensor failure uses an out-of-range sentinel
        # that diagnostics can treat as invalid (-1).
        distance_value = -1.0 if distance is None else float(distance)
        self._send_model(
            ProtocolTelemetry(
                device_id=self.state.device_id,
                timestamp_ms=self.state.uptime_ms(),
                battery_voltage=self.state.battery_voltage,
                distance_cm=distance_value,
                left_encoder=self.state.left_encoder,
                right_encoder=self.state.right_encoder,
                motor_status={
                    "left": self.state.left_motor,
                    "right": self.state.right_motor,
                },
                uptime_ms=self.state.uptime_ms(),
                firmware_version=self.state.firmware_version,
                emergency_stopped=self.state.emergency_stopped,
            )
        )

    # --- inbound ---

    def _poll_inbound(self) -> None:
        if self._serial is None:
            return
        raw = self._serial.readline()
        if not raw:
            return
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        if not line:
            return
        self._handle_line(line)

    def _handle_line(self, line: str) -> None:
        if self._ignore_host:
            return
        try:
            message = parse_protocol_line(line)
        except (ValueError, json.JSONDecodeError):
            # Malformed input must NOT keep the watchdog alive.
            if self.config.malformed_keeps_watchdog_alive:
                self.state.touch_host()
            self._send_model(
                ProtocolError(code="MALFORMED_MESSAGE", message="Invalid JSON line")
            )
            return

        # Only well-formed protocol messages refresh the host watchdog.
        self.state.touch_host()

        msg_type = getattr(message, "type", None)
        if msg_type == "handshake_ack":
            assert isinstance(message, ProtocolHandshakeAck)
            if message.status == "rejected":
                logger.warning("Host rejected handshake: %s", message.reason)
                self._handshake_acked = False
            else:
                self._handshake_acked = True
            return
        if msg_type == "emergency_stop":
            self._handle_emergency_stop(getattr(message, "command_id", None), getattr(message, "reason", "operator"))
            return
        if msg_type == "command":
            self._handle_command(message)
            return

    def _handle_emergency_stop(self, command_id: str | None, reason: str) -> None:
        self.state.stop_motors(emergency=True)
        if command_id:
            self._send_model(
                ProtocolCommandAck(command_id=command_id, status=AckStatus.ACCEPTED)
            )
            if not self._drop_results:
                self._send_model(
                    ProtocolCommandResult(
                        command_id=command_id,
                        status=ResultStatus.COMPLETED,
                        left_encoder_delta=0,
                        right_encoder_delta=0,
                        message=f"emergency_stop:{reason}",
                    )
                )
        self._send_telemetry()

    def _handle_command(self, message: Any) -> None:
        command_id = message.command_id
        action = message.action.value if hasattr(message.action, "value") else str(message.action)
        params = message.parameters or {}

        if action not in SUPPORTED_ACTIONS:
            self._send_model(
                ProtocolCommandAck(
                    command_id=command_id,
                    status=AckStatus.REJECTED,
                    reason=f"unsupported action: {action}",
                )
            )
            if not self._drop_results:
                self._send_model(
                    ProtocolCommandResult(
                        command_id=command_id,
                        status=ResultStatus.FAILED,
                        message=f"unsupported action: {action}",
                    )
                )
            return

        if self.state.emergency_stopped and action not in {"stop", "emergency_stop", "read_distance", "read_battery", "read_encoders"}:
            self._send_model(
                ProtocolCommandAck(
                    command_id=command_id,
                    status=AckStatus.REJECTED,
                    reason="emergency stop latch active",
                )
            )
            if not self._drop_results:
                self._send_model(
                    ProtocolCommandResult(
                        command_id=command_id,
                        status=ResultStatus.FAILED,
                        message="emergency stop latch active",
                    )
                )
            return

        self._send_model(ProtocolCommandAck(command_id=command_id, status=AckStatus.ACCEPTED))

        if self._drop_results:
            return

        if action == "stop":
            # Explicit stop is the operator reset: clear latch and idle motors.
            self.state.clear_emergency()
            self.state.stop_motors(emergency=False)
            self._send_model(
                ProtocolCommandResult(
                    command_id=command_id,
                    status=ResultStatus.COMPLETED,
                    left_encoder_delta=0,
                    right_encoder_delta=0,
                    message="stop:latch_cleared",
                )
            )
            self._send_telemetry()
            return
        if action == "emergency_stop":
            self.state.stop_motors(emergency=True)
            self._send_model(
                ProtocolCommandResult(
                    command_id=command_id,
                    status=ResultStatus.COMPLETED,
                    left_encoder_delta=0,
                    right_encoder_delta=0,
                )
            )
            self._send_telemetry()
            return

        if action == "read_distance":
            distance = self.state.effective_distance()
            self._send_model(
                ProtocolCommandResult(
                    command_id=command_id,
                    status=ResultStatus.COMPLETED if distance is not None else ResultStatus.FAILED,
                    distance_cm=distance if distance is not None else None,
                    message=None if distance is not None else "sensor failure",
                )
            )
            return

        if action == "read_battery":
            self._send_model(
                ProtocolCommandResult(
                    command_id=command_id,
                    status=ResultStatus.COMPLETED,
                    battery_voltage=self.state.battery_voltage,
                )
            )
            return

        if action == "read_encoders":
            self._send_model(
                ProtocolCommandResult(
                    command_id=command_id,
                    status=ResultStatus.COMPLETED,
                    left_encoder_delta=0,
                    right_encoder_delta=0,
                    message=f"left={self.state.left_encoder},right={self.state.right_encoder}",
                )
            )
            return

        speed = float(params.get("speed", 0.15))
        duration_ms = int(params.get("duration_ms", 500))
        left_delta, right_delta = self.state.apply_motion(action, speed, duration_ms)
        # Simulate motion duration without blocking host reads entirely.
        end = time.monotonic() + (min(duration_ms, self.config.motor_timeout_ms) / 1000.0)
        while time.monotonic() < end and self._running:
            self._poll_inbound()
            time.sleep(0.01)
        self.state.stop_motors()
        self._send_model(
            ProtocolCommandResult(
                command_id=command_id,
                status=ResultStatus.COMPLETED,
                left_encoder_delta=left_delta,
                right_encoder_delta=right_delta,
            )
        )

    # --- scenarios / periodic ---

    def _apply_scenario_clock(self) -> None:
        elapsed = time.monotonic() - self._started_at
        scenario = self.config.scenario
        if elapsed < self.config.delay_before_fault_s:
            return

        if scenario == Scenario.HOST_DISCONNECT:
            self._ignore_host = True
        elif scenario == Scenario.DEVICE_DISCONNECT:
            logger.warning("Scenario device_disconnect — closing port")
            self._running = False
        elif scenario == Scenario.HEARTBEAT_TIMEOUT:
            self._suppress_outbound = True
        elif scenario == Scenario.MALFORMED_JSON and not self._malformed_emitted:
            self._write_line("not-json{{{")
            self._malformed_emitted = True

    def _maybe_emit_periodic(self) -> None:
        if self._suppress_outbound:
            return
        now = time.monotonic()
        if now - self._last_heartbeat_at < self.config.heartbeat_interval_s:
            return
        if self.config.scenario == Scenario.HEARTBEAT_TIMEOUT:
            return
        # If the host went silent (closed serial), require a fresh handshake.
        if self.state.host_silent_ms() > max(2000, self.config.watchdog_ms // 2):
            self._handshake_acked = False
        if not self._handshake_acked:
            self._send_handshake()
        self._send_heartbeat()
        if self.config.scenario != Scenario.STALE_TELEMETRY:
            self._send_telemetry()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Virtual ESP32 protocol simulator")
    parser.add_argument("--port", required=True, help="Serial/PTY device path (simulator end)")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument(
        "--scenario",
        default=Scenario.NORMAL.value,
        choices=[s.value for s in Scenario],
        help="Behaviour / failure scenario",
    )
    parser.add_argument("--battery-voltage", type=float, default=None)
    parser.add_argument("--distance-cm", type=float, default=None)
    parser.add_argument("--delay-before-fault-s", type=float, default=None)
    parser.add_argument("--heartbeat-interval-s", type=float, default=None)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--daemon", action="store_true", help="Double-fork into background")
    parser.add_argument("--pid-file", default="", help="Write daemon PID here")
    parser.add_argument("--log-file", default="", help="Append logs when daemonizing")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.daemon:
        if not args.pid_file:
            print("--pid-file is required with --daemon", file=sys.stderr)
            return 2
        try:
            from .daemonize import daemonize
        except ImportError:
            from daemonize import daemonize

        daemonize(
            pid_file=args.pid_file,
            stdout=args.log_file or None,
            stderr=args.log_file or None,
        )

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    overrides = {
        "battery_voltage": args.battery_voltage,
        "distance_cm": args.distance_cm,
        "delay_before_fault_s": args.delay_before_fault_s,
        "heartbeat_interval_s": args.heartbeat_interval_s,
    }
    config = ScenarioConfig.from_name(args.scenario, **overrides)
    sim = VirtualEsp32(args.port, baud=args.baud, config=config)

    def _stop(*_args: object) -> None:
        sim._running = False

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    sim.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
