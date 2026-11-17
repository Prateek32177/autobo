# Hardware setup

## Start without hardware

The application starts in **simulation** by default. No ESP32 is required.

```bash
./scripts/setup.sh
./scripts/start.sh
```

## Milestone 2 preparation (ESP32)

When you are ready to test physical hardware:

### Dependencies

- `pyserial` (installed with the runtime)
- PlatformIO CLI (for build/upload)
- USB serial permission on your OS (macOS: usually automatic; Linux: dialout group)

### Firmware

```bash
cd firmware/esp32
pio run
pio run -t upload
pio device monitor -b 115200
```

Protocol: [firmware_protocol.md](firmware_protocol.md)

### Runtime connection (when board is attached)

1. `GET /api/hardware/ports` or dashboard Settings → serial port count / note.
2. Register a device with `connection.type=serial` and the listed port.
3. `POST /api/hardware/connect` with that `device_id`.

The app must still start if no ports exist.

## Planned hardware bill of materials

- ESP32 development board
- Dual DC geared motors + driver
- Wheel encoders
- Distance sensor
- Battery voltage measurement
- Laptop webcam (camera)
- Physical power switch and emergency stop

Do not purchase a Raspberry Pi until the laptop + ESP32 loop is validated.
