---
id: mav-component
title: "Your own MAVLink component: sensor, parameters, messages"
level: L3
readingTime: 45 min
firmware: ArduPilot 4.7 (checked against 4.7.3) · PX4 1.18 (checked against v1.18.0) · MAVLink 2
status: published
added: 2026-11-08
tags:
  - MAVLink
  - component
  - DISTANCE_SENSOR
  - ESP32
  - parameters
related:
  - mav-routing
  - comp-esp32
  - est-alt-sources
next:
  - mav-sdk
source: content/companion/mav-component.md
source_hash: 10aaf8b2314e
---

## summary
So far the companion has been a client: it read telemetry and sent commands. Here it becomes a **participant in the system**: a component with its own compid, heartbeat, parameters, and messages that the autopilot uses as sensor data. This is how rangefinders, obstacle sensors, external navigation, gimbals, and payloads connect to ArduPilot and PX4. The module covers a component's duties (heartbeat, answering requests, parameters), sensor messages (`DISTANCE_SENSOR`, `OBSTACLE_DISTANCE`, `ODOMETRY`/`VISION_POSITION_ESTIMATE`), debug messages (`NAMED_VALUE_*`, `DEBUG_VECT`), and two implementations: Python on a companion and C on an ESP32. Lab: a virtual rangefinder that ArduPilot SITL accepts as `RNGFND1`, then the same component on an ESP32.

## theory
### What makes a component "well-behaved"
1. **Heartbeat** at 1 Hz with its own `MAV_TYPE` (for a sensor, `MAV_TYPE_GENERIC` or a specific one), `MAV_AUTOPILOT_INVALID` (it is not an autopilot!), the sysid of its system (the same vehicle), and a unique compid. Without a heartbeat, routing to the component does not work (the mav-routing module).
2. **Answers requests addressed to it**: a `COMMAND_LONG` with its compid → a `COMMAND_ACK` (even UNSUPPORTED is better than silence, which leaves the client hanging until its timeout); `MAV_CMD_REQUEST_MESSAGE` for a `COMPONENT_INFORMATION`/`AUTOPILOT_VERSION`-style description, where possible.
3. **Its own parameters**, if it needs them, over the parameter protocol: it answers `PARAM_REQUEST_LIST`/`PARAM_REQUEST_READ`/`PARAM_SET` from the GCS addressed to its compid, and stores the values in non-volatile memory. QGC and Mission Planner show them in a separate group for the component.
4. **Does not duplicate other components' messages** and does not send the autopilot commands that conflict with the operator.
5. **Degrades honestly**: when it loses measurements, it stops sending the message (or flags it as invalid) instead of repeating the last value. The autopilot detects the timeout and disables the source.

### Distance sensor: DISTANCE_SENSOR (132)
Fields: `time_boot_ms`, `min_distance`/`max_distance`/`current_distance` in **centimeters**, `type` (`MAV_DISTANCE_SENSOR_LASER`, `_ULTRASOUND`, `_RADAR`…), `id`, `orientation` (`MAV_SENSOR_ROTATION_PITCH_270` = down, `_NONE` = forward…), `covariance` (255: unknown), and in the extension fields `horizontal_fov`, `vertical_fov`, `quaternion`, `signal_quality` (0: unknown, 1: invalid signal … 100: perfect).

ArduPilot: `RNGFND1_TYPE = 10` (MAVLink), `RNGFND1_ORIENT = 25` (down), `RNGFND1_MIN`/`RNGFND1_MAX` (meters; before 4.7, `RNGFND1_MIN_CM`/`RNGFND1_MAX_CM` in centimeters). The autopilot treats values outside [min, max] as "out of range", not as a measurement. Rate: 10–50 Hz; ArduPilot's MAVLink rangefinder timeout is 500 ms: if packets arrive slower than ~2 Hz or with gaps longer than 0.5 s, the sensor is considered lost. A downward rangefinder is used for height above ground (`RFND` in the log, the EKF POSZ source = rangefinder, landing, terrain following); sensors in other orientations are used for obstacle avoidance (`PRX` proximity, `PRX1_TYPE = 2` MAVLink).

{{diagram:mav-rangefinder-timeout|The 0.5 s timeout only works for an honest component: a sensor that goes silent is dropped after 0.5 s, one that repeats its last value is never dropped, and a pause longer than 0.5 s causes "flickering".}}

