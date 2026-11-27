---
id: px4-companion-jetson
title: "PX4 + Jetson Orin: a companion over UART, MAVLink and uXRCE-DDS"
level: L3
readingTime: 45 min
firmware: PX4 1.18 (checked against the v1.17.0 source; v1.18.0 parameter differences noted, link budget from the 1.17.0 topics) · JetPack 7.2.2 (Jetson Linux 39.2.2, Ubuntu 24.04) / JetPack 6.2.x (Ubuntu 22.04)
status: published
tags:
  - Jetson
  - companion
  - uXRCE-DDS
  - offboard
related:
  - comp-intro
  - px4-ros2
  - per-cv
  - per-edge-ml
next:
  - per-cv
source: content/px4/px4-companion-jetson.md
source_hash: 601397b0c346
---

## summary
The Jetson Orin Nano/NX is the standard vision companion for PX4: CUDA and TensorRT in 7–40 W. This module puts the whole setup together: roles and the boundary of responsibility, choosing JetPack and ROS 2 for the same Ubuntu (as of November 2026, JetPack 7.2.2 on Ubuntu 24.04 supports the whole Orin family), power modes and Super Mode, power supply and heat, the physical connection to TELEM2, how to **find** the right UART on your JetPack version (the device name differs between versions), the two links (MAVLink and uXRCE-DDS) with their PX4 parameters, bandwidth and checks, starting the agent with systemd, and the latency budget of the "camera → command" chain. The lab starts with a link and power budget (a script that runs on any computer), then the connection and measurements on hardware. The first-generation Jetson Nano is out of support (JetPack 4, Ubuntu 18.04), so do not use it for new projects.

## theory
### Roles and the boundary
The Pixhawk (PX4) does stabilization, EKF, failsafes and missions; the Jetson does vision, planning, ROS 2 and networking. The boundary is the same as in the "Companion: role and boundaries" module: without the Jetson the vehicle must still fly and come back, and losing the companion in offboard is handled by the PX4 failsafe (`COM_OF_LOSS_T`, `COM_OBL_RC_ACT`), not by hope. PX4 also watches the companion a second way: if the HEARTBEAT from a component of type "onboard controller" stops arriving over MAVLink, after 5 s (`COM_OBC_LOSS_T` before 1.18, 5 s by default) commander reports "Connection to mission computer lost". It is only a warning with no action (`Commander.cpp`, v1.17.0 and v1.18.0); the offboard failsafe sets the reaction. In 1.18 the timeout is not a parameter: the 5 s are hard-coded and `COM_OBC_LOSS_T` is removed.

### Which Jetson and which system
| Board | Power modes: original → Super (`nvpmodel`) | INT8 sparse, TOPS: original → Super | What it gives you |
|---|---|---|---|
| Orin Nano 4 GB | 7, 10 W → 7 (or 10), 25 W, MAXN SUPER | 20 → 34 | a minimal detector |
| Orin Nano 8 GB | 7, 15 W → 15, 25 W, MAXN SUPER | 40 → 67 | the main choice for detection and tracking |
| Orin NX 8 GB | 10, 15, 20 W, MAXN → +40 W, MAXN SUPER | 70 → 117 | the same module form factor, twice the compute |
| Orin NX 16 GB | 10, 15, 25 W, MAXN → +40 W, MAXN SUPER | 100 → 157 | several models at once |
| Jetson Nano (2019) | out of support, JetPack 4 | — | not for new projects |

The power modes and TOPS are from NVIDIA's Super Mode announcement (JetPack 6.2, January 2025). For the Orin Nano 4 GB the announcement contradicts itself (10 or 7 W in the lowest Super mode), so check `nvpmodel -q` on your board. TOPS are peak sparse INT8; the real speed of a model is in `per-edge-ml` and `comp-jetson-nano`.

The JetPack version decides the Ubuntu version, and with it the ROS 2 distribution. As of November 2026 the current one is JetPack 7.2.2 (Jetson Linux 39.2.2): Ubuntu 24.04, kernel 6.8, CUDA 13.2.2, supporting Thor and the whole Orin family; it pairs with ROS 2 Jazzy and the Micro XRCE-DDS agent v2.4.3. The previous line is JetPack 6.2.x on Ubuntu 22.04 with ROS 2 Humble and agent v2.4.2. The PX4 1.17 documentation names Humble on 22.04 as the recommended platform, but it covers Jazzy too (the agent version table). The rule: pick the "JetPack + ROS 2" pair for the same Ubuntu, and never install ROS 2 on an Ubuntu it was not built for; that road leads to source builds and endless dependency trouble. A new project on Orin: JetPack 7.2.x + Jazzy; an existing Humble stack is not worth moving for one Jetson.

