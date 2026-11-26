---
id: px4-companion-jetson
title: "PX4 + Jetson Orin: a companion over UART, MAVLink and uXRCE-DDS"
level: L3
readingTime: 35 min
firmware: PX4 1.15+ · JetPack 6/7
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
source_hash: 53438f964c4d
---

## summary
Jetson Orin Nano/NX is the standard companion computer for vision on PX4: CUDA and TensorRT in 7–25 W. This module puts the whole setup together: roles and the boundary of responsibility, power and heat, the physical connection to TELEM2, how to **find** the right UART on your JetPack version (the device name differs between versions), the two communication channels — MAVLink and uXRCE-DDS — with the PX4 parameters and how to verify them, starting the agent automatically with systemd, and the latency budget of the “camera → command” chain. The first-generation Jetson Nano is no longer supported (JetPack 4, Ubuntu 18.04) — don't pick it for new projects.

## theory
### Roles and the boundary
Pixhawk (PX4) — stabilization, EKF, failsafe, missions; Jetson — vision, planning, ROS 2, networking. The boundary is the same as in the module “Companion: role and boundaries”: without the Jetson the vehicle must still fly and return, and loss of the companion in offboard is handled by the PX4 failsafe (`COM_OF_LOSS_T`, `COM_OBL_RC_ACT`), not by hope.

### Which Jetson and which OS
| Board | What it gives you | OS |
|---|---|---|
| Orin Nano 4/8 GB | the main choice for detection and tracking; 7–25 W modes (`nvpmodel`) | JetPack 6 (Ubuntu 22.04 → ROS 2 Humble) or JetPack 7 (Ubuntu 24.04 → ROS 2 Jazzy) |
| Orin NX 8/16 GB | 2× the compute, the same module form factor | the same |
| Jetson Nano (2019) | no longer supported, JetPack 4 | not for new projects |

The JetPack version determines the Ubuntu version, and therefore the ROS 2 distribution: installing ROS 2 on the “wrong” Ubuntu is the road to building from source and endless dependency problems.

### Power and heat
- The Jetson gets a **separate** BEC or DC-DC from the power bus with current headroom, not power from the flight controller; common ground with the Pixhawk.
- Power mode: `sudo nvpmodel -q` shows the current one, `nvpmodel -m <N>` switches it; `jetson_clocks` locks the clocks (stable latency at the cost of energy).
- Heat: in a closed enclosure without airflow the Orin throttles after a few minutes, and detection latency doubles (module “ML on board”). A heatsink with a fan or prop wash airflow, and `tegrastats` in the flight log.

### Physical connection
- **UART (recommended for flight)**: Pixhawk TELEM2 — TX, RX, GND; Jetson — pins 8 (TX) and 10 (RX) of the 40-pin header, ground on pin 6. TX↔RX crossed. 3.3 V logic on both sides; **do not connect the 5 V from the TELEM2 connector to the Jetson**.
- **The device name depends on the board and JetPack**: on Orin this UART can be `/dev/ttyTHS0` or `/dev/ttyTHS1`, on the old Nano it is `/dev/ttyTHS1`; the Orin debug console is `/dev/ttyTCU0`. Don't trust an article — check with a loopback (practice, step 2).
- **Ethernet** (Pixhawk 6X, 6X Pro, etc.): MAVLink and uXRCE-DDS over UDP, without the UART speed limit — the best option if you have it.
- **USB** — for the bench; in flight a USB connection is unreliable: connector vibration and re-enumeration drop the link.

### Two communication channels
1. **MAVLink** (MAVSDK, pymavlink, MAVROS): `MAV_1_CONFIG = TELEM2`, `MAV_1_MODE = Onboard` (the stream set for a companion), `SER_TEL2_BAUD = 921600`. Pro: it's a standard, the same code works with ArduPilot; con: a limited set of data and rates.
2. **uXRCE-DDS**: `UXRCE_DDS_CFG = TELEM2`, the same baud rate, MAVLink disabled on this port (`MAV_1_CONFIG = Disabled` or moved to another port). On the Jetson — `MicroXRCEAgent serial --dev <port> -b 921600`; the topics `/fmu/out/*`, `/fmu/in/*` from `px4_msgs` of **the same version** as the firmware (since 1.16 messages are versioned, some topics have a `_v1` suffix). Pro: PX4's internal topics with low latency; con: PX4 only, the versions must match.

Only one thing lives on one port. If you need both — MAVLink on TELEM1/USB/Ethernet, DDS on TELEM2.

{{diagram:jetson-link-choice|Ethernet снимает вопрос полосы; на UART DDS со всеми топиками не помещается в 921600 (117 %), поэтому либо 3 Мбод и контроль Payload tx, либо MAVLink, а два протокола — на разных портах.}}

### Worked example: the latency budget
CSI camera at 60 fps (up to 16 ms until a frame is ready) → TensorRT YOLO-nano FP16 ~12 ms → tracker 2 ms → DDS over UART at 921600 ~2 ms → PX4 velocity controller (time constant ~0.5 s). The pure delay is ~35 ms: a tracking loop with Kp ≈ 1 1/s is stable with margin (module “Tracking”). A USB camera with MJPEG adds 40–80 ms, a Wi-Fi bridge instead of a wire adds 20–50 ms with jitter; two such “small things” eat the whole margin. Hence the rule: CSI and a wire, not USB and radio.

{{diagram:jetson-latency-budget|На проводе и CSI цепочка укладывается в 32 мс; USB-камера и Wi-Fi-мост вместе дают 92–162 мс — в 3–5 раз больше.}}