### Obstacles and external navigation
- `OBSTACLE_DISTANCE` (330): an array of 72 distances by sector (`increment` degrees per sector, `angle_offset`), for 2D lidars and stereo cameras → proximity in ArduPilot (`PRX1_TYPE = 2`), collision prevention in PX4.
- `VISION_POSITION_ESTIMATE` (102), `VISION_SPEED_ESTIMATE` (103), `ODOMETRY` (331): pose/velocity from VIO or motion capture → the ArduPilot EKF as ExternalNav (`EK3_SRC1_POSXY = 6`), PX4 as external vision (`EKF2_EV_CTRL`). Time matters here (`usec` timestamps, TIMESYNC), and so do coordinate frames (FRD/NED vs FLU/ENU: the math-linalg-rot module).

### Debug messages
To show your own value in the GCS and in the log without a dialect of your own: `NAMED_VALUE_FLOAT` (251), a name of up to 10 characters and a float; `NAMED_VALUE_INT` (252); `DEBUG_VECT` (250), a name and three floats. Mission Planner shows them in the Quick tab and graphs, ArduPilot writes received `NAMED_VALUE_FLOAT` messages to the log (`NVAL`), PX4 writes them to the ulog as debug topics. For a permanent integration, use your own dialect (the mav-protocol module) or `TUNNEL` (385).

### A Python implementation
`examples/mavlink/virtual_rangefinder.py` is a complete component: its own compid (`MAV_COMP_ID_PERIPHERAL`), a heartbeat, reading `GLOBAL_POSITION_INT` to simulate a measurement, publishing `DISTANCE_SENSOR` at a set rate, range clamping. The structure (polling, sending at a fixed rate, the heartbeat separately) is the same for any sensor: replace `measurement_cm()` with reading a real lidar over UART/I2C, and you have a working driver.

### An ESP32 implementation (C)
On a microcontroller you use a generated C library (the header-only `c_library_v2` or your own from mavgen):

```c
#include <common/mavlink.h>

static void send_distance(uart_port_t uart, uint16_t dist_cm) {
    mavlink_message_t msg;
    uint8_t buf[MAVLINK_MAX_PACKET_LEN];
    mavlink_msg_distance_sensor_pack(1, MAV_COMP_ID_PERIPHERAL, &msg,
        esp_timer_get_time() / 1000, 20, 4000, dist_cm,
        MAV_DISTANCE_SENSOR_LASER, 0, MAV_SENSOR_ROTATION_PITCH_270, 255,
        0, 0, NULL, 0);                                   /* fovs, quaternion, signal_quality: extensions */
    uint16_t len = mavlink_msg_to_send_buffer(buf, &msg);
    uart_write_bytes(uart, (const char *)buf, len);
}
```

Receiving is byte by byte with `mavlink_parse_char(chan, byte, &msg, &status)` in the task that reads the UART. A separate FreeRTOS task sends the heartbeat once a second; sending from several tasks needs a mutex, or frames get interleaved on the UART. The ESP-IDF and UART details are in the comp-esp32 module.

### Testing a component
A component is tested at three levels: (1) unit, the measurement/packing function (`test_component.py`, range clamping); (2) integration with a fake vehicle, checking the message arrives with the right compid and orientation; (3) SITL, checking the autopilot actually uses the data (`RFND.Dist` in the log matches what you sent, `RNGFND1` shows healthy in the status). Only the third level proves that the autopilot parameters and the message agree.

{{diagram:mav-component-seq|The minimum for a "well-behaved" component: a HEARTBEAT with its own compid, the sensor data, parameters on request, and an answer to every command.}}

### Where it fits in the system

- **Takes in:** its own sensor's measurement over UART or I2C (`emb-protocols`); a route to itself, only after its own heartbeat (`mav-routing`); the receiving parameters in the autopilot (`RNGFND1_TYPE`, `PRX1_TYPE`).
- **Puts out:** `DISTANCE_SENSOR`, height above ground for the EKF and landing (`est-alt-sources`); `OBSTACLE_DISTANCE` for obstacle avoidance (`per-depth-avoid`); `ODOMETRY` for external navigation (`per-visual-nav`).
- **If you get this wrong:** when measurements are lost, the component keeps sending the last value → the autopilot sees no timeout and holds altitude on a dead rangefinder; height sources are covered in `est-alt-sources`. Centimeters mixed up with meters, or the wrong orientation → values outside [min, max] count as "out of range", and `RFND.Dist` in the log does not match what was sent (`est-alt-sources`).

