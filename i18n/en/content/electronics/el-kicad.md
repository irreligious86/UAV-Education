---
id: el-kicad
title: "Board design in KiCad: from schematic to order, layout for EMC"
level: L3
readingTime: 45 min
firmware: KiCad 8+ · ArduPilot 4.5+ (board testing)
status: published
tags:
  - KiCad
  - PCB
  - layout
  - EMC
related:
  - el-power-design
  - el-emi
  - el-measure
  - emb-protocols
next:
  - ap-heavy
source: content/electronics/el-kicad.md
source_hash: e53578687db9
---

## summary
A “top”-level engineer isn't limited to what's for sale: if you need a 100 A current sensor with I²C, a power board for a specific frame, an adapter for the companion with the right connectors, you draw the board yourself. This module takes you through the full cycle in KiCad on a real example — an INA226 current sensor board with a shunt: calculating the shunt and the calibration register, the schematic and the ERC check, footprints, layout with current in mind (trace width per IPC-2221) and electromagnetic compatibility, DRC for the fab's capabilities, output files for manufacturing, and testing the finished board on a flight controller.

## theory
### When to make your own board
- The board you need doesn't exist, or doesn't fit in size, connectors or current.
- Many identical vehicles: your own power and distribution board removes hand-soldered wiring — the main source of failures in the field (module “Wiring”).
- Educational value: layout forces you to understand where interference on the compass and gyro comes from.

Don't: a flight controller from scratch as your first project — that means high-speed layout, an IMU, certified firmware; start with peripherals.

### The KiCad cycle
1. **Schematic** (Schematic Editor): symbols, connections, net names, component values. **ERC** (electrical rules check) catches unconnected pins, two outputs on one net, forgotten power (`PWR_FLAG` flags).
2. **Footprints**: each symbol gets a package (0603, SOT-23-6, MSOP-10, a JST-GH connector). A footprint error is the most expensive one: the board arrives and the chip doesn't fit.
3. **Layout** (PCB Editor): board outline, layer stackup, component placement, traces, copper pours, vias.
4. **DRC** (design rules check) — the fab's rules: minimum trace width and clearance, holes, edge clearances.
5. **Output**: Gerber files for the layers, a drill file, a BOM (bill of materials), a position file for automated assembly; a 3D view to check packages and connectors.