{{diagram:px4-jetson-link|PX4 and Jetson: the camera is on the Jetson, the link to the flight controller is over TELEM2 via MAVLink or uXRCE-DDS.}}

## practice
### Step 0. Link and power budget (calculation, no hardware)
Runs on any computer with Python 3. `DDS_ALL_CAPS` and `DDS_TYPICAL` come from the `px4-ros2` lab for PX4 1.17.0. Save as `link_lab.py`:
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

### Step 1. Prepare the Jetson
```bash
sudo usermod -aG dialout $USER        # access to serial ports (log out and in)
systemctl status nvgetty              # on boards where the header UART is a console, stop it:
sudo systemctl disable --now nvgetty
sudo nvpmodel -q                      # current power mode
```

### Step 2. Find “your” UART with a loopback
A jumper between pins 8 and 10, the Pixhawk not connected. For each candidate:
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
Exactly one port should answer OK — that is pins 8/10 on your system. “Permission denied” — the dialout group or a console on the port; “no echo” on both — wrong pins or the UART is disabled in the device tree (Jetson-IO: `sudo /opt/nvidia/jetson-io/jetson-io.py`).

### Step 3. The MAVLink channel
PX4 parameters in QGC: `MAV_1_CONFIG = TELEM 2`, `MAV_1_MODE = Onboard`, `SER_TEL2_BAUD = 921600`, reboot. Remove the jumper, connect TX/RX/GND. Check:
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
Write down the rates of ATTITUDE and LOCAL_POSITION_NED.

### Step 4. The uXRCE-DDS channel
`MAV_1_CONFIG = Disabled`, `UXRCE_DDS_CFG = TELEM2`, reboot. On the Jetson:
```bash
MicroXRCEAgent serial --dev /dev/ttyTHS1 -b 921600
ros2 topic list | grep fmu                     # versioned names, e.g. ..._v1 since PX4 1.16/1.17
ros2 topic hz /fmu/out/vehicle_attitude
ros2 topic echo --once /fmu/out/timesync_status
```
Compare the rate of `vehicle_attitude` with ATTITUDE from step 3.

### Step 5. Start the agent automatically
`/etc/systemd/system/xrce-agent.service`:
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
`sudo systemctl enable --now xrce-agent`; check that after a `sudo kill` of the agent the topics come back on their own, within ~10 s (course estimate: 2 s `RestartSec` + ~3 s for three missed pings + session re-creation); measure and record your time. Use your own binary path, user and port.

### Step 6. Heat under load
Run the detector (module “Computer vision”) for 20 minutes in the enclosure, logging `tegrastats --interval 1000 --logfile tegra.log`. Find the moment throttling starts (the GPU clock drops, the temperature is at its limit) and the detection latency before and after.

The lab counts as done when the port has been found with a loopback, both channels have been verified with the rates written down, the agent comes back by itself after a crash, and you have a 20-minute thermal log.

## diagnostics
- **Symptom:** `Permission denied: /dev/ttyTHS*`
  - Possible cause: the user isn't in dialout, or there is a console on the port.
  - What to do: `usermod -aG dialout`, log in again, `systemctl disable --now nvgetty`.
- **Symptom:** the port opens, but there is no data
  - Possible cause: the wrong ttyTHS, TX/RX not crossed, no common ground, MAVLink not enabled on TELEM2.
  - What to do: the loopback from step 2, check the wiring, `MAV_1_CONFIG`.
- **Symptom:** MAVLink works, uXRCE-DDS doesn't
  - Possible cause: MAVLink is still on the same port, the agent runs at a different baud rate, `px4_msgs` is a different version.
  - What to do: `MAV_1_CONFIG = Disabled`, the same baud, `px4_msgs` from the branch that matches the firmware.
- **Symptom:** the topics are there, but `ros2 topic echo` is silent
  - Possible cause: a QoS mismatch (PX4 publishes best effort).
  - What to do: a subscriber with `qos_profile_sensor_data`, `ros2 topic echo --qos-reliability best_effort`.
- **Symptom:** detection latency grows after 10 minutes of flight
  - Possible cause: Jetson throttling.
  - What to do: airflow, the `nvpmodel` mode, `tegrastats` in the flight log.
- **Symptom:** the Jetson reboots under throttle
  - Possible cause: the shared BEC sags.
  - What to do: a separate DC-DC with headroom, a capacitor on the input, measure the voltage with an oscilloscope under load.

## references
- PX4 — Pixhawk + Companion Computer | https://docs.px4.io/main/en/companion_computer/pixhawk_companion.html | primary | A
- PX4 — uXRCE-DDS (PX4–ROS 2/DDS bridge) | https://docs.px4.io/main/en/middleware/uxrce_dds.html | primary | A
- eProsima — Micro XRCE-DDS Agent | https://github.com/eProsima/Micro-XRCE-DDS-Agent | primary | A
- NVIDIA Developer Forums — UART1 on expansion pins 8/10 (Orin) | https://forums.developer.nvidia.com/t/how-to-access-uart1-on-expansion-pins-8-10/328934 | secondary | B

## checklist
- I understand the boundary between the Jetson and PX4 and what PX4 does when the companion is lost
- I choose JetPack and ROS 2 for the same Ubuntu
- I power the Jetson separately and keep an eye on heat and the power mode
- I find my UART with a loopback, not from an article
- I set up MAVLink and uXRCE-DDS on different ports and verify the rates
- I run the agent via systemd with automatic restart
- I calculate the “camera → command” latency budget
