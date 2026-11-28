---
id: ap-companion
title: "Companion + ArduPilot: control from code"
level: L3
readingTime: 50 min
firmware: ArduPilot 4.7 (checked against 4.7.3; the lab uses Copter SITL 4.7.2 + MAVProxy 1.8.75 + pymavlink 2.4.50)
status: published
added: 2026-11-07
tags:
  - GUIDED
  - offboard
  - pymavlink
  - SERIAL
  - routing
related:
  - comp-raspberry
  - ap-missions
  - mav-routing
  - mav-sdk
next:
  - bf-custom
source: content/ardupilot/ap-companion.md
source_hash: 353b0e3c7668
---

## summary
GUIDED mode is the door through which a companion computer controls the vehicle: "fly to this point", "hold this velocity", "look over there". This module shows how to set position and velocity targets from Python on a companion, how ArduPilot protects itself from a companion that has gone silent or gone haywire, and how to build a control loop that you can debug safely in SITL. Before that comes the wire: which FC port to give the companion, which `SERIALn_*` parameters to set, which parameters were renamed in 4.7.2 (`SRn_*` → `MAVn_*`, `SYSID_THISMAV` → `MAV_SYSID`), why ArduCopter 4.7 sends a companion no telemetry by default, and which participant on the network counts as the ground station for the failsafe. The lab was run on ArduCopter 4.7.2 SITL through a MAVProxy router: a parameter audit, a GUIDED arm and takeoff with COMMAND_ACK checks, a stream of velocity targets, a measurement of the stop after the companion goes silent (the drop starts after 3.2–3.3 s, and the stop at < 0.2 m/s comes after 4.3 s), and the pilot taking over control. The result is a framework for the track's capstone: your own logic on board.