### Example: an INA226 current sensor
The INA226 is a digital current and voltage monitor over I²C: it measures the drop across a shunt (±81.92 mV range, 2.5 µV step) and the bus voltage (up to 36 V — up to 8S), and computes current and power.
- **Shunt.** Maximum current 100 A with an 81.92 mV range → R ≤ 0.82 mΩ; take 0.5 mΩ: 50 mV at 100 A, with margin. Power in the shunt, I²R: 5 W at 100 A, 0.8 W at 40 A continuous — a 2512 package or two shunts in parallel, wide copper pads for heat dissipation.
- **Resolution.** A 2.5 µV step / 0.5 mΩ = 5 mA — it won't get more precise than that. The calibration register: CAL = 0.00512 / (Current_LSB · R_shunt) = 0.00512 / (0.005 · 0.0005) = 2048.
- **Support components.** 100 nF at the supply pin, I²C pull-ups (usually already on the flight controller — don't duplicate them without need), the address set by pins A0/A1, a TVS diode on the battery rail, an I²C connector with the Dronecode pinout (JST-GH).
- **In the flight controller.** ArduPilot: `BATT_MONITOR` — INA2xx type, the I²C bus and address (`BATT_I2C_BUS`, `BATT_I2C_ADDR`), the maximum current and shunt resistance — via the INA2xx driver parameters for your version; to verify, compare with a clamp ammeter (module “Measurements”).

### Layout for current
- Trace width for a given current per IPC-2221: I = k·ΔT^0.44·A^0.725 (outer layer k = 0.048, A is the cross-section in mil²). For 1 oz copper (35 µm) and a +10 °C rise: 2 A — ~0.8 mm, 5 A — ~2.8 mm, 10 A — ~7.2 mm. Tens of amps are not carried by a trace: pours on both sides, 2 oz copper, rows of vias, wires and bus bars soldered to pads.
- **Kelvin connection of the shunt**: the sense traces to the INA226 leave from the middle of the shunt pads as a separate pair, not from the power trace — otherwise the drop across the copper adds to the measurement.

{{diagram:chart-trace-width|Outer-layer trace width vs. current per IPC-2221: 1 oz and 2 oz copper at a 10 °C rise and 1 oz at 20 °C.}}

### Layout for EMC
- **Solid ground.** On a 4-layer board: signal — ground — power — signal. The current returns along the ground directly under its trace; a slot in the pour under a trace is an antenna.
- **Keep high-current loops short.** In a buck converter, the input capacitor goes right next to the switch and the diode/low-side switch: the loop with fast current is the main radiator on the board.
- **Sensitive circuits apart.** IMU, compass, analog measurements — away from converters and power rails; a compass on a board with current is a bad idea (module “Interference”).
- **Differential pairs** (CAN, USB) — two traces side by side, equal length, over solid ground; the 120 Ω CAN terminator goes on the end node of the bus.
- **Connectors**: ESD protection at external connectors, a keyed connector against reverse polarity, standard pinouts.

### Fab capabilities
Cheap two-layer boards: trace and clearance from ~0.127–0.15 mm, holes from ~0.3 mm, 1 or 2 oz copper. Load the specific fab's rules into Board Setup before layout — DRC then checks exactly those.

## practice
### Step 1. Calculation
For your vehicle: maximum and continuous current, battery voltage. Pick a shunt (INA226 range, power, package), calculate the resolution and the calibration register, the width of the power traces (or decide that the current runs through wires soldered to the shunt pads).

### Step 2. Schematic and ERC
A new KiCad project. INA226, shunt, 100 nF, TVS, a power connector and an I²C connector (JST-GH, 4 pins: +5 V, SCL, SDA, GND). Choose the address. ERC with no errors; explain or fix every warning.

### Step 3. Layout and DRC
A two-layer board: the shunt's power pads on both sides with vias, a Kelvin pair to the INA226, a ground pour on the bottom, the I²C connector at the edge. Load the chosen fab's rules, DRC with no errors. Check the 3D view.

### Step 4. Output files
Gerber and drill files, BOM, position file. Open the Gerbers in KiCad's built-in viewer (Gerber Viewer) and check every layer: outline, mask, silkscreen, holes. Ordering the board is optional.

### Step 5. Testing the finished board (if built)
Before connecting a battery — a continuity check for shorts, a power-up from a bench supply with current limiting. Connect it to the flight controller, find the device on the I²C bus, set up the battery monitor, compare the current with a clamp meter at three loads. Record the error.

The lab counts when the shunt, calibration and trace calculations are done, the schematic passes ERC, the board passes DRC with the fab's rules, and the output files are checked in the viewer; if the board is built — the current error is measured.

## diagnostics
- **Symptom:** the current reading has a constant error that grows with current
  - Possible cause: no Kelvin measurement — the drop across the copper gets into the reading.
  - What to do: a sense pair from the shunt pads; refine the calibration against a reference.
- **Symptom:** the device isn't found on I²C
  - Possible cause: wrong address via A0/A1, no pull-ups, SDA/SCL swapped in the connector.
  - What to do: check the address, the pull-ups, the pinout against Dronecode.
- **Symptom:** the shunt or traces get very hot
  - Possible cause: underestimated I²R power, narrow traces, too little copper.
  - What to do: a higher-power package or parallel shunts, pours, 2 oz, wires to the pads.
- **Symptom:** after installing the board the compass jumps or the gyro gets noisy
  - Possible cause: power currents and a converter next to the sensors, a slot in the ground.
  - What to do: separate them, short current loops, solid ground, compass on a mast.
- **Symptom:** the chip doesn't fit on the board
  - Possible cause: wrong footprint (package, pin pitch).
  - What to do: check the footprint against the datasheet before ordering; print the board at 1:1 and lay the components on it.

## references
- KiCad — documentation | https://docs.kicad.org/ | primary | A
- Texas Instruments — INA226 datasheet | https://www.ti.com/lit/ds/symlink/ina226.pdf | primary | A
- Dronecode — Pixhawk Connector Standard (DS-009) | https://github.com/pixhawk/Pixhawk-Standards/blob/master/DS-009%20Pixhawk%20Connector%20Standard.pdf | primary | A
- ArduPilot — Power monitors and battery setup | https://ardupilot.org/copter/docs/common-powermodule-landingpage.html | primary | A
- Texas Instruments — PCB layout guidelines for switching power supplies (SNVA021) | https://www.ti.com/lit/an/snva021c/snva021c.pdf | primary | B

## checklist
- I know when to make my own board and when to buy one
- I go through the KiCad cycle: schematic, ERC, footprints, layout, DRC, output files
- I calculate the shunt, the resolution and the INA226 calibration
- I choose the trace width for the current and make a Kelvin connection
- I lay out with EMC in mind: ground, current loops, sensitive circuits
- I test the finished board before connecting it to the vehicle
