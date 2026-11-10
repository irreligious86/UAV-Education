---
id: el-dronecan
title: "DroneCAN: the onboard CAN bus, nodes, ESCs and peripheral firmware"
level: L3
readingTime: 35 min
firmware: ArduPilot 4.5+ · PX4 1.15+
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
source_hash: 138698f95105
---

## summary
On a 5" quad everything lives on UART and I²C. On an X8, a VTOL or any vehicle with wires longer than half a meter, that ends in interference, a shortage of ports and “GPS drops out on throttle”. DroneCAN moves the GPS, compass, current sensor, rangefinders, airspeed and even ESCs onto a single four-wire differential bus. This module is the system level on top of “Connecting peripherals” and “Protocols”: bus physics and checking it with a multimeter, node IDs and their automatic allocation (DNA), ArduPilot and PX4 setup, ESCs over CAN and the bus load budget, updating node firmware, and AP_Periph — how to make your own node from an STM32 board.

## theory
### Why a bus when you have UART
- **Noise immunity.** CAN is a differential pair: interference couples into both wires equally, and the receiver looks at the difference. A meter of wire next to an X8 power bus is normal for CAN and guaranteed glitches for I²C.
- **One port, many devices.** GPS, compass, current sensor, rangefinder, airspeed, 8 ESCs — on one bus, through a splitter.
- **Telemetry and diagnostics for free.** Every node reports on itself (`NodeStatus`: health, mode, uptime), and the node firmware can be updated from the ground station.
- **Redundancy.** Two CAN ports on the flight controller mean two independent buses; critical nodes are duplicated.

The price: more expensive peripherals, slightly more complex setup, and the bus has to be built correctly physically.

### Bus physics
- 1 Mbit/s (the DroneCAN standard). The longer the bus, the stricter the requirements; on a vehicle it's a few meters, which is not a limitation.
- **120 Ω terminators at both ends** of the bus, and only at both ends. Check with the power off: a multimeter between CAN_H and CAN_L should show **~60 Ω** (two 120 Ω in parallel). 120 Ω means one terminator, infinity means none, 40 Ω means three.
- **Dronecode/Pixhawk connector**: JST-GH 4 pin — 1: +5 V, 2: CAN_H, 3: CAN_L, 4: GND. The H/L pair is twisted.
- **Topology is a line**, not a star: short stubs off the trunk. Splitters (CAN hub/splitter) make the “line” internally.
- Power over the bus: the 5 V from the flight controller is current-limited — a GPS with compass and a couple of sensors are fine, ESCs and servos are powered separately.

### DroneCAN on top of CAN
DroneCAN (formerly UAVCAN v0) defines **what** goes in the frames: the 29-bit frame identifier carries the priority, the message type and the sender's node ID; long messages are split across several frames. The node ID is 1…127; the flight controller is usually 10 in ArduPilot (`CAN_D1_UC_NODE`) and 1 in PX4 (`UAVCAN_NODE_ID`).

**DNA (dynamic node allocation)**: a new node without an ID asks the server for one, and the flight controller hands out a free one and remembers it by the node's unique ID. That's why peripherals “just plug in and work”. It breaks when nodes are moved between vehicles or settings are copied: two nodes with the same stored ID means a conflict. The fix is clearing the DNA table on the flight controller or a fixed ID on the node.

Cyphal (UAVCAN v1) is the next, incompatible version of the protocol; ArduPilot and most peripherals use DroneCAN, PX4 supports both. When buying peripherals, check that they speak DroneCAN.

### ArduPilot setup
| What | Parameters | Value |
|---|---|---|
| Enable port CAN1 | `CAN_P1_DRIVER` | 1 (first driver) |
| Driver 1 protocol | `CAN_D1_PROTOCOL` | 1 = DroneCAN |
| Bitrate | `CAN_P1_BITRATE` | 1000000 |
| GPS over CAN | `GPS1_TYPE` (before 4.6 — `GPS_TYPE`) | 9 = DroneCAN |
| Current sensor | `BATT_MONITOR` | 8 = DroneCAN |
| Rangefinder | `RNGFND1_TYPE` | 24 = DroneCAN |
| ESCs over CAN | `CAN_D1_UC_ESC_BM` | bitmask of the outputs sent to the bus as ESC commands |

The node's compass is picked up automatically (it shows up in the compass list). After changing `CAN_*`, reboot. In Mission Planner: Setup → Optional Hardware → DroneCAN/UAVCAN shows the nodes, their parameters and firmware update; that's also where SLCAN mode is, which turns the flight controller into a USB-CAN adapter for DroneCAN GUI Tool.

### PX4 setup
`UAVCAN_ENABLE`: 2 — sensors, 3 — sensors and ESCs; after that, nodes are discovered automatically, and which data to accept is chosen with the `UAVCAN_SUB_*` parameters. ESCs over CAN: `UAVCAN_ENABLE = 3`, then output mapping on the Actuators tab in QGC. The details differ between versions — check the DroneCAN section of the PX4 docs for your version.