## practice
### Step 1. Component tests
```bash
cd examples/mavlink
python -m pytest -q tests/test_component.py
```
Read what the tests check: the sender's compid, the orientation, the value range.

### Step 2. ArduPilot SITL accepts the rangefinder
Start SITL (the ap-sitl module), set `RNGFND1_TYPE = 10`, `RNGFND1_ORIENT = 25`, `RNGFND1_MAX = 40` (`RNGFND1_MAX_CM = 4000` on 4.6 and earlier), and reboot. Run `virtual_rangefinder.py --master udpin:0.0.0.0:14551` (the script listens on a separate SITL/router output, `--out=udp:127.0.0.1:14551`, and replies to the address the stream came from). Take off to 10 m: in Mission Planner `rangefinder1` shows ~10 m minus the "terrain", and the log has `RFND`. Stop the script: within a few hundred milliseconds the autopilot should stop treating the rangefinder as healthy.

### Step 3. A component parameter
Give the component a parameter `RF_OFFSET_CM` (the mounting offset): answers to `PARAM_REQUEST_LIST`/`READ`/`SET` for its own compid, storage in a JSON file. Check that QGC shows it in the component's group and that changing it from QGC changes `DISTANCE_SENSOR` right away. Note: by the MAVLink definition, `MAV_COMP_ID_PERIPHERAL` (158) is for devices without a parameter service; once the component has parameters, give it another free compid (for example `MAV_COMP_ID_USER1`…, or `MAV_COMP_ID_ONBOARD_COMPUTER2` (192) on a companion).

### Step 4. ESP32
Port the component to an ESP32: a UART to the SITL TELEM port through a USB-UART adapter (or to a real FC), heartbeat + `DISTANCE_SENSOR` with a sine wave instead of a sensor; then connect a real rangefinder (a VL53L1X over I2C or a TFmini over UART). Compare `RFND` in the log with the readings.

Self-check: the lab is done when the `tests/test_component.py` tests pass, SITL uses the virtual rangefinder (at 10 m `rangefinder1` shows ~10 m minus the "terrain", the log has `RFND`, and after the script stops, the autopilot stops treating the rangefinder as healthy within a few hundred milliseconds), the `RF_OFFSET_CM` parameter shows in QGC in the component's group and changing it changes `DISTANCE_SENSOR` right away, and there is an ESP32 version, at least with synthetic data, whose sine wave shows in `RFND`.

## diagnostics
- **Symptom:** SITL does not see the rangefinder even though packets are flowing
  - Possible cause: no reboot after `RNGFND1_TYPE`; the orientation does not match `RNGFND1_ORIENT`; values outside min/max.
  - What to do: reboot; ORIENT 25 ↔ PITCH_270; check the units (cm vs m).
- **Symptom:** the rangefinder "flickers" between healthy and unhealthy
  - Possible cause: a low or unsteady send rate (a sleep in the receive loop).
  - What to do: send on a timer at ≥ 10 Hz; make receiving non-blocking.
- **Symptom:** QGC does not show the component's parameters
  - Possible cause: no heartbeat from the component, or the replies go out with the autopilot's compid.
  - What to do: send a heartbeat; reply with your own compid and honor target_component in the request.
- **Symptom:** "broken" frames arrive from the ESP32 from time to time
  - Possible cause: two tasks writing to the UART at the same time.
  - What to do: a single sender task with a queue, or a mutex on the UART.

## references
- MAVLink — DISTANCE_SENSOR, OBSTACLE_DISTANCE, ODOMETRY (common.xml) | https://mavlink.io/en/messages/common.html | primary | A
- ArduPilot — Rangefinder parameters (RNGFND1_TYPE 10: MAVLink) | https://ardupilot.org/copter/docs/common-rangefinder-landingpage.html | primary | A
- ArduPilot — AP_RangeFinder (source) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/AP_RangeFinder | primary | A
- MAVLink — c_library_v2 (generated C headers) | https://github.com/mavlink/c_library_v2 | primary | A
- PX4 — Distance sensors and MAVLink | https://docs.px4.io/v1.17/en/sensor/rangefinders.html | primary | A

## checklist
- I know a component's duties: heartbeat, answers, its own parameters, honest degradation
- I fill in DISTANCE_SENSOR correctly (units, orientation, range)
- I set up ArduPilot for a MAVLink rangefinder and verify it in the log
- I use NAMED_VALUE_* for quick debugging
- I implement a component in Python and on an ESP32 (mavlink_parse_char, mutex)
- I test at three levels: unit, fake vehicle, SITL
