---
id: el-dronecan
title: "DroneCAN: the onboard CAN bus, nodes, ESCs and peripheral firmware"
level: L3
readingTime: 35 min
firmware: ArduPilot 4.7 (checked against 4.7.3) · PX4 1.18 (parameters checked against v1.18.0)
status: published
tags:
  - DroneCAN
  - CAN
  - AP_Periph
  - peripherals
related:
  - el-peripherals
  - emb-protocols
  - el-emi
  - ap-heavy
next:
  - el-redundancy
source: content/electronics/el-dronecan.md
source_hash: 71f82072f9b0
---

## summary
On a 5" quad everything lives on UART and I²C. On an X8, a VTOL, or any aircraft with wire runs longer than half a meter, that ends in interference, a shortage of ports and "the GPS drops out at full throttle". DroneCAN moves the GPS, compass, current sensor, rangefinders, airspeed and even the ESCs onto one four-wire differential bus. This module is the system level on top of "Connecting peripherals" and "Protocols": the bus physics and how to check it with a multimeter, node IDs and their dynamic allocation (DNA), ArduPilot and PX4 setup, ESCs over CAN and the bus load budget, node firmware updates, and AP_Periph: how to turn an STM32 board into your own node.

## theory
### Why a bus when you have UART
- **Noise immunity.** CAN is a differential pair: interference couples equally into both wires, and the receiver looks at the difference. A meter of wire next to the X8 power bus is normal for CAN and guaranteed errors for I²C.
- **One port, many devices.** GPS, compass, current sensor, rangefinder, airspeed and 8 ESCs on one bus, through a splitter.
- **Telemetry and diagnostics for free.** Every node reports on itself (`NodeStatus`: health, mode, uptime), and node firmware can be updated from the ground station.
- **Redundancy.** Two CAN ports on the flight controller are two independent buses; critical nodes are duplicated.

The price: more expensive peripherals, slightly more complex setup, and the bus has to be built correctly at the physical level.

### Bus physics
- Bit rate 1 Mbit/s: the ArduPilot and PX4 default and the highest of the bit rates the specification recommends (the specification itself is bit rate agnostic; at 1 Mbit/s the bus may be up to 40 m long with stubs up to 0.3 m). On an aircraft it is a few meters, so this is not a limit.
- **120 Ω terminators at the two ends** of the bus, and only at the two ends. Check with the power off: a multimeter between CAN_H and CAN_L should read **~60 Ω** (two 120 Ω in parallel). 120 Ω means one terminator, open circuit means none, 40 Ω means three.
- **Dronecode/Pixhawk connector**: JST-GH 4-pin; 1: +5 V, 2: CAN_H, 3: CAN_L, 4: GND. The H/L pair is twisted.
- **The topology is a line**, not a star: short stubs off the main bus. Splitters (CAN hubs) form the "line" internally.
- Bus power: the 5 V from the flight controller is current-limited; a GPS with a compass and a couple of sensors is fine, but ESCs and servos are powered separately.

### DroneCAN on top of CAN
DroneCAN (formerly UAVCAN v0) defines **what** travels in the frames: the 29-bit frame identifier carries the priority, the message type and the source node ID; long messages are split across several frames. The node ID is 1…127 (the specification reserves 126 and 127 for debugging tools, so dynamic allocation hands out no more than 125); the flight controller is usually 10 in ArduPilot (`CAN_D1_UC_NODE`) and 1 in PX4 (`UAVCAN_NODE_ID`).

**DNA (dynamic node allocation)**: a new node without an ID requests one from the server, and the flight controller hands out a free ID and remembers it against the node's unique ID. That is why peripherals "just plug in and work". It breaks when nodes are moved between aircraft or settings are copied: two nodes with the same stored ID are a conflict. The cure is clearing the DNA database on the flight controller or a fixed ID on the node.

{{diagram:dronecan-dna-flow|The node ID is bound to the node's unique ID in the flight controller's database: a moved or copied node produces a duplicate ID and "Duplicate Node"; the cure is clearing the database with bit 0 of CAN_D1_UC_OPTION or a fixed ID.}}