Two JetPack 7.2.x traps on the Orin Nano devkit. There is no SD card image any more: the system is installed from an ISO image or from an x86 host. The ISO does not switch to Super a board whose bootloader was flashed without the `-super` configuration (an NVIDIA engineer's answer on the forum, June 2026): such boards, including ones sold as the Super Developer Kit, list only the 7 and 15 W modes, and a mode set by hand with `nvpmodel` falls back to 15 W after a reboot. The sign: no `-super` suffix in `/etc/nv_boot_control.conf`. The fix is reflashing from an x86 host with the `jetson-orin-nano-devkit-super` configuration; check that `sudo nvpmodel -q` shows MAXN SUPER.

### Power and heat
- Power the Jetson from a **separate** BEC or DC-DC converter on the main power bus with headroom, not from the flight controller; share ground with the Pixhawk. The battery-side current is I = P / (η·U_min). The lab example: the module in the 25 W mode plus 5 W for the carrier board and camera, efficiency 0.9: on 4S at 13.2 V (3.3 V per cell) 2.53 A, on 6S at 19.8 V 1.68 A; size the converter for 1.5 × 30 = 45 W (a course guideline, as for the BEC in `el-power-design`). Check the input voltage range in your carrier board's documentation: the devkit and third-party boards differ.
- Power mode: `sudo nvpmodel -q` shows the current one, `nvpmodel -m <N>` switches it (mode numbers depend on the module and are listed in `/etc/nvpmodel.conf`); `jetson_clocks` locks the clocks (stable latency at the cost of energy). A mode is a ceiling for the clocks, not a guarantee: when it overheats the clocks drop even in MAXN.
- Heat: in a closed case without airflow an Orin throttles within a few minutes and the detection latency doubles (the "ML on board" module). Use a heatsink with a fan or prop wash, and log `tegrastats --interval 1000 --logfile tegra.log` during the flight: each line shows CPU and GPU load and clocks (`GR3D_FREQ`), the temperatures and the power per rail. Throttling looks like the GPU clock dropping at the same load with the temperature at its upper limit.

### Physical connection
- **UART (recommended for flight)**: Pixhawk TELEM2 TX, RX, GND; on the Jetson pins 8 (TX) and 10 (RX) of the 40-pin header, ground on pin 6. Cross TX↔RX. 3.3 V logic on both sides; **do not connect the 5 V from the TELEM2 connector to the Jetson**.
- **The device name depends on the board and JetPack**: on Orin this UART is `/dev/ttyTHS0` or `/dev/ttyTHS1`, on the old Nano `/dev/ttyTHS1`; the Orin debug console is `/dev/ttyTCU0`. Do not trust an article, check with a loopback (practice, step 2).
- **Ethernet** (Pixhawk 6X, 6X Pro and others): MAVLink and uXRCE-DDS over UDP, with no UART speed limit, which makes it the best option when you have it. On `px4/fmu-v6x` PX4 1.17 sets `MAV_2_CONFIG` = 1000 by default (Ethernet, `rc.board_defaults`; it also sets `MAV_2_MODE` = 0 Normal, so set 2 Onboard for a companion).
- **USB** is for the bench; in flight a USB link is unreliable: connector vibration and re-enumeration break the link.

### Two links
1. **MAVLink** (MAVSDK, pymavlink, MAVROS): `MAV_1_CONFIG = TELEM2` (102), `MAV_1_MODE = Onboard` (the stream set for a companion), `SER_TEL2_BAUD = 921600`. By default the second MAVLink instance is disabled (to save RAM, per the comment in `src/modules/mavlink/module.yaml`), and `MAV_1_MODE` is already 2, Onboard. `MAV_1_RATE` = 0 means "half the theoretical bandwidth": baud/20 = 46 080 bytes/s at 921600. Pro: a standard, the same code works with ArduPilot; con: a limited set of data and rates.
2. **uXRCE-DDS**: `UXRCE_DDS_CFG = TELEM2` (102), the same baud rate, MAVLink off on that port (`MAV_1_CONFIG = Disabled` or moved to another port). On the Jetson, `MicroXRCEAgent serial --dev <port> -b 921600`; topics `/fmu/out/*`, `/fmu/in/*` from `px4_msgs` of **the same version** as the firmware (messages are versioned: in 1.17 some topics have the `_v1` suffix, `vehicle_status_v1`, `vehicle_local_position_v1`, `battery_status_v1`; in 1.16 only `vehicle_status`, 1.15 has no suffixes; in 1.18 it is already `vehicle_status_v4`). Pro: PX4's internal topics with low latency; con: PX4 only, and the versions must match.

One port carries one protocol. If you need both, put MAVLink on TELEM1/USB/Ethernet and DDS on TELEM2. Over Ethernet both share one cable on different UDP ports: `MAV_2_CONFIG` = 1000 for MAVLink and `UXRCE_DDS_CFG` = 1000 for DDS. The client takes the agent address from `UXRCE_DDS_AG_IP`, an IPv4 address written as a signed 32-bit integer (192.168.1.2 → −1062731518, 127.0.0.1 → 2130706433, the default), and the port from `UXRCE_DDS_PRT` (8888).

### Link bandwidth
UART 8N1 carries a byte in 10 bits: 921600 baud is 92 160 bytes/s, 3 000 000 baud (the maximum of the `uxrce_dds_client` `-b` option) is 300 000 bytes/s. The DDS client sends every outgoing topic of its build, regardless of subscribers; per the `px4-ros2` module calculation, all 27 outgoing topics of PX4 1.17.0 at their rate caps come to 107 495 bytes/s (upper bound), which is 117 % of 921600 and 36 % of 3 Mbaud. The subset a node usually needs (`vehicle_odometry`, `vehicle_local_position_v1`, `vehicle_status_v1`, `timesync_status`) is 26 835 bytes/s, 29 % of 921600. Some topics run below their cap, so the real load is what `Payload tx` shows in `uxrce_dds_client status`, but that counts only the CDR data, without the headers (up to ~23 bytes per sample; with every topic at its cap, ~78 900 bytes/s instead of up to 107 495 on the wire). Keep `Payload tx` below ~50 % of capacity (a course guideline: with headers that is about 70 % of the line; at 921600, below ~46 000 bytes/s). The time to send one setpoint frame is t = 10·N / baud: `TrajectorySetpoint` (64 bytes of CDR plus ~23 bytes of headers) takes 0.94 ms at 921600 and 0.29 ms at 3 Mbaud. The transmission itself costs almost nothing in the latency budget; the queue is what hurts when the link is overloaded.

{{diagram:jetson-link-choice|Ethernet removes the bandwidth question; on a UART, DDS with all topics does not fit into 921600 (117 %), so use either 3 Mbaud and watch Payload tx, or MAVLink, and put the two protocols on different ports.}}

### Worked example: the latency budget
CSI camera at 60 fps (up to 16 ms until a frame is ready) → TensorRT YOLO-nano FP16 ~12 ms → tracker 2 ms → DDS over UART 921600 ~2 ms (0.94 ms for the frame plus waiting for the client cycle) → PX4 velocity controller (time constant ~0.5 s). Pure delay 16 + 12 + 2 + 2 = 32 ms, rounded to ~35 ms: a tracking loop with Kp ≈ 1 1/s is stable with margin (the "Tracking" module). A USB camera with MJPEG adds 40–80 ms (72–112 ms in total), a Wi-Fi bridge instead of a wire another 20–50 ms with jitter (92–162 ms together, 3–5 times more than on a wire); two such "details" eat the whole margin. Hence the rule: CSI and a wire, not USB and radio.

{{diagram:jetson-latency-budget|With a wire and CSI the chain fits into 32 ms; a USB camera and a Wi-Fi bridge together give 92–162 ms, 3–5 times more.}}

{{diagram:px4-jetson-link|PX4 and Jetson: the camera on the Jetson, the link to the flight controller on TELEM2 over MAVLink or uXRCE-DDS.}}

{{lesson:per-edge-ml|There you learn to measure the latency and the thermal behavior of the model itself honestly (warm-up, percentiles, 20 minutes in a case), so that the 12 ms in this budget is your number, not the marketing one.}}

### Reference: parameters and commands
| Parameter / command | Default (PX4 1.17.0) | Values | Why |
|---|---|---|---|
| `MAV_1_CONFIG` | disabled | 102 TELEM2, 1000 Ethernet | MAVLink port for the companion |
| `MAV_1_MODE` | 2 (Onboard) | 0 Normal, 2 Onboard, 7 Minimal… | stream set |
| `MAV_1_RATE` | 0 | B/s; 0 → baud/20 | MAVLink bandwidth |
| `SER_TEL2_BAUD` | 921600 | baud | TELEM2 baud rate |
| `UXRCE_DDS_CFG` | 0 (disabled) | 102 TELEM2, 1000 Ethernet | DDS client port |
| `UXRCE_DDS_AG_IP` / `UXRCE_DDS_PRT` | 2130706433 / 8888 | int32 / 0–65535 | agent over Ethernet |
| — (`COM_OBC_LOSS_T` before 1.18) | 5 s | not configurable in 1.18 | companion loss warning (MAVLink) |
| `COM_OF_LOSS_T` / `COM_OBL_RC_ACT` | 1 s / 0 (Position) | s / 0–7 | Offboard loss (`px4-ros2`) |
| `sudo nvpmodel -q` / `-m <N>` | — | the module's modes | power mode |
| `sudo jetson_clocks` | — | — | clocks to the mode maximum |
| `tegrastats --interval 1000 --logfile f` | — | ms | clocks, temperatures, power |
| `MicroXRCEAgent serial --dev <port> -b 921600` | — | agent v2.4.3 (Jazzy) / v2.4.2 (Humble) | the Jetson side |

### Place in the system

- **Takes in:** power from a separate BEC with current headroom (`el-power-design`); PX4 topics and commands over TELEM2 (`px4-ros2`); CSI camera frames (`per-camera`); a port freed from other drivers (`px4-setup-scratch`).
- **Hands on:** Offboard setpoints to the PX4 velocity controller (`px4-control`); the "camera → command" latency budget to the tracking loop (`per-tracking`); a system with ROS 2 to the nodes (`ros2-px4`).
- **If you get it wrong here:** a Jetson in a closed case without airflow → throttling → the detection latency doubles → the tracking loop loses its margin and starts to oscillate (`per-edge-ml`, `per-tracking`). MAVLink and uXRCE-DDS on the same TELEM2 → no `/fmu/*` topics, the node is silent (`px4-ros2`). DDS with every topic at 921600 → the link is saturated, setpoints wait in the queue, and a gap longer than `COM_OF_LOSS_T` drops you out of Offboard (`px4-ros2`).

## practice
### Step 0. Link and power budget (calculation, no hardware)
Before soldering, work out exactly what will go over the wire and how much current the Jetson will draw. The script below runs on any computer with Python 3; the `DDS_ALL_CAPS` and `DDS_TYPICAL` numbers are the result of the `px4-ros2` lab for PX4 1.17.0. Save it as `link_lab.py`:
```python
"""Jetson <-> PX4 link budget: UART capacity, MAVLink auto rate, uXRCE-DDS load, agent IP, latency, power."""
import ipaddress
import struct

BAUDS = (921600, 1500000, 3000000)       # 921600 = SER_TEL2_BAUD default; 3000000 = uxrce_dds_client -b max
DDS_ALL_CAPS = 107495                    # B/s, px4-ros2 lab: all 27 /fmu/out topics of PX4 1.17.0 at their caps
DDS_TYPICAL = {"vehicle_odometry": 13700, "vehicle_local_position_v1": 11950,
               "vehicle_status_v1": 515, "timesync_status": 670}     # same lab, B/s at cap
SETPOINT_FRAME = 64 + 23                 # TrajectorySetpoint CDR 64 B + ~23 B XRCE/serial overhead (course estimate)

print("1) UART capacity (8N1 = 10 bit per byte) and MAV_1_RATE = 0 (PX4 uses baud/20):")
for b in BAUDS:
    print(f"   {b:>8} baud: {b // 10:>6} B/s raw, MAVLink auto rate {b // 20:>6} B/s")

print("\n2) uXRCE-DDS load on the same UART:")
typ = sum(DDS_TYPICAL.values())
for b in BAUDS:
    print(f"   {b:>8}: all topics at caps {100 * DDS_ALL_CAPS / (b / 10):5.0f} %, "
          f"odometry+local_position+status+timesync {100 * typ / (b / 10):4.0f} %")

print("\n3) Time to send one TrajectorySetpoint frame (%d B):" % SETPOINT_FRAME)
for b in BAUDS:
    print(f"   {b:>8}: {SETPOINT_FRAME * 10 / b * 1000:.2f} ms")

print("\n4) UXRCE_DDS_AG_IP is the IPv4 address as a signed int32:")
for ip in ("127.0.0.1", "192.168.1.2", "10.41.10.1"):
    u = int(ipaddress.IPv4Address(ip))
    s = struct.unpack("<i", struct.pack("<I", u))[0]
    print(f"   {ip:>12} -> {s}")

print("\n5) Latency budget camera -> setpoint, ms (module worked example):")
chains = {"CSI + wire": [16, 12, 2, 2], "USB MJPEG + wire": [16 + 40, 12, 2, 2], "USB MJPEG + Wi-Fi": [16 + 80, 12, 2, 2 + 50]}
for name, parts in chains.items():
    print(f"   {name:18s} {' + '.join(map(str, parts))} = {sum(parts)} ms")

print("\n6) Battery-side current of the Jetson DC-DC (module + 5 W carrier/camera, efficiency 0.9):")
for mode_w in (15, 25):
    for cells, vmin in ((4, 13.2), (6, 19.8)):
        i = (mode_w + 5) / 0.9 / vmin
        print(f"   {mode_w} W mode, {cells}S at {vmin} V: {i:.2f} A, size the converter for {1.5 * (mode_w + 5):.0f} W")
```
Output of `python3 link_lab.py` (2026-11-26):
```
1) UART capacity (8N1 = 10 bit per byte) and MAV_1_RATE = 0 (PX4 uses baud/20):
     921600 baud:  92160 B/s raw, MAVLink auto rate  46080 B/s
    1500000 baud: 150000 B/s raw, MAVLink auto rate  75000 B/s
    3000000 baud: 300000 B/s raw, MAVLink auto rate 150000 B/s

2) uXRCE-DDS load on the same UART:
     921600: all topics at caps   117 %, odometry+local_position+status+timesync   29 %
    1500000: all topics at caps    72 %, odometry+local_position+status+timesync   18 %
    3000000: all topics at caps    36 %, odometry+local_position+status+timesync    9 %

3) Time to send one TrajectorySetpoint frame (87 B):
     921600: 0.94 ms
    1500000: 0.58 ms
    3000000: 0.29 ms

4) UXRCE_DDS_AG_IP is the IPv4 address as a signed int32:
      127.0.0.1 -> 2130706433
    192.168.1.2 -> -1062731518
     10.41.10.1 -> 170461697

5) Latency budget camera -> setpoint, ms (module worked example):
   CSI + wire         16 + 12 + 2 + 2 = 32 ms
   USB MJPEG + wire   56 + 12 + 2 + 2 = 72 ms
   USB MJPEG + Wi-Fi  96 + 12 + 2 + 52 = 162 ms

6) Battery-side current of the Jetson DC-DC (module + 5 W carrier/camera, efficiency 0.9):
   15 W mode, 4S at 13.2 V: 1.68 A, size the converter for 30 W
   15 W mode, 6S at 19.8 V: 1.12 A, size the converter for 30 W
   25 W mode, 4S at 13.2 V: 2.53 A, size the converter for 45 W
   25 W mode, 6S at 19.8 V: 1.68 A, size the converter for 45 W
```
How to read it. Item 1 is the wire capacity and the bandwidth MAVLink takes by itself with `MAV_1_RATE` = 0. Item 2 is the baud rate decision: at 921600 the full set of DDS topics does not fit, at 1.5 Mbaud it takes 72 %, at 3 Mbaud 36 %; if the Pixhawk and the Jetson run reliably at 3 Mbaud over your cable (check with the step 2 loopback at that speed), that is the simplest headroom. Item 4 gives the values for `UXRCE_DDS_AG_IP` for an Ethernet link: the first two match the examples in the PX4 parameter description, so the formula is confirmed. Item 6 decides the choice of DC-DC converter and the wire gauge for the Jetson's power.

### Step 1. Preparing the Jetson
```bash
sudo usermod -aG dialout $USER        # access to serial ports (log out and in)
systemctl status nvgetty              # on boards where the header UART is a console, stop it:
sudo systemctl disable --now nvgetty
sudo nvpmodel -q                      # current power mode
```
Write down the power mode. An Orin Nano 8 GB flashed with the Super configuration should list the 15 W, 25 W and MAXN SUPER modes; if the list has only 7 and 15 W, the board was flashed without Super (the "Which Jetson and which system" section).

### Step 2. Find "your" UART with a loopback
A jumper between pins 8 and 10, the Pixhawk disconnected. For each candidate:
```python
import serial, sys
for dev in ("/dev/ttyTHS0", "/dev/ttyTHS1"):
    try:
        with serial.Serial(dev, 921600, timeout=0.2) as s:
            s.reset_input_buffer(); s.write(b"loopback-test\n")
            print(dev, "OK" if s.readline() == b"loopback-test\n" else "no echo")
    except serial.SerialException as e:
        print(dev, "error:", e)
```
Exactly one port should answer OK: that is pins 8/10 on your system. "Permission denied" means the dialout group or a console on the port; "no echo" on both means the wrong pins or the UART disabled in the device tree (Jetson-IO: `sudo /opt/nvidia/jetson-io/jetson-io.py`). If you plan to use 3 Mbaud, repeat the loopback with `3000000` instead of `921600`: the loopback tests the Jetson UART but not the cable to the Pixhawk, so the final speed check is in step 4, by the `Payload tx` counter with no session drops.

### Step 3. The MAVLink link
PX4 parameters in QGC: `MAV_1_CONFIG = TELEM 2`, `MAV_1_MODE = Onboard`, `SER_TEL2_BAUD = 921600`, reboot. Remove the jumper and connect TX/RX/GND (the Jetson powered from its own DC-DC, propellers off for all of steps 3–6). Check:
```python
from pymavlink import mavutil
m = mavutil.mavlink_connection("/dev/ttyTHS1", baud=921600)   # your port from step 2
m.wait_heartbeat(); print("sys", m.target_system, "comp", m.target_component)
import time, collections
cnt, t0 = collections.Counter(), time.time()
while time.time() - t0 < 10:
    msg = m.recv_match(type=["ATTITUDE", "LOCAL_POSITION_NED"], blocking=True, timeout=1)
    if msg: cnt[msg.get_type()] += 1
print({k: v / 10 for k, v in cnt.items()}, "Hz")
```
Write down the ATTITUDE and LOCAL_POSITION_NED rates.

### Step 4. The uXRCE-DDS link
`MAV_1_CONFIG = Disabled`, `UXRCE_DDS_CFG = TELEM2`, reboot. On the Jetson:
```bash
MicroXRCEAgent serial --dev /dev/ttyTHS1 -b 921600   # your port from step 2
ros2 topic list | grep fmu                     # versioned names, e.g. ..._v1 since PX4 1.16/1.17
ros2 topic hz /fmu/out/vehicle_attitude
ros2 topic echo --once /fmu/out/timesync_status
```
Compare the `vehicle_attitude` rate with ATTITUDE from step 3. In the PX4 console (the MAVLink console in QGC over USB) run `uxrce_dds_client status`: write down `Payload tx` and compare it with half the capacity from step 0 (~46 000 of 92 160 bytes/s at 921600, since `Payload tx` does not count headers).

### Step 5. Starting the agent automatically
`/etc/systemd/system/xrce-agent.service` (in `ExecStart`, your own port from step 2, `ttyTHS0` or `ttyTHS1`):
```ini
[Unit]
Description=Micro XRCE-DDS Agent for PX4
After=network.target

[Service]
ExecStart=/usr/local/bin/MicroXRCEAgent serial --dev /dev/ttyTHS1 -b 921600
Restart=always
RestartSec=2
User=nvidia

[Install]
WantedBy=multi-user.target
```
`sudo systemctl enable --now xrce-agent`; check that after `sudo kill` of the agent the topics come back on their own within ~10 s (a course guideline: 2 s of `RestartSec` + ~3 s for three missed pings + recreating the session); measure and write down your time. The binary path, the user and the port are your own. The PX4 client reconnects by itself: when the agent disappears, it recreates the session after three missed pings (~3 s), so you do not need to reboot the flight controller (read from the code; if `/fmu/in/*` does not get through after a restart, enable `UXRCE_DDS_RX_TO`).

### Step 6. Heat under load
Run the detector (the "Computer vision" module) for 20 minutes in the case, logging `tegrastats --interval 1000 --logfile tegra.log`. Find the moment throttling starts (the GPU clock drops, the temperature is at the limit) and the detection latency before and after.

### Moving to real hardware: abort and acceptance
Steps 1–6 are the hardware; the safety order is as follows. Propellers stay off until the end of step 6. Abort and investigate if: the voltage at the Jetson input sags more than 5 % below the DC-DC nominal under detector load (a course guideline), the Jetson reboots under motor load on the bench, `Payload tx` stays above 50 % of capacity (a course guideline), the agent session drops (the agent log shows the session being created again) or `timesync converged: false`. Acceptance for flight: 20 minutes of the detector in the case without throttling, or with throttling that keeps the chain latency within the budget of the "Tracking" module; the agent comes back by itself after `kill` and after a cold start.

Self-check: the lab is done when (calculation) your step 0 run gave 92160 B/s and 46080 B/s for 921600, 117 % / 72 % / 36 % for the three speeds, −1062731518 for 192.168.1.2 and 2.53 A for 25 W on 4S; (hardware) the loopback on pins 8/10 answered OK on exactly one port, the MAVLink link delivers ATTITUDE and LOCAL_POSITION_NED with their rates written down, `vehicle_attitude` shows over uXRCE-DDS and its rate is written next to ATTITUDE from step 3, `Payload tx` is written down and below 50 % of the chosen speed's capacity, after `sudo kill` of the agent the topics come back on their own (time written down, the course guideline is up to ~10 s), and in the 20-minute `tegra.log` you found the moment throttling starts (or saw that it did not) and wrote down the detection latency before and after.

**Reference answer for the self-check.** A correct result: one port, two links with measured rates, `Payload tx` below 50 % of capacity, the agent comes back by itself. Typical wrong results: (1) no port answered OK: the wrong pins or the UART disabled in the device tree, while "Permission denied" means the dialout group or a console on the port; (2) MAVLink worked but there are no DDS topics: MAVLink stayed on the same port (`MAV_1_CONFIG` not Disabled), the agent runs at another baud rate, the agent is from the v3.x branch, or `px4_msgs` is another version; (3) the detection latency roughly doubled after a few minutes: throttling in a closed case without airflow; (4) step 0 gave 115 200 bytes/s for 921600: you counted 8 bits per byte instead of 10 (forgot the start and stop bits); (5) the IP came out as 3232235778: that is the unsigned value, the parameter expects a signed int32.

## diagnostics
- **Symptom:** `Permission denied: /dev/ttyTHS*`
  - Possible cause: the user is not in dialout, or a console runs on the port.
  - What to do: `usermod -aG dialout`, log in again, `systemctl disable --now nvgetty`.
- **Symptom:** the port opens but no data arrives
  - Possible cause: the wrong ttyTHS, TX/RX not crossed, no common ground, MAVLink not enabled on TELEM2.
  - What to do: the loopback from step 2, check the wiring, `MAV_1_CONFIG`.
- **Symptom:** MAVLink works, uXRCE-DDS does not
  - Possible cause: MAVLink is still on the same port, the agent runs at another baud rate, a v3.x agent, `px4_msgs` of another version.
  - What to do: `MAV_1_CONFIG = Disabled`, the same baud rate, agent v2.4.3/v2.4.2, `px4_msgs` from the branch that matches the firmware.
- **Symptom:** the topics are there, but `ros2 topic echo` is silent
  - Possible cause: a QoS mismatch (PX4 publishes best effort).
  - What to do: a subscriber with `qos_profile_sensor_data`, `ros2 topic echo --qos-reliability best_effort`.
- **Symptom:** topics come and go; rates are lower than expected
  - Possible cause: the UART is saturated: the full set of DDS topics needs 117 % of 921600.
  - What to do: `uxrce_dds_client status` → `Payload tx`; raise the baud rate to 1.5–3 Mbaud (both sides), Ethernet or a trimmed `dds_topics.yaml`.
- **Symptom:** over Ethernet the client cannot find the agent
  - Possible cause: `UXRCE_DDS_AG_IP` entered as an unsigned number or with the octets swapped, the agent listens on another port.
  - What to do: convert the IP to a signed int32 (step 0), check `UXRCE_DDS_PRT` against `MicroXRCEAgent udp4 -p`.
- **Symptom:** after installing JetPack 7.2 there are no 25 W and MAXN SUPER modes, and a manually set mode resets after a reboot
  - Possible cause: the board was flashed without the Super configuration; the ISO does not switch it to Super.
  - What to do: reflash from an x86 host with the `jetson-orin-nano-devkit-super` configuration, check `nvpmodel -q`.
- **Symptom:** "Connection to mission computer lost" in QGC
  - Possible cause: the companion's MAVLink HEARTBEAT has been missing for more than 5 s (`COM_OBC_LOSS_T` before 1.18): the process crashed, the Jetson rebooted.
  - What to do: this is a warning with no action, so make sure the offboard failsafe (`COM_OBL_RC_ACT`) is configured; go through `journalctl` on the Jetson.
- **Symptom:** the detection latency grows after 10 minutes of flight
  - Possible cause: Jetson throttling.
  - What to do: airflow, the `nvpmodel` mode, `tegrastats` in the flight log.
- **Symptom:** the Jetson reboots on throttle
  - Possible cause: a sag on a shared BEC or a DC-DC without headroom (current calculation in step 0).
  - What to do: a separate DC-DC with 1.5× headroom, a capacitor on the input, measure the voltage with an oscilloscope under load.

## references
- PX4 — Pixhawk + Companion Computer | https://docs.px4.io/v1.17/en/companion_computer/pixhawk_companion.html | primary | A
- PX4 — uXRCE-DDS (PX4–ROS 2/DDS bridge) | https://docs.px4.io/v1.17/en/middleware/uxrce_dds.html | primary | A
- PX4-Autopilot v1.17.0 — mavlink module.yaml (MAV_n_CONFIG, MAV_n_MODE, MAV_n_RATE) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/mavlink/module.yaml | primary | A
- PX4-Autopilot v1.17.0 — uxrce_dds_client module.yaml (UXRCE_DDS_AG_IP int32 encoding) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/uxrce_dds_client/module.yaml | primary | A
- NVIDIA — JetPack SDK / Jetson Linux 39.2.2 (JetPack 7.2.2) | https://developer.nvidia.com/embedded/jetson-linux | primary | A
- NVIDIA — JetPack 7.2.1 release notes and downloads | https://developer.nvidia.com/embedded/jetpack/downloads/archive-7.2.1 | primary | A
- NVIDIA Technical Blog — JetPack 6.2 brings Super Mode to Orin Nano and Orin NX | https://developer.nvidia.com/blog/nvidia-jetpack-6-2-brings-super-mode-to-nvidia-jetson-orin-nano-and-jetson-orin-nx-modules | primary | A
- NVIDIA Developer Forums — 25W and MAXN SUPER not seen in JetPack 7.2 | https://forums.developer.nvidia.com/t/25w-and-maxn-super-not-seen-in-jetpack-7-2/372627 | secondary | B
- eProsima — Micro XRCE-DDS Agent | https://github.com/eProsima/Micro-XRCE-DDS-Agent | primary | A
- NVIDIA Developer Forums — UART1 on expansion pins 8/10 (Orin) | https://forums.developer.nvidia.com/t/how-to-access-uart1-on-expansion-pins-8-10/328934 | secondary | B

## checklist
- I understand the boundary between the Jetson and PX4, and what PX4 does when the companion is lost
- I pick JetPack and ROS 2 for the same Ubuntu; I check that the Orin is flashed with Super if I need 25 W
- I power the Jetson separately with 1.5× headroom, compute the battery-side current, and watch the heat and the power mode
- I find my UART with a loopback, not from an article
- I set up MAVLink and uXRCE-DDS on different ports and check the rates
- I do the bandwidth math: `Payload tx` (without headers) below 50 % of the link capacity
- I start the agent through systemd with automatic restart
- I work out the "camera → command" latency budget