### ESCs over CAN and bus load
The ESC command (`esc.RawCommand`) carries 14 bits per motor: for 8 motors that's 14 bytes of payload, i.e. a multi-frame message of ~3 frames. At 400 Hz that's ~1200 frames/s. A CAN frame with 8 data bytes and an extended identifier is ~130–150 bits with bit stuffing; at 1 Mbit/s the bus carries ~7000 frames/s. ESC commands take ~15–20 %, plus ESC telemetry coming back, GPS, compass, current sensor. Rule: keep the bus load below ~50 %, and put ESCs and navigation sensors on different buses if there are many nodes.

### AP_Periph: your own node
AP_Periph is ArduPilot firmware that turns an STM32 board (your own or an off-the-shelf one: GPS modules, “CAN adapters”) into a DroneCAN node. The same hwdef as flight controllers, and ArduPilot drivers run on the node: GPS, compass, baro, rangefinders, airspeed, LEDs, all the way up to a CAN → PWM/DShot ESC bridge (the node takes ESC commands from the bus and outputs them to ordinary ESCs). This is the way to go when you need a CAN sensor that isn't sold.

{{diagram:dronecan-bus|DroneCAN on a vehicle: a linear bus with 120 Ω terminators at the ends; the flight controller allocates node IDs (DNA), GPS, current sensor and ESCs on one pair of wires.}}

## practice
### Step 1. Check the bus with the power off
Build the bus: flight controller → splitter → GPS/compass → current sensor (or any two nodes). Multimeter between CAN_H and CAN_L with the power off: record the resistance. Expect 55–65 Ω. Deliberately remove one terminator — 120 Ω; that's the most common cause of “the node is there, then it isn't”.

### Step 2. Setup and nodes
ArduPilot: `CAN_P1_DRIVER = 1`, `CAN_D1_PROTOCOL = 1`, `GPS1_TYPE = 9`, reboot. In Mission Planner (DroneCAN/UAVCAN): the node list with node ID, name, mode and health. Write down the node table. In the log: the node's GPS and compass messages, `BAT` from the current sensor.

### Step 3. DroneCAN GUI Tool
SLCAN through the flight controller (or a USB-CAN adapter): DroneCAN GUI Tool → bus monitor. See each node's `NodeStatus`, the GNSS and magnetometer message rates, the bus load. Compare with the estimate from the theory.

### Step 4. Conflict and recovery
Simulate “a node from another vehicle”: give a node a fixed node ID that matches another node. Watch what disappears. Recover: restore automatic ID allocation, clear the DNA table, restart the bus. Write the procedure down as instructions for your vehicle's logbook.

### Step 5 (optional). Node firmware update
Through Mission Planner or DroneCAN GUI Tool, update the firmware of one node (on the bench only, with a backup of the node's parameters). Record the versions before and after.

The lab counts when the bus has been checked with a multimeter (60 Ω), the nodes are visible in the GCS and in the log, the bus load has been measured and compared with the estimate, and the recovery procedure after an ID conflict is written down.

## diagnostics
- **Symptom:** a node appears and disappears
  - Possible cause: no terminator or three of them, a bad contact in a JST-GH, a star instead of a line.
  - What to do: 60 Ω between H and L with the power off, check the connectors, rework the topology.
- **Symptom:** no nodes visible at all
  - Possible cause: `CAN_P1_DRIVER` or `CAN_D1_PROTOCOL` not set, no reboot, no 5 V on the bus.
  - What to do: parameters, reboot, voltage on pin 1 of the connector.
- **Symptom:** two GPS units “flicker”, the data jumps
  - Possible cause: a node ID conflict after moving a node from another vehicle.
  - What to do: clear the DNA table, restore automatic ID allocation.
- **Symptom:** CAN motors twitch at high RPM
  - Possible cause: bus load close to the limit, the ESC command rate too high for the number of nodes.
  - What to do: measure the load in DroneCAN GUI Tool, move the ESCs to a separate CAN2 bus.
- **Symptom:** the node is visible, but there is no data in the EKF
  - Possible cause: the device type is not selected (`GPS1_TYPE`, `BATT_MONITOR`, `RNGFND1_TYPE`).
  - What to do: set the DroneCAN type for the sensor you need, reboot.

## references
- ArduPilot — CAN Bus Setup (DroneCAN) | https://ardupilot.org/copter/docs/common-canbus-setup-advanced.html | primary | A
- DroneCAN — Specification | https://dronecan.github.io/Specification/1._Introduction | primary | A
- ArduPilot — AP_Periph (DroneCAN peripherals) source | https://github.com/ArduPilot/ardupilot/tree/master/Tools/AP_Periph | primary | A
- PX4 — DroneCAN | https://docs.px4.io/main/en/dronecan/ | primary | A

## checklist
- I can explain when DroneCAN beats UART/I²C
- I check the bus with a multimeter: 60 Ω between H and L with the power off
- I know the Dronecode connector and the “line” topology
- I understand node ID and DNA and can resolve an ID conflict
- I set up DroneCAN in ArduPilot and PX4 and select the sensor type
- I estimate the bus load for ESCs over CAN
- I know what AP_Periph is and when to build my own node
