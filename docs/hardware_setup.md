# Hardware setup

## Milestone 1

No physical hardware is required. The runtime seeds a **simulated** rover:

- Device ID: `rover-sim-001`
- Connection type: `simulation`
- Components: ESP32 controller, distance sensor, left/right motors, encoders, battery

## Milestone 2+ (preview)

Planned initial rover stack:

- ESP32 development board
- Dual DC geared motors + compatible motor driver
- Wheel encoders
- Distance sensor
- Battery voltage measurement
- Laptop webcam (camera)
- Physical power switch and emergency stop

USB serial at **115200** baud using the JSON Lines protocol documented in [firmware_protocol.md](firmware_protocol.md).

Do not purchase a Raspberry Pi until the laptop + ESP32 loop is validated.
