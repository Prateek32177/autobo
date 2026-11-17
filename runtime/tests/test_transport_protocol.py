"""Transport independence and protocol session tests."""

from __future__ import annotations

import asyncio

import pytest

from contracts.protocol import (
    PROTOCOL_VERSION,
    ProtocolCommand,
    ProtocolHandshake,
    ResultStatus,
    parse_protocol_line,
)
from physical_ai.hardware.protocol.session import ProtocolSession, ProtocolSessionError
from physical_ai.hardware.sim_peer import SimulatedEsp32Peer
from physical_ai.hardware.transport.memory import MemoryTransport


@pytest.mark.asyncio
async def test_memory_transport_can_be_swapped_for_session() -> None:
    host, peer = MemoryTransport.pair()
    await host.connect()
    await peer.connect()

    await peer.write_line('{"type":"heartbeat","device_id":"d","firmware_version":"1","uptime_ms":1}')
    line = await host.read_line(timeout=1.0)
    msg = parse_protocol_line(line)
    assert msg.type == "heartbeat"


@pytest.mark.asyncio
async def test_protocol_handshake_and_command_correlation() -> None:
    host_t, peer_t = MemoryTransport.pair()
    peer = SimulatedEsp32Peer(peer_t, device_id="rover-x", interval_seconds=0.05)
    session = ProtocolSession(host_t, command_timeout=2.0, read_timeout=0.1)

    telemetries: list = []
    session.on_telemetry(lambda m: telemetries.append(m) or asyncio.sleep(0))

    await peer.start()
    await session.start()
    hs = await session.perform_handshake(timeout=2.0)
    assert isinstance(hs, ProtocolHandshake)
    assert hs.protocol_version == PROTOCOL_VERSION
    assert hs.device_id == "rover-x"

    result = await session.send_command(
        ProtocolCommand(
            command_id="cmd-corr-1",
            action="move_forward",
            parameters={"speed": 0.2, "duration_ms": 100},
        )
    )
    assert result.status == ResultStatus.COMPLETED
    assert result.command_id == "cmd-corr-1"
    assert result.left_encoder_delta and result.left_encoder_delta > 0

    await asyncio.sleep(0.12)
    assert len(telemetries) >= 1

    await session.stop()
    await peer.stop()


@pytest.mark.asyncio
async def test_malformed_messages_are_ignored_safely() -> None:
    host_t, peer_t = MemoryTransport.pair()
    await host_t.connect()
    await peer_t.connect()
    session = ProtocolSession(host_t, read_timeout=0.05)
    malformed: list[str] = []

    async def on_bad(line: str, exc: Exception) -> None:
        malformed.append(line)

    session.on_malformed(on_bad)
    await session.start()
    await peer_t.write_line("not-json{{{")
    await peer_t.write_line(
        '{"type":"heartbeat","device_id":"d","firmware_version":"1","uptime_ms":2}'
    )
    await asyncio.sleep(0.15)
    assert len(malformed) >= 1
    await session.stop()


@pytest.mark.asyncio
async def test_protocol_version_mismatch_rejected() -> None:
    host_t, peer_t = MemoryTransport.pair()
    await host_t.connect()
    await peer_t.connect()
    session = ProtocolSession(host_t, expected_protocol_version="1.0", read_timeout=0.05)
    await session.start()
    await peer_t.write_line(
        '{"type":"handshake","device_id":"d","firmware_version":"1",'
        '"protocol_version":"9.9","manufacturer":"x","board":"y","model":"z"}'
    )
    with pytest.raises(ProtocolSessionError):
        await session.perform_handshake(timeout=1.0)
    await session.stop()