Cyphal (UAVCAN v1) is the next, incompatible version of the protocol; ArduPilot and most peripherals use DroneCAN, and PX4 supports both. When buying peripherals, check that they speak DroneCAN.

### ArduPilot setup
| What | Parameters | Value |
|---|---|---|
| Enable the CAN1 port | `CAN_P1_DRIVER` | 1 (First driver) |
| Protocol of driver 1 | `CAN_D1_PROTOCOL` | 1 = DroneCAN |
| Bit rate | `CAN_P1_BITRATE` | 1000000 |
| GPS over CAN | `GPS1_TYPE` (before 4.6: `GPS_TYPE`) | 9 = DroneCAN |
| Current sensor | `BATT_MONITOR` | 8 = DroneCAN-BatteryInfo |
| Rangefinder | `RNGFND1_TYPE` | 24 = DroneCAN |
| ESCs over CAN | `CAN_D1_UC_ESC_BM` | bitmask of the outputs sent onto the bus as ESC commands |
| Servos over CAN | `CAN_D1_UC_SRV_BM` (0), `CAN_D1_UC_SRV_RT` (50 Hz) | mask of the outputs sent onto the bus as `actuator.ArrayCommand`; the 1000–2000 µs pulse after `SERVOn_MIN/TRIM/MAX` is scaled to −1…1 (bit 4 of `UC_OPTION` sends the microseconds themselves) |
| ID of the flight controller itself | `CAN_D1_UC_NODE` | 10 by default, 1–125; must not match the fixed ID of any node |
| Driver options | `CAN_D1_UC_OPTION` (0) | bit 0 (1): ClearDNADatabase at boot (clears itself, message `UC DNA database reset`); 1 (2): IgnoreDNANodeConflicts (do not block arming on a duplicate ID); 2 (4): EnableCanfd; 3 (8): IgnoreDNANodeUnhealthy (do not block arming on an unhealthy node); 4 (16): SendServoAsPWM; 5 (32): SendGNSS (broadcast GNSS on the bus); 6 (64): UseHimarkServo; 7 (128): HobbyWingESC; 8 (256): EnableStats; 9 (512): EnableFlexDebug; 10 (1024): SecondaryAllowExtendedFrames (extended frames for the secondary protocol, `CAN_D1_PROTOCOL2`) |

A node's compass is picked up automatically (it appears in the compass list). Reboot after changing `CAN_*`. In Mission Planner, Setup → Optional Hardware → DroneCAN/UAVCAN shows the nodes, their parameters and firmware update; the same page has the SLCAN mode, which turns the flight controller into a USB-CAN adapter for the DroneCAN GUI Tool.

### PX4 setup
PX4 1.18 (checked against `uavcan_params.yaml` and `module.yaml` v1.18.0). By default `UAVCAN_ENABLE` = 0: the bus driver is not started, and a CAN GPS stays silent even if it works. Choosing the value:

| `UAVCAN_ENABLE` | What it enables | When to choose it |
|---|---|---|
| 0 (default) | nothing (Disabled) | CAN is not used |
| 1 | Sensors Manual Config: sensors, node IDs set by hand, no DNA and no node firmware update | nodes with fixed node IDs |
| 2 | Sensors Automatic Config: sensors, the flight controller allocates IDs (DNA) and updates node firmware | the usual choice for GPS, compass, current sensor |
| 3 | Sensors and Actuators (ESCs) Automatic Config: the same plus ESC and servo outputs over CAN | ESCs or servos on the bus |