## theory
### The companion ↔ FC link: port, protocol, baud rate
A companion is connected to a free telemetry UART of the flight controller (usually TELEM2 = `SERIAL2`; the FC's USB is left for configuration). On the FC side there are three port settings: the protocol `SERIALn_PROTOCOL = 2` (MAVLink2; 1 is MAVLink1, 45 is DDS XRCE for ROS 2), the baud rate `SERIALn_BAUD`, and hardware flow control `BRD_SERn_RTSCTS`. The baud rate is set as a code, not as a baud number: 57 = 57600, 115 = 115200, 460 = 460800, 921 = 921600, 1500 = 1.5 Mbaud (`AP_SerialManager.cpp`, the `@Values` of `SERIAL1_BAUD`). The 4.7.2 defaults for `SERIAL1` and `SERIAL2` are MAVLink2 at 57 (`AP_SerialManager.cpp:47–64`, confirmed by the parameter audit in SITL). For a companion 57600 is too slow, and the arithmetic shows it.

An 8N1 UART sends 10 bits per byte, so 921600 baud is 92 160 bytes/s and 57600 baud is 5 760 bytes/s. A MAVLink2 frame adds 12 bytes to the payload (a 10-byte header and a 2-byte CRC; a signature adds another 13). LOCAL_POSITION_NED and ATTITUDE each carry 28 bytes of payload, so up to 40 bytes each on the wire. A companion that needs position and attitude at 50 Hz each for a tracking loop takes 2 × 50 × 40 = 4000 bytes/s: that is 69% of a 57600 link and 4.3% of a 921600 link. At 57600 the GCS stream through the router, parameters, and missions come on top of that, the link overflows, messages start getting lost, and the failure looks like "random timeouts" in the code. A course guideline: 921 for a companion on a short wire (up to ~30 cm), link load no higher than 50%, and 1500 only with `BRD_SERn_RTSCTS = 1` and a check for losses.

Flow control: `BRD_SER1_RTSCTS` is 0 Disabled, 1 Enabled, 2 Auto, and 3 uses the RTS pin as an RS-485 driver enable; `BRD_SER1_RTSCTS`…`BRD_SER3_RTSCTS` default to 2, Auto (`AP_BoardConfig.cpp`); the parameter does not exist if the port has no RTS/CTS lines on that board (`HAL_HAVE_RTSCTS_SERIALn`). If the RTS/CTS lines are not wired to the companion, set 0 explicitly so you do not depend on auto-detection. UART levels are 3.3 V on the FC and on a Raspberry Pi; the ground is shared, and the wiring is FC TX → companion RX and the other way around.

In 4.7 two bits of `SERIALn_OPTIONS` moved to `MAVn_OPTIONS`: "don't forward mavlink to/from this port" (it was bit 10, now bit 1) and "ignore stream rate requests" (it was bit 12, now bit 2); bit 0 of `MAVn_OPTIONS` accepts unsigned MAVLink2 messages (`GCS_MAVLink_Parameters.cpp`, the `@Bitmask` of `_OPTIONS`). The conversion on update is done once (the hidden `MAVn_OPTIONSCNV`).

{{lesson:comp-raspberry|The Raspberry Pi UART, the mavlink-router configuration, the power budget, and a systemd watchdog: the companion side of the same wire.}}

### MAVn channels and telemetry streams in 4.7
In 4.7 the MAVLink channel parameters are collected in the `MAV` group: `MAV1_*`, `MAV2_*` …, one block per channel. The channel number is not the `SERIALn` number: channel 1 is the console (`SERIAL0`, USB), and after that channels are handed to the ports with a MAVLink protocol in order of their numbers (a conclusion from the code: the console in `GCS::setup_console`, `GCS_Common.cpp:2808–2819`; the rest in `GCS::setup_uarts`, `GCS_Common.cpp:2844–2853`). If MAVLink is on `SERIAL0`, `SERIAL1`, and `SERIAL2`, a companion on `SERIAL2` is `MAV3_*`; if you switch `SERIAL1` to GPS, the same wire becomes `MAV2_*`.

Each block holds the rates of the stream groups `_RAW_SENS`, `_EXT_STAT`, `_RC_CHAN`, `_RAW_CTRL`, `_POSITION`, `_EXTRA1`, `_EXTRA2`, `_EXTRA3`, `_PARAMS`, `_ADSB` (before 4.7, `SR0_*` … `SR6_*`, numbered from zero). On Copter every default is 0 (the `APM_BUILD_COPTER_OR_HELI` block in `GCS_MAVLink_Parameters.cpp`), on Plane they are mostly 1 Hz (PARAMS 10, ADSB 5), and on Sub 2…10 Hz for the main groups (RAW_CTRL, PARAMS, ADSB are 0). The SITL 4.7.2 audit confirms it: `MAV1_EXT_STAT = 0`, `MAV2_POSITION = 0`, while `SR0_EXT_STAT` and `SYSID_THISMAV` answer "no such parameter". The practical conclusion: a companion that silently listens to an ArduCopter 4.7 port gets neither position nor mode beyond HEARTBEAT. The options: (a) request the messages you need with `MAV_CMD_SET_MESSAGE_INTERVAL` (511) after connecting; the request applies to the channel it arrived on and lasts until a reboot; (b) set `MAVn_*` for your channel (these require a reboot); (c) get the stream through a router for which the ground station has already requested it, but then the GCS decides the rates, not your loop.

### Who is who: sysid, compid, and the GCS failsafe
A companion is part of the vehicle: the same sysid as the autopilot (`MAV_SYSID`, before 4.7 `SYSID_THISMAV`, default 1) and its own compid, by convention 191 (`MAV_COMP_ID_ONBOARD_COMPUTER`). ArduPilot always accepts packets from its own components (`GCS_Common.cpp:7181`, "accept packets from our own components (e.g. mavlink-connected companion computers)"); it also accepts them from other sysids as long as bit 0 of `MAV_OPTIONS` (accept MAVLink only from `MAV_GCS_SYSID…_HI`) is not set; with it set, a companion on the vehicle's sysid is still admitted. For ArduPilot the ground station is whoever has a sysid within the range `MAV_GCS_SYSID`…`MAV_GCS_SYSID_HI` (before 4.7, `SYSID_MYGCS`, default 255). Three things depend on that:

- The companion's HEARTBEAT does **not** refresh the GCS failsafe timer: only packets from the ground station's sysid reset it, namely HEARTBEAT and also RC_CHANNELS_OVERRIDE and MANUAL_CONTROL (`GCS_Common.cpp:4342, 4224, 7456`). A companion cannot "keep the GCS failsafe alive", and it should not, otherwise a failure of the station's radio link would go unnoticed.
- `MANUAL_CONTROL` and `RC_CHANNELS_OVERRIDE` are accepted only from the station's sysid (`GCS_Common.cpp:4179, 7439`). A companion that wants to "fly the sticks" would have to pose as the station, which is a bad idea; GUIDED exists for control.
- `FS_GCS_ENABLE` (default 0, disabled; 1 is RTL, 5 is LAND, and so on) with the `FS_GCS_TIMEOUT` timeout (default 5 s, range 2–120 s) watches the station, not the companion. ArduCopter has no separate "companion failsafe": what protects you from a silent companion is `GUID_TIMEOUT` (only for velocity, acceleration, and angle targets) and the pilot.

### A router on the companion
The FC has one UART, and there are several consumers: your service, a ground station over Wi-Fi or 4G, tlog recording. Only the router (mavlink-router, MAVProxy, mavp2p) opens the `/dev/serial0` port, and the rest connect to it over UDP. In the lab MAVProxy 1.8.75 plays the router: `mavproxy.py --master=tcp:127.0.0.1:5840 --out=udp:127.0.0.1:14650 --out=udp:127.0.0.1:14651 --streamrate=-1 --daemon`, with one input from SITL and two UDP outputs (the companion and the "station"). Without `--streamrate=-1` MAVProxy requests its own streams at 4 Hz and by doing so resets the rates the companion set with `SET_MESSAGE_INTERVAL` (verified: 4.0–4.2 Hz instead of 10 Hz; with the flag, 10.0–10.2 Hz). On board the standard is mavlink-router as a systemd service (the configuration is in the comp-raspberry module; it was not run in this lab because it is not installed in the environment). A router forwards packets by the same sysid/compid rules as ArduPilot, so a script without its own HEARTBEAT may not receive the replies addressed to it. And one more reason to keep a router: SITL's TCP port (and a single `/dev/serial0`) accepts one client, and a second script gets silence.

{{lesson:mav-routing|Forwarding rules by sysid/compid, mavlink-router versus MAVProxy, UDP versus TCP, and measuring loss under netem.}}

### GUIDED and its timeouts
In GUIDED the vehicle waits for targets from an external source. The targets can be:

- **position**: `SET_POSITION_TARGET_GLOBAL_INT` (86) with coordinates, or `SET_POSITION_TARGET_LOCAL_NED` (84) in meters relative to home or to the vehicle;
- **velocity**: the same messages with a `type_mask` bitmask that says "ignore position, use velocity";
- **attitude/thrust**: `SET_ATTITUDE_TARGET`, for advanced cases.

What happens if the companion goes silent depends on the type of the last target (`ArduCopter/mode_guided.cpp`, 4.7.2; `get_timeout_ms()` = `GUID_TIMEOUT` × 1000, no less than 100 ms, and it is used "only for velocity, acceleration, angles, and angular rates", per the comment in the code):

- **position** (`pos_control_run`): there is no timeout: the vehicle flies to the last point and hovers there indefinitely; the timeout only stops a yaw rate rotation;
- **velocity, acceleration, velocity + acceleration** (`velaccel_control_run`, `accel_control_run`): after `GUID_TIMEOUT` the setpoints are zeroed: the vehicle brakes and hovers;
- **position + velocity + acceleration** (`posvelaccel_control_run`): velocity and acceleration are zeroed, and position is held;
- **angles and thrust** (`SET_ATTITUDE_TARGET`, `angle_control_run`): after `GUID_TIMEOUT` the lean angles → level with the previous heading, and the climb rate → 0.

`GUID_TIMEOUT` = 3.0 s by default, range 0.1–5 s (`ArduCopter/Parameters.cpp`, `guided_timeout`). A measurement in SITL (practice, step 3, telemetry at 10 Hz): with a 2 m/s target sent at 5 Hz, the speed holds at 1.98–1.99 m/s until 3.21 s after the last target, the first drop is visible at 3.31 s, and it is below 0.2 m/s at 4.32 s. This is protection you should rely on, not work around; and it is an argument for sending velocity targets from the companion, not position targets, wherever a companion failure must stop the vehicle.

{{diagram:guided-silence-tree|Only velocity, acceleration, and angle targets have a timeout: after a position target a silent companion leaves the vehicle flying to the point and hovering there.}}

### Coordinate frame
`LOCAL_NED`: X is north, Y is east, Z is **down**. A 10 m climb is Z = −10. Half of the mistakes in offboard code are the sign of the Z axis. For targets relative to the vehicle's nose there is `MAV_FRAME_BODY_OFFSET_NED`.

### What the FC checks
The geofence (`FENCE_*`), speed and acceleration limits (`WP_*`, before 4.7 `WPNAV_*`), the battery failsafe, EKF health. A companion can ask for anything, but execution still happens within the FC's parameters. Hence the debugging rule: if the vehicle "won't obey", first look at `STATUSTEXT`, then at the limit parameters, and only then at your own code.

### The control loop
A good companion loop:

1. Read the state (position, velocity, mode, arming) from telemetry at a set rate.
2. Compute the decision.
3. Send the target **regularly** (for example at 5–10 Hz for velocity), even if it has not changed.
4. Check that the mode is still GUIDED: the pilot can take control with a switch at any moment, and the code must respect that.

### Companion code as a state machine
A script that "sends a command, sleeps 10 seconds, sends the next one" works in SITL and breaks in the field: the command is not accepted, the pilot changed the mode, the GPS dropped out. The robust form is a state machine in which every transition checks a condition and has a timeout:

| State | What it does | Transition onward | If it fails |
|---|---|---|---|
| WAIT_READY | waits for a GPS fix and EKF OK in telemetry | ready | wait, send nothing |
| ARM_TAKEOFF | GUIDED, arm, `MAV_CMD_NAV_TAKEOFF`, waits for the ACK and an altitude ≥ 90% of the target | altitude reached | no altitude within 20 s → LAND |
| TASK | sends targets at 5–10 Hz, checks the mode on every iteration | task complete | mode is not GUIDED → PILOT |
| RETURN | `RTL` through a mode change command | disarm | — |
| PILOT | **stays silent**, only reads telemetry | the pilot switched back to GUIDED and confirmed | — |

The skeleton:
```python
import time
from pymavlink import mavutil

class Mission:
    def __init__(self, m):
        self.m, self.state, self.t0 = m, "WAIT_READY", time.time()
        self.alt, self.mode, self.armed = 0.0, "", False

    def go(self, state):
        print(f"{self.state} -> {state}"); self.state, self.t0 = state, time.time()

    def read(self):
        while (msg := self.m.recv_match(blocking=False)) is not None:
            t = msg.get_type()
            if t == "GLOBAL_POSITION_INT": self.alt = msg.relative_alt / 1000
            elif t == "HEARTBEAT" and msg.type != mavutil.mavlink.MAV_TYPE_GCS:
                self.mode = mavutil.mode_string_v10(msg)
                self.armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)

    def step(self):
        self.read()
        if self.state in ("TASK", "ARM_TAKEOFF") and self.mode not in ("GUIDED", ""):
            return self.go("PILOT")                       # the pilot always wins
        if self.state == "ARM_TAKEOFF" and time.time() - self.t0 > 20 and self.alt < 9:
            self.m.set_mode(self.m.mode_mapping()["LAND"]); return self.go("PILOT")
        # ... the remaining transitions follow the table
```
Code like this is easy to test: replace `m` with a fake connection (as in `examples/mavlink/tests`) and check every row of the table, including "the pilot took control in the middle of TASK".

### Safety during development
- Everything goes through SITL first. The same code, the same port, only a different address.
- A pilot with a transmitter and a switch for LOITER/RTL, always, even when "it definitely works".
- The geofence is enabled and tested.
- The first real tests use only position targets at low altitude; velocity comes later.

### Power, boot, and a watchdog for the companion
Power the companion from a separate 5 V BEC with current to spare (a Raspberry Pi 4/5 under load draws more than an amp, a Jetson several amps), not from the FC's telemetry port: a sag when a camera or modem starts will reboot the computer in the middle of a flight, and to the autopilot that is just silence on the link. The FC and the companion share a ground (through the UART signal wire and the power bus), otherwise the UART picks up noise.

The second race is boot time. The FC is ready within seconds, a Linux computer within tens of seconds, and the service with the router later still. Hence the rules for the code: wait for the autopilot's HEARTBEAT with a timeout and retry instead of crashing; request the streams (`SET_MESSAGE_INTERVAL`) after every reconnect, because they last only until the FC reboots; never arm "on service start", only on an explicit command and a verified state (the `WAIT_READY` state).

The third is a hang. The process is alive but is not sending targets (a deadlock, memory exhaustion, thermal throttling). From outside it looks the same as a crash, and you catch it with two layers: on the companion, systemd `WatchdogSec` with a service restart and, if you want, the SoC's hardware watchdog; on the FC, what is already there: `GUID_TIMEOUT` for velocity targets, and the pilot. If you need the FC to react specifically to a lost companion (for example, LAND after 5 s without its HEARTBEAT), you write that as a Lua script: in 4.7.2 scripts can receive MAVLink (`mavlink:init`, `mavlink:register_rx_msgid`, `mavlink:receive_chan`; see `libraries/AP_Scripting/docs/docs.lua:4006–4017`). That is a conclusion from the API documentation; 4.7.2 does not ship a ready-made watchdog script, so test your own in SITL the same way as the timeout test below.

### Example: velocity in GUIDED (pymavlink)
```python
from pymavlink import mavutil
m = mavutil.mavlink_connection("tcp:127.0.0.1:5762"); m.wait_heartbeat()
m.set_mode(m.mode_mapping()["GUIDED"]); m.arducopter_arm(); m.motors_armed_wait()
m.mav.command_long_send(m.target_system, m.target_component, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0,0,0,0,0,0, 10)
import time; time.sleep(10)
for _ in range(50):                          # 10 s at 5 Hz: forward 1 m/s in body frame
    m.mav.set_position_target_local_ned_send(
        0, m.target_system, m.target_component, mavutil.mavlink.MAV_FRAME_BODY_OFFSET_NED,
        0b0000111111000111,                    # use velocity only (bits: ignore pos x/y/z, acc, yaw, yaw_rate)
        0,0,0,  1.0,0.0,0.0,  0,0,0,  0,0)
    time.sleep(0.2)
# stop sending -> after GUID_TIMEOUT (3 s default) the copter stops and hovers
```
The full starter project (a square, a failsafe test, CI) is `examples/sitl-pymavlink` in the course repository. `GUID_TIMEOUT` = 3.0 s by default (range 0.1–5); the `GUID_OPTIONS` bits: 0 allows arming from the transmitter in GUIDED, 2 ignores pilot yaw, 6 uses waypoint navigation for position targets, 7 allows weathervaning.

### Worked example: "the vehicle does not move on a velocity command"
The checks, in order: (1) the mode is GUIDED (`HEARTBEAT.custom_mode`); (2) `type_mask`: is velocity masked out; (3) the sending rate is ≥ 2 Hz (the timeout is 3 s); (4) `WP_SPD` (before 4.7, `WPNAV_SPEED`)/`PSC_*` are not limiting it to zero; (5) the geofence is not holding it at the boundary; (6) `STATUSTEXT`: "Mode change to Guided failed: requires position", "PreArm: Need Position Estimate" and the like. A course guideline: most often the culprit is (1) or (2).

{{diagram:guided-timeout|A velocity target in GUIDED is valid for GUID_TIMEOUT (3 s by default): the companion must repeat it more often, otherwise the vehicle stops and hovers.}}

### Parameter reference (ArduCopter 4.7.2)
| Parameter | Default | Range / values | Old name (before 4.7) | Why a companion cares |
|---|---|---|---|---|
| `SERIALn_PROTOCOL` | 2 (MAVLink2) on SERIAL1/2 | 1 MAVLink1, 2 MAVLink2, 45 DDS XRCE, −1 None | — | the protocol of the companion port |
| `SERIALn_BAUD` | 57 (57600) on SERIAL1/2 | 57, 115, 230, 460, 921, 1500, 2000 | — | 921 for a companion |
| `BRD_SERn_RTSCTS` | SER2: 2 (Auto) | 0 Disabled, 1 Enabled, 2 Auto, 3 RS-485 | — | 1 if RTS/CTS are wired, otherwise 0 |
| `MAVn_EXT_STAT`, `MAVn_POSITION`, `MAVn_EXTRA1…3` | Copter: 0 Hz | 0–50 Hz, reboot | `SRn_*` (n from zero) | the static streams of the channel |
| `MAVn_OPTIONS` | 0 | bit 0 unsigned, 1 no forwarding, 2 ignore stream rates | bits 10, 12 in `SERIALn_OPTIONS` | isolating the channel |
| `MAV_SYSID` | 1 | 1–255 | `SYSID_THISMAV` | the companion's sysid equals this |
| `MAV_GCS_SYSID`, `MAV_GCS_SYSID_HI` | 255, 0 | 1–255, 0–255 | `SYSID_MYGCS` | who counts as the station |
| `GUID_TIMEOUT` | 3.0 s | 0.1–5 s | — | the timeout of velocity, acceleration, and angle targets |
| `GUID_OPTIONS` | 0 | bits 0, 2–7 | — | arming from the transmitter, yaw, waypoint navigation |
| `FS_GCS_ENABLE` | 0 | 0 Disabled, 1 RTL, 3 SmartRTL/RTL, 4 SmartRTL/LAND, 5 LAND, 6 DO_LAND_START/RTL, 7 BRAKE/LAND | — | the station's failsafe, not the companion's |
| `FS_GCS_TIMEOUT` | 5 s | 2–120 s | — | the station failsafe threshold |

### Place in the system

- **Receives:** the companion's wire and power (`comp-raspberry`) and the stream through a router (`mav-routing`); the vehicle state (position, mode, arming) from MAVLink telemetry, which on ArduCopter 4.7 you have to request yourself (`comp-mavlink`); a healthy position estimate, without which GUIDED does not work (`ap-ekf`); the limits within which the FC carries out any request, that is, the geofence and the failsafes (`ap-safety-fs`).
- **Provides:** position and velocity targets to the autopilot's position controller; the same GUIDED with `GUID_TIMEOUT` as the basis of a tracking loop (`per-tracking`) and of a ROS 2 node (`ros2-ardupilot`); code to run in `ap-sitl`.
- **If you get it wrong here:** you mixed up the sign of Z in `LOCAL_NED` → the target goes down instead of climbing; the axes are covered in `math-linalg-rot`. Velocity targets arrive less often than `GUID_TIMEOUT` → the vehicle stops and hovers in the middle of the task, which looks like an autopilot failure; you catch it with a run in `ap-sitl`. A port at 57600 with 50 Hz streams → packet loss and "random" timeouts in the library (`mav-sdk`).

## practice
### Step 1. Test bench: SITL → router → companion
ArduCopter 4.7.2 SITL (instance `-I 8`, so the SERIAL0 TCP port = 5760 + 80 = 5840, with the `copter.parm` parameters), MAVProxy 1.8.75 as a router with two UDP outputs, and the companion script on the first of them. The second output stands in for the ground station: in step 3 the "pilot" changes the mode from it. The `--streamrate=-1` flag is mandatory: without it MAVProxy itself requests 4 Hz streams on its input (REQUEST_DATA_STREAM), and every such request resets the message intervals of the group (`initialise_message_intervals_for_stream`, `GCS_Param.cpp` / `GCS_Common.cpp`), so the 10 Hz the companion requested with `SET_MESSAGE_INTERVAL` turns into 4 Hz. This is how it was run:

```bash
./run_sitl.sh 8 > sitl8.log 2>&1 &      # arducopter -S --model + -I 8 -w --defaults copter.parm --home -35.363261,149.165230,584,353
sleep 2
mavproxy.py --master=tcp:127.0.0.1:5840 --out=udp:127.0.0.1:14650 --out=udp:127.0.0.1:14651 \
  --streamrate=-1 --daemon --non-interactive --state-basedir=./mp8 > mavproxy8.log 2>&1 &
sleep 4
python3 -u companion_lab.py udpin:127.0.0.1:14650
```

### Step 2. The companion script: audit, GUIDED, stream, silence, takeover
The script presents itself as component 191 of its own vehicle (sysid 1), reads parameters by name (a nonexistent name returns None, which is how you see the 4.7 renames), requests LOCAL_POSITION_NED at 10 Hz (Copter 4.7 streams default to 0), switches to GUIDED, arms, and takes off with COMMAND_ACK checks, sends 2 m/s north at 5 Hz for 8 s, goes silent and records speed against time, then verifies that after the station changes the mode not a single target goes out.

```python
"""ap-companion lab: ArduCopter 4.7.2 SITL -> MAVProxy (router) -> companion (this script, compid 191).
Param audit, GUIDED arm/takeoff with COMMAND_ACK, velocity stream at 5 Hz, then silence:
measure time from the last setpoint to the stop (GUID_TIMEOUT)."""
import math, sys, time
from pymavlink import mavutil

URL = sys.argv[1] if len(sys.argv) > 1 else "udpin:127.0.0.1:14650"
m = mavutil.mavlink_connection(URL, source_system=1, source_component=191)  # MAV_COMP_ID_ONBOARD_COMPUTER
hb = m.wait_heartbeat(timeout=20)
print(f"FC heartbeat: sysid={m.target_system} compid={m.target_component} autopilot={hb.autopilot} type={hb.type}")
L = mavutil.mavlink

def param(name, timeout=3):
    m.mav.param_request_read_send(m.target_system, m.target_component, name.encode(), -1)
    t = time.time() + timeout
    while time.time() < t:
        p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.5)
        if p and p.param_id == name:
            return p.param_value
    return None

print("--- param audit (4.7.2 names; None = no such parameter)")
for n in ["SERIAL1_PROTOCOL", "SERIAL1_BAUD", "SERIAL2_PROTOCOL", "SERIAL2_BAUD", "MAV1_EXT_STAT", "MAV2_POSITION",
          "MAV_SYSID", "MAV_GCS_SYSID", "SYSID_THISMAV", "SR0_EXT_STAT", "GUID_TIMEOUT", "GUID_OPTIONS",
          "FS_GCS_ENABLE", "FS_GCS_TIMEOUT", "DDS_ENABLE"]:
    v = param(n)
    print(f"{n:17s} = {v if v is None else round(v, 3)}")

def cmd(command, *p, timeout=3):
    m.mav.command_long_send(m.target_system, m.target_component, command, 0, *(list(p) + [0] * (7 - len(p))))
    a = m.recv_match(type="COMMAND_ACK", blocking=True, timeout=timeout,
                     condition=f"COMMAND_ACK.command=={command}")
    return None if a is None else a.result

state = {"mode": "", "armed": False, "alt": 0.0, "v": 0.0}
def pump(dt=0.0):
    end = time.time() + dt
    while True:
        msg = m.recv_match(blocking=dt > 0, timeout=max(0.01, end - time.time()))
        if msg is not None:
            t = msg.get_type()
            if t == "HEARTBEAT" and msg.get_srcComponent() == 1:
                state["mode"] = mavutil.mode_string_v10(msg)
                state["armed"] = bool(msg.base_mode & L.MAV_MODE_FLAG_SAFETY_ARMED)
            elif t == "LOCAL_POSITION_NED":
                state["alt"], state["v"] = -msg.z, math.hypot(msg.vx, msg.vy)
        if time.time() >= end and msg is None:
            return

# 4.7: MAVn_* stream rates are 0 by default -> ask for the message we control by, 10 Hz
print("SET_MESSAGE_INTERVAL LOCAL_POSITION_NED 10 Hz ACK =", cmd(L.MAV_CMD_SET_MESSAGE_INTERVAL, 32, 100000))
print("--- wait for EKF / GPS (pre-arm)")
t0 = time.time()
while time.time() - t0 < 90:
    m.set_mode(m.mode_mapping()["GUIDED"]); pump(1.0)
    if state["mode"] == "GUIDED":
        r = cmd(L.MAV_CMD_COMPONENT_ARM_DISARM, 1)
        if r == 0:
            break
print(f"GUIDED + arm ACK=0 after {time.time()-t0:.1f} s, mode={state['mode']}")
print("takeoff ACK =", cmd(L.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 10))
t0 = time.time()
while state["alt"] < 9.5 and time.time() - t0 < 30:
    pump(0.2)
print(f"alt {state['alt']:.1f} m after {time.time()-t0:.1f} s")

VEL_ONLY = 0b0000_1111_1100_0111
print("--- 2 m/s north at 5 Hz for 8 s, then silence")
t0 = time.time(); last = 0
while time.time() - t0 < 8:
    if state["mode"] != "GUIDED":
        print("pilot took over"); break
    m.mav.set_position_target_local_ned_send(0, m.target_system, m.target_component, L.MAV_FRAME_LOCAL_NED,
                                             VEL_ONLY, 0, 0, 0, 2.0, 0, 0, 0, 0, 0, 0, 0)
    last = time.time(); pump(0.2)
print(f"speed at last setpoint: {state['v']:.2f} m/s")
t_dec = t_stop = None; trace = []
while time.time() - last < 10:
    pump(0.1); dt = time.time() - last; trace.append((round(dt, 2), round(state["v"], 2)))
    if t_dec is None and state["v"] < 1.8: t_dec = dt
    if t_stop is None and state["v"] < 0.2: t_stop = dt
    if t_stop and dt > t_stop + 1: break
open("guided_timeout_trace.csv", "w").write("t_s,v_ms\n" + "".join(f"{a},{b}\n" for a, b in trace))
print("t after last setpoint, s : " + " ".join(f"{a:4.1f}" for a, _ in trace[4::5]))
print("ground speed, m/s        : " + " ".join(f"{b:4.2f}" for _, b in trace[4::5]))
print(f"speed < 1.8 m/s after {t_dec:.1f} s; < 0.2 m/s after {t_stop:.1f} s from the last setpoint; mode={state['mode']}")
print("--- pilot takeover: GCS (sysid 255, port 14651) switches to LOITER 3 s into a new velocity stream")
import threading
def gcs():
    g = mavutil.mavlink_connection("udpin:127.0.0.1:14651", source_system=255, source_component=190)
    g.wait_heartbeat(timeout=10); time.sleep(3.0)
    g.set_mode(g.mode_mapping()["LOITER"]); gcs.t = time.time()
threading.Thread(target=gcs, daemon=True).start()
t0 = time.time(); sent_after = 0; gcs.t = None; seen = None
while time.time() - t0 < 10:
    pump(0.2)
    if state["mode"] != "GUIDED":
        seen = seen or time.time()
        if time.time() - seen > 2: break
        continue                                   # PILOT state: read only, send nothing
    m.mav.set_position_target_local_ned_send(0, m.target_system, m.target_component, L.MAV_FRAME_LOCAL_NED,
                                             VEL_ONLY, 0, 0, 0, 0, 2.0, 0, 0, 0, 0, 0, 0)
    if gcs.t: sent_after += 1
print(f"mode {state['mode']} seen {seen - gcs.t:.2f} s after the GCS command; setpoints sent after it: {sent_after}")
m.set_mode(m.mode_mapping()["GUIDED"]); pump(1.0)
print("LAND ACK =", cmd(L.MAV_CMD_NAV_LAND, 0, 0, 0, 0, 0, 0, 0))
t0 = time.time()
while state["armed"] and time.time() - t0 < 60:
    pump(0.5)
print(f"disarmed after landing: {not state['armed']} ({time.time()-t0:.0f} s)")
```

### Step 3. The output of the run and how to read it
```text
FC heartbeat: sysid=1 compid=0 autopilot=3 type=2
--- param audit (4.7.2 names; None = no such parameter)
SERIAL1_PROTOCOL  = 2.0
SERIAL1_BAUD      = 57.0
SERIAL2_PROTOCOL  = 2.0
SERIAL2_BAUD      = 57.0
MAV1_EXT_STAT     = 0.0
MAV2_POSITION     = 0.0
MAV_SYSID         = 1.0
MAV_GCS_SYSID     = 255.0
SYSID_THISMAV     = None
SR0_EXT_STAT      = None
GUID_TIMEOUT      = 3.0
GUID_OPTIONS      = 0.0
FS_GCS_ENABLE     = 0.0
FS_GCS_TIMEOUT    = 5.0
DDS_ENABLE        = None
SET_MESSAGE_INTERVAL LOCAL_POSITION_NED 10 Hz ACK = 0
--- wait for EKF / GPS (pre-arm)
GUIDED + arm ACK=0 after 28.1 s, mode=GUIDED
takeoff ACK = 0
alt 9.5 m after 8.8 s
--- 2 m/s north at 5 Hz for 8 s, then silence
speed at last setpoint: 1.99 m/s
t after last setpoint, s :  0.7  1.2  1.7  2.2  2.7  3.2  3.7  4.2  4.7  5.2
ground speed, m/s        : 1.99 1.99 1.99 1.98 1.98 1.98 1.33 0.27 0.04 0.02
speed < 1.8 m/s after 3.5 s; < 0.2 m/s after 4.3 s from the last setpoint; mode=GUIDED
--- pilot takeover: GCS (sysid 255, port 14651) switches to LOITER 3 s into a new velocity stream
mode LOITER seen 0.08 s after the GCS command; setpoints sent after it: 0
LAND ACK = 0
disarmed after landing: True (13 s)
```

Read it block by block. Audit: the `SERIAL1`/`SERIAL2` ports are MAVLink2 at 57600, the channel streams are zero, the old names `SYSID_THISMAV` and `SR0_EXT_STAT` do not exist, `GUID_TIMEOUT` = 3.0 s, the station failsafe is disabled, and there is no `DDS_ENABLE`: this SITL build has no AP_DDS (see the ros2-ardupilot module). `compid=0` in the first line means pymavlink used the broadcast component address; ArduPilot accepts commands with it, as the ACK = 0 results confirm. Arming succeeded after 28.1 s, which is how long SITL waits for the EKF and GPS; before that the switch to GUIDED (which needs a position from the EKF) or the arm is rejected, and the loop retries once a second. Silence: at 1.99 m/s at the moment of the last target the speed holds until 3.2 s, at 3.7 s it is already 1.33 m/s, and it is below 0.2 m/s after 4.3 s. Telemetry ran at 10 Hz (in the CSV the values change every 0.1 s: at 3.21 s still 1.98, at 3.31 s 1.96, at 3.41 s 1.89), so the start of braking is determined to within ±0.1 s: 3.2–3.3 s, that is, `GUID_TIMEOUT` plus the telemetry delay and the script's polling step (0.1 s). In the first run, without `--streamrate=-1`, telemetry ran at 4 Hz, and the same boundary was blurred to 3.0–3.4 s. Takeover: the station switched to LOITER, the script saw the new mode in HEARTBEAT after 0.08 s and sent no targets after that.

{{diagram:chart-ap-guided-silence-stop|The speed holds for the full 3 s of GUID_TIMEOUT after the last target and drops to zero in about a second of braking: the stop at < 0.2 m/s comes after 4.3 s.}}

### Step 4. The state machine on a fake connection
Add the transitions from the table and a test: the fake returns a HEARTBEAT with LOITER mode in the middle of TASK, and the state machine must move to PILOT and send no more targets. A second test: altitude does not increase for 20 s after takeoff, and the state machine commands LAND. Both tests go into CI, as in the `examples/sitl-pymavlink` starter.

### Step 5. Capstone framework
Assemble it from the track's modules: a Raspberry Pi with a router → a Python service → GUIDED logic (for example, "orbit a point of interest and return"), and an ESP32 indicating the state. The readiness criterion: the scenario works in SITL, the protocol and the behavior on a companion failure are documented, and a real flight happens only with a geofence and a pilot.

### Moving to real hardware
The wire: FC TELEM2 ↔ companion UART (TX→RX, RX→TX, GND), `SERIAL2_PROTOCOL = 2`, `SERIAL2_BAUD = 921`, `BRD_SER2_RTSCTS = 0` (or 1 with RTS/CTS wired); reboot the FC. The companion is powered from its own 5 V BEC. The order, with acceptance criteria and abort conditions:

1. **Bench, propellers off, FC and companion on battery power.** Run the script up to the "wait for EKF" block (with arming commented out). Acceptance: the audit prints the same values you set; `MAV3_*` (or your channel number) are zeros unless you set them; the `SET_MESSAGE_INTERVAL` request gives ACK = 0 and LOCAL_POSITION_NED arrives at 10 Hz ± 1 Hz (count over 10 s); if you get ~4 Hz, the router (MAVProxy without `--streamrate=-1`, or a ground station) re-requested the streams and reset the interval. Abort: packet loss on the link > 1% by the seq counter means lowering the baud rate or shortening the wire.
2. **Bench, propellers off, arming.** GUIDED and an arm with an ACK check, no takeoff: in ArduCopter without propellers the motors spin up to idle, as they should. Acceptance: ACK = 0, GUIDED mode in HEARTBEAT. Abort: on any ACK ≠ 0, read the `STATUSTEXT` "PreArm: …"; do not work around it.
3. **Field, propellers on, a pilot with a transmitter, a LOITER/RTL switch, a geofence.** Take off to 10 m, a velocity target of 1 m/s for 3 s, then silence. Acceptance: braking starts after `GUID_TIMEOUT` ± 0.5 s in the DataFlash log (the target is the `GUIP` message, the response is `PSCN`/`PSCE`), and the vehicle hovers; after the pilot switches to LOITER the companion sends no targets (the router's tlog). Abort: the pilot takes control on any movement in the wrong direction (axis sign, frame), and you analyze it on the ground.

### What you should get and what to record
- **Audit.** The table of 15 parameters matches the step 3 output (in SITL) or what you set (on hardware); the old 4.6 names answer None.
- **Velocity and the timeout.** `VEL_ONLY` targets are sent at 5 Hz. After the silence the speed holds for ~3 s (`GUID_TIMEOUT`) and drops to < 0.2 m/s in about a second of braking: in the run, 3.2–3.3 s to the start of the drop and 4.3 s to the stop. Save the CSV, `guided_timeout_trace.csv`.
- **A mode change by the pilot.** The station switches to LOITER in the middle of the stream: the script sees the mode in `HEARTBEAT.custom_mode` within a fraction of a second (0.08 s in the run) and sends no more targets, so the `setpoints sent after it` counter = 0.
- **Position (extension).** A `SET_POSITION_TARGET_LOCAL_NED` target with the mask `0b0000_1111_1111_1000` (x, y, z only) to (20, 0, −10): the vehicle flies to a point 20 m north at an altitude of 10 m and hovers there with no stream of targets, because a position target has no timeout. Record the arrival time and the position error from `LOCAL_POSITION_NED`.
- **Geofence (extension).** `FENCE_ENABLE = 1`, type altitude and circle, radius 50 m, action RTL. A target outside the circle is rejected, or the vehicle flies to the boundary and goes into RTL; save the log: it is proof that the protection works without your code.

Self-check: the lab is done when (SITL) the audit shows `SERIAL1/2_PROTOCOL = 2`, `SERIAL1/2_BAUD = 57`, `MAV1_EXT_STAT = 0`, `MAV_SYSID = 1`, `MAV_GCS_SYSID = 255`, `GUID_TIMEOUT = 3.0`, and `SYSID_THISMAV` and `SR0_EXT_STAT` are None; `SET_MESSAGE_INTERVAL`, the arm, the takeoff, and the landing give ACK = 0; after the last 2 m/s target the speed is no lower than 1.9 m/s until 3.0 s and below 0.2 m/s no later than 5.0 s; LOCAL_POSITION_NED in the CSV changes in 0.1 s steps (10 Hz); after the station switches to LOITER the script sent 0 targets; both state machine tests on the fake connection (step 4) pass. Count the extensions separately: the position target is an arrival at (20, 0, −10) with an error < 1 m and a hover with no stream; the geofence is a target beyond the 50 m circle that was rejected or ended in RTL. On hardware, use the three acceptance criteria from the previous subsection.

**Reference for the self-check.** A correct result matches the step 3 output: the speed drops after 3.2–3.3 s, the stop comes after ~4.3 s, and after the pilot changes the mode the companion stays silent. Typical wrong results: (1) LOCAL_POSITION_NED arrives at ~4 Hz instead of 10 Hz, because MAVProxy was started without `--streamrate=-1` and its REQUEST_DATA_STREAM requests reset the interval; (2) the script hangs on "wait for EKF" for more than 90 s although everything is ready in SITL: no HEARTBEAT with a mode was received, because the streams and the router are not set up or the script is listening on the wrong UDP port; (3) the vehicle jerks and hovers while the script is still running, because the pause between targets exceeded `GUID_TIMEOUT` (3 s): keep the rate at 2 Hz or higher; (4) after the silence the vehicle does not stop but flies somewhere and hovers, because the last target was a position target, which has no timeout; (5) the vehicle goes the wrong way in altitude, because the sign of Z is wrong (in LOCAL_NED the Z axis points down, so an altitude of 10 m is z = −10) or the wrong field is masked in `type_mask`.

## diagnostics
- **Symptom:** the vehicle does not respond to targets
  - Possible cause: not in GUIDED, not armed, or `type_mask` ignores the fields you need.
  - What to do: check the mode and arming in the heartbeat, the mask, and `STATUSTEXT`.
- **Symptom:** it flies up instead of down (or the other way around)
  - Possible cause: the sign of Z in NED.
  - What to do: Z is positive down; a climb is a negative Z.
- **Symptom:** it hovers after a couple of seconds although a command was sent
  - Possible cause: the velocity target was sent once, and the timeout fired.
  - What to do: send it regularly (5–10 Hz).
- **Symptom:** it stops at a boundary before reaching the target
  - Possible cause: the geofence or the `WP_*` limits.
  - What to do: check `FENCE_*` and the FC messages; this is protection, not a bug.
- **Symptom:** the companion script receives only HEARTBEAT, with no position or mode
  - Possible cause: ArduCopter 4.7: the `MAVn_*` streams default to 0; the script listens to the port directly, with no station to request the streams.
  - What to do: `MAV_CMD_SET_MESSAGE_INTERVAL` for the messages you need after every connection, or set `MAVn_*` for your channel (with a reboot).
  - In the log: the router's tlog has only a HEARTBEAT once a second from sysid 1.
- **Symptom:** after the update to 4.7 the parameters `SR2_*`, `SYSID_THISMAV`, `SYSID_MYGCS` have "disappeared"
  - Possible cause: the 4.7 rename: `MAVn_*` (the MAVLink channel number, not the SERIAL number), `MAV_SYSID`, `MAV_GCS_SYSID`.
  - What to do: look for the new names; count the channel number in the order of the MAVLink ports (the console is MAV1).
- **Symptom:** random command and mission timeouts, lost packets with 50 Hz telemetry
  - Possible cause: the companion port is at 57600 (the SERIAL1/2 default), with the link load above 50%.
  - What to do: `SERIALn_BAUD = 921`, calculate the load (frame bytes × rate), and at 1500 use RTS/CTS.
- **Symptom:** the companion went silent in the middle of a flight, and the vehicle kept flying to the point
  - Possible cause: the last target was a position, which has no `GUID_TIMEOUT`; the silence is often caused by a power sag on the companion.
  - What to do: in modes where a companion failure must stop the vehicle, send velocity targets; a separate BEC; if needed, a Lua watchdog on the companion's HEARTBEAT.
- **Symptom:** the GCS failsafe does not trigger although the ground station is gone, or it triggers with the companion alive
  - Possible cause: sysid confusion: the failsafe watches only the sysids in `MAV_GCS_SYSID`…`_HI`, and the companion's heartbeat (sysid 1) does not reset it; a station with a nonstandard sysid outside the range.
  - What to do: check the station's sysid and `MAV_GCS_SYSID`; keep the companion on the vehicle's sysid, compid 191.

## references
- Copter Commands in Guided Mode — ArduPilot Dev | https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html | primary | A
- MAVLink SET_POSITION_TARGET_LOCAL_NED (common.xml) | https://mavlink.io/en/messages/common.html#SET_POSITION_TARGET_LOCAL_NED | primary | A
- Guided Mode — ArduPilot Copter | https://ardupilot.org/copter/docs/ac2_guidedmode.html | primary | A
- ArduPilot Copter-4.7.2 — mode_guided.cpp (timeouts per target type) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/ArduCopter/mode_guided.cpp | primary | A
- ArduPilot Copter-4.7.2 — AP_SerialManager.cpp (SERIALn_PROTOCOL/BAUD, defaults) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_SerialManager/AP_SerialManager.cpp | primary | A
- ArduPilot Copter-4.7.2 — GCS_MAVLink_Parameters.cpp (MAVn_* streams, options) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/GCS_MAVLink/GCS_MAVLink_Parameters.cpp | primary | A
- ArduPilot Copter-4.7.2 — GCS_Common.cpp (own-sysid acceptance, GCS heartbeat) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/GCS_MAVLink/GCS_Common.cpp | primary | A
- MAVProxy | https://ardupilot.org/mavproxy/ | primary | A

## checklist
- All targets go through SITL first
- The sign of Z in NED is checked
- Velocity targets are sent regularly, and the timeout was tested deliberately
- The code respects a mode change by the pilot
- The geofence is enabled, and there is a pilot with a LOITER/RTL switch
- The behavior on a companion failure is documented
- The companion port: MAVLink2, 921, RTS/CTS according to the actual wiring; the `MAVn` channel number is worked out
- The companion requests the streams itself (`SET_MESSAGE_INTERVAL`); I do not rely on the station
- The companion is on the vehicle's sysid, compid 191; the GCS failsafe is set up for the station
- The companion is powered from its own BEC, the service runs under a watchdog, and it waits for the FC with a timeout