The rest needs a reboot after each change: `UAVCAN_NODE_ID` = 1 (the flight controller's ID), `UAVCAN_BITRATE` = 1 000 000 bit/s, which must match the bit rate of the nodes. Default subscriptions: only `UAVCAN_SUB_GPS`, `UAVCAN_SUB_GPS_R` and `UAVCAN_SUB_MAG` are enabled (= 1); the current sensor (`UAVCAN_SUB_BAT`), baro, rangefinder, airspeed, flow and the rest are 0 and must be enabled by hand, otherwise the node is visible but no data comes from it. The flight controller forwards RTK corrections to a CAN GPS only with `UAVCAN_PUB_RTCM` = 1 (default 0; RTK is covered in `nav-rtk`). With value 3 the Actuators screen shows the `UAVCAN_EC_FUNCn` outputs (ESC 1…12, command 1…8191) and `UAVCAN_SV_FUNCn` (servos 1…15, 0…1000, disarmed 500); functions are assigned the same way as for PWM outputs. Check in the console: `uavcan status` lists the nodes and the error counters. The full `UAVCAN_*` table and the "node not visible" troubleshooting are in `px4-hardware-peripherals`.

### ESCs over CAN and bus load
The ESC command (`esc.RawCommand`) carries 14 bits per motor: for 8 motors that is 14 bytes of payload, a multi-frame transfer of ~3 frames. At 400 Hz that is ~1200 frames/s. A CAN frame with 8 data bytes and an extended identifier is ~130–150 bits with bit stuffing, so at 1 Mbit/s the bus carries ~7000 frames/s. The ESC commands take ~15–20 %, plus the ESC telemetry coming back, the GPS, the compass and the current sensor. Rule: keep bus load below ~50 %, and put the ESCs and the navigation sensors on different buses if there are many nodes.

### AP_Periph: your own node
AP_Periph is ArduPilot firmware that turns an STM32 board (your own or an off-the-shelf one: GPS modules, "CAN adapters") into a DroneCAN node. It uses the same hwdef as flight controllers, and the node runs ArduPilot drivers: GPS, compass, baro, rangefinders, airspeed, LEDs, up to an ESC bridge from CAN to PWM/DShot (the node receives ESC commands from the bus and outputs them to ordinary ESCs). This is the path when you need a CAN sensor that you cannot buy.

{{diagram:dronecan-bus|DroneCAN on an aircraft: a linear bus with 120 Ω terminators at the ends; the flight controller allocates node IDs (DNA), with GPS, current sensor and ESCs on one pair of wires.}}

### Where it fits in the system

- **Takes in:** 5 V from the flight controller, current-limited (`el-power-design`); the connector, pinout and general connection rules (`el-peripherals`); motor commands if the ESCs are on the bus (`f-motors-esc`).
- **Puts out:** GPS position and the compass field to state estimation (`est-gnss`); battery current and voltage to the battery failsafe (`ap-safety-fs`); range to the altitude sources (`est-alt-sources`); a second bus to redundancy (`el-redundancy`).
- **If you get this wrong:** one or three terminators on the bus (120 or 40 Ω instead of ~60) → frames are lost, the GPS and compass drop out, and the EKF is left without a position (`nav-resilience`). Nodes moved between aircraft → two nodes with the same stored ID, and the sensor is not visible; the cure is clearing the DNA database, and before flight ArduPilot catches it with the pre-arm message "Duplicate Node" (the pre-arm mechanism is in `ap-safety-fs`).

## practice
### Step 1. Check the bus with the power off
Build the bus: flight controller → splitter → GPS/compass → current sensor (or any two nodes). Multimeter between CAN_H and CAN_L with the power off: record the resistance. Expect 55–65 Ω. Deliberately remove one terminator: 120 Ω; this is the most common cause of "the node comes and goes".

### Step 2. Setup and nodes
ArduPilot: `CAN_P1_DRIVER = 1`, `CAN_D1_PROTOCOL = 1`, `GPS1_TYPE = 9`, reboot. In Mission Planner (DroneCAN/UAVCAN): the list of nodes with node ID, name, mode and health. Record the node table. In the log: the GPS and compass messages from the node, `BAT` from the current sensor.

PX4: `UAVCAN_ENABLE` = 2, plus `UAVCAN_SUB_BAT` = 1 for the current sensor, reboot. In the MAVLink Console, `uavcan status` shows the nodes with their IDs and state; the data comes from `listener sensor_gps` and `listener battery_status`. A node in `uavcan status` but no topic means its `UAVCAN_SUB_*` subscription is off.

### Step 3. DroneCAN GUI Tool
SLCAN through the flight controller (or a USB-CAN adapter): DroneCAN GUI Tool → bus monitor. See each node's `NodeStatus`, the GNSS and magnetometer message rates, and the bus load. Compare with the estimate from the theory.

### Step 4. Conflict and recovery
Simulate "a node from another aircraft": give a node a fixed node ID that matches another node. Watch what disappears. Recover: restore automatic allocation, clear the DNA database (`CAN_D1_UC_OPTION = 1`, reboot: `UC DNA database reset` in Messages, and the bit clears itself), restart the bus. Until the duplicate is fixed, arming is blocked with `PreArm: DroneCAN: Duplicate Node …`; bits 1 and 3 lift the block but not the cause, so do not set them. Write down the procedure as an instruction for your aircraft's logbook.

### Step 5 (optional). Node firmware update
Through Mission Planner or the DroneCAN GUI Tool, update the firmware of one node (on the bench only, with a backup of the node's parameters). Record the versions before and after.

Self-check: the lab is done when the bus has been checked with a multimeter (55–65 Ω between CAN_H and CAN_L with the power off), every node is visible in the GCS with its node ID and produces messages in the log, the bus load has been measured and compared with the theory estimate (ESC commands at 400 Hz ~15–20 %, the whole bus below ~50 %), and the recovery procedure after an ID conflict is written down and has worked: after clearing the DNA database and rebooting, both nodes are back in the list.

**Reference answer for self-check.** Multimeter: ~60 Ω means two terminators, 120 Ω one, 40 Ω three, open circuit none. Node table: in ArduPilot the flight controller usually has node ID 10, automatically allocated IDs are no higher than 125, and there are no duplicate IDs. The conflict in step 4: the sensor of the node with the matching ID disappears, and ArduPilot shows the pre-arm "Duplicate Node" before flight. Common wrong results: a node that "comes and goes" with correct parameters means one terminator on the bus; no nodes at all means no reboot after changing `CAN_*`.

## diagnostics
- **Symptom:** a node appears and disappears
  - Possible cause: no terminator or three of them, a bad contact in a JST-GH, a star instead of a line.
  - What to do: 60 Ω between H and L with the power off, check the connectors, rework the topology.
- **Symptom:** no nodes visible at all
  - Possible cause: `CAN_P1_DRIVER` or `CAN_D1_PROTOCOL` not set, no reboot, no 5 V on the bus.
  - What to do: parameters, reboot, voltage on pin 1 of the connector.
- **Symptom:** two GPS units "flicker" and the data jumps
  - Possible cause: a node ID conflict after moving a node from another aircraft.
  - What to do: clear the DNA database, restore automatic ID allocation.
- **Symptom:** motors on CAN twitch at high RPM
  - Possible cause: the bus load is close to the limit, the ESC command rate is too high for the number of nodes.
  - What to do: measure the load in the DroneCAN GUI Tool, move the ESCs to a separate CAN2 bus.
- **Symptom:** the node is visible but the EKF has no data
  - Possible cause: the device type is not selected (`GPS1_TYPE`, `BATT_MONITOR`, `RNGFND1_TYPE`).
  - What to do: set the DroneCAN type for the sensor, reboot.

## references
- ArduPilot — CAN Bus Setup (DroneCAN) | https://ardupilot.org/copter/docs/common-canbus-setup-advanced.html | primary | A
- DroneCAN — Specification | https://dronecan.github.io/Specification/1._Introduction | primary | A
- ArduPilot — AP_Periph (DroneCAN peripherals) source | https://github.com/ArduPilot/ardupilot/tree/master/Tools/AP_Periph | primary | A
- PX4 — DroneCAN (docs in the v1.18.0 tree) | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/docs/en/dronecan/index.md | primary | A

## checklist
- I can explain when DroneCAN is better than UART/I²C
- I check the bus with a multimeter: 60 Ω between H and L with the power off
- I know the Dronecode connector and the "line" topology
- I understand node IDs and DNA and can resolve an ID conflict
- I set up DroneCAN in ArduPilot and PX4 and choose the sensor type
- I estimate the bus load for ESCs over CAN
- I know what AP_Periph is and when to build my own node
