---
id: el-kicad
title: "Board design in KiCad: from schematic to order, layout for EMC"
level: L3
readingTime: 45 min
firmware: KiCad 8+ · ArduPilot 4.7 (checked against 4.7.3) (board testing)
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
source_hash: 7687ded27739
---

## summary
A top-level engineer is not limited to what is on sale: when you need a 100 A current sensor on I²C, a power board for a specific frame, or a companion adapter with the right connectors, you draw the board yourself. This module walks you through the full KiCad cycle on a real example, a current sensor board built around an INA226 with a shunt: calculating the shunt and the calibration register, the schematic and the ERC check, footprints, layout for current (trace width per IPC-2221) and for electromagnetic compatibility, DRC against the fab's capabilities, the manufacturing output files, and testing the finished board on a flight controller.

## theory
### When to make your own board
- The board you need does not exist, or it does not fit in size, connectors or current.
- Many identical aircraft: your own power and distribution board removes hand-soldered wiring, the main source of failures in the field (the "Wiring" module).
- Learning value: layout forces you to understand where interference on the compass and gyro comes from.

What not to do: a flight controller from scratch as your first project; that means high-speed layout, an IMU, certified firmware. Start with peripherals.

### The KiCad cycle
1. **Schematic** (Schematic Editor): symbols, connections, net names, values. **ERC** (electrical rules check) catches unconnected pins, two outputs on one net, a forgotten power source (`PWR_FLAG` flags).
2. **Footprints**: every symbol gets a package (0603, SOT-23-6, MSOP-10, a JST-GH connector). A footprint error is the most expensive kind: the board arrives and the chip does not fit.
3. **Layout** (PCB Editor): board outline, layer stackup, component placement, traces, zones, vias.
4. **DRC** (design rules check): the fab's rules: minimum trace width and clearance, holes, edge clearances.
5. **Output**: Gerber files for the layers, a drill file, a BOM (bill of materials), a component placement file for automated assembly; the 3D viewer to check packages and connectors.

{{diagram:kicad-design-flow|Each check (ERC, DRC, the 3D viewer) sends you back to the step where the error was made when it fails; the fab's rules are loaded into Board Setup before layout.}}

### Example: a current sensor on the INA226
The INA226 is a digital current and voltage monitor on I²C: it measures the drop across a shunt (range ±81.92 mV, LSB 2.5 µV) and the bus voltage (up to 36 V, i.e. up to 8S), and calculates current and power.
- **Shunt.** Maximum current 100 A with a range of 81.92 mV → R ≤ 0.82 mΩ; take 0.5 mΩ: 50 mV at 100 A, with margin. Power in the shunt, I²R: 5 W at 100 A, 0.8 W at 40 A continuous, so use a 2512 package or two shunts in parallel, with wide copper pads to carry the heat away.
- **Resolution.** An LSB of 2.5 µV / 0.5 mΩ = 5 mA; it will not get any finer. Calibration register: CAL = 0.00512 / (Current_LSB · R_shunt) = 0.00512 / (0.005 · 0.0005) = 2048.
- **Support components.** 100 nF at the supply pin, I²C pull-ups (usually already on the flight controller, so do not duplicate them without need), the address set by pins A0/A1, a TVS diode on the battery bus, an I²C connector with the Dronecode pinout (JST-GH).
- **In the flight controller.** ArduPilot: `BATT_MONITOR` set to the INA2xx type, the I²C bus and address (`BATT_I2C_BUS`, `BATT_I2C_ADDR`), the maximum current and shunt resistance set with the INA2xx driver parameters of your version; verify by comparing with a clamp meter (the "Measurements" module).

### Layout for current
- Trace width for current per IPC-2221: I = k·ΔT^0.44·A^0.725 (external layer k = 0.048, A is the cross-section in mil²). For 1 oz copper (35 µm) and a +10 °C rise: 2 A needs ~0.8 mm, 5 A ~2.8 mm, 10 A ~7.2 mm. Tens of amps are not carried by a trace: use zones on both sides, 2 oz copper, rows of vias, and wires and busbars soldered to the pads.
- **Kelvin connection of the shunt**: the sense traces to the INA226 leave from the middle of the shunt pads as a separate pair, not from the power trace; otherwise the drop in the copper is added to the measurement.

{{diagram:chart-trace-width|External trace width versus current per IPC-2221: 1 oz and 2 oz copper at a 10 °C rise and 1 oz at 20 °C.}}

### Layout for EMC
- **Solid ground.** On a 4-layer board: signal, ground, power, signal. The return current flows in the ground under its own trace; a slot in the zone under a trace makes an antenna.
- **Keep high-current loops short.** In a buck converter the input capacitor sits right next to the switch and the diode/low-side switch: the loop with the fast current is the main radiator on the board.
- **Keep sensitive circuits separate.** IMU, compass, analog measurements go away from converters and power buses; a compass on a board that carries current is a bad idea (the "Interference" module).
- **Differential pairs** (CAN, USB): two traces side by side, of equal length, over solid ground; the 120 Ω CAN terminator goes on the node at the end of the bus.
- **Connectors**: ESD protection at external connectors, a keyed connector against reverse polarity, standard pinouts.

### Fab capabilities
Cheap two-layer boards: trace and clearance from ~0.127–0.15 mm, holes from ~0.3 mm, 1 or 2 oz copper. Load the specific fab's rules into Board Setup before layout, so that DRC checks exactly those.

### Where it fits in the system

- **Takes in:** the maximum current and bus voltage (`el-power-design`); the I²C and CAN pinouts (`el-peripherals`, `el-dronecan`); placement rules for interference sources and sensitive circuits (`el-emi`).
- **Puts out:** battery current and voltage over I²C to `BATT_MONITOR`, from which the consumed mAh is calculated and the battery failsafe is triggered (`f-power`, `ap-safety-fs`); a board that replaces hand-soldered wiring (`el-wiring`).
- **If you get this wrong:** sense traces not taken Kelvin-style, or the wrong shunt resistance set → the current reading is wrong, the mAh in the log differs from the charger by more than ±10 %, and the flight time is calculated wrongly (`f-power`; clamp-meter check in `el-measure`). A large converter loop or a slotted ground → the board radiates, and the compass and GPS suffer (`el-emi`).

## practice
### Step 1. Calculation
For your aircraft: the maximum and continuous current, the battery voltage. Choose the shunt (INA226 range, power, package), calculate the resolution and the calibration register, and the width of the power traces (or decide that the current runs through wires soldered to the shunt pads).

### Step 2. Schematic and ERC
A new KiCad project. INA226, shunt, 100 nF, TVS, a power connector and an I²C connector (JST-GH, 4 pins: +5 V, SCL, SDA, GND). Choose the address. ERC with no errors; explain or fix every warning.

### Step 3. Layout and DRC
A two-layer board: the shunt power pads on both sides with vias, a Kelvin pair to the INA226, a ground zone on the bottom, the I²C connector at the edge. Load the chosen fab's rules, DRC with no errors. Check the 3D viewer.

### Step 4. Output files
Gerbers and drill file, BOM, placement file. Open the Gerbers in KiCad's built-in viewer (Gerber Viewer) and check every layer: outline, mask, silkscreen, holes. Ordering the board is optional.

### Step 5. Testing the finished board (if assembled)
Before connecting a battery: check for shorts, and test the supply from a bench power supply with current limiting. Connect it to the flight controller, find the device on the I²C bus, set up the battery monitor, compare the current with a clamp meter at three loads. Record the error.

Self-check: the lab is done when the shunt, calibration and trace calculation, with the inputs from the example plugged in, gives its numbers (100 A and 0.5 mΩ → 50 mV, 5 W, a 5 mA step, CAL = 2048), and for your aircraft the shunt drop at maximum current is below 81.92 mV; the schematic passes ERC with no errors, the board passes DRC with no errors under the loaded fab rules, and every layer of the output files has been checked in the Gerber Viewer; if the board is assembled, the current error against the clamp meter has been measured at three loads and recorded.

**Reference answer for self-check.** Check the trace widths against the IPC-2221 guideline values from the theory (1 oz, +10 °C): 2 A needs ~0.8 mm, 5 A ~2.8 mm, 10 A ~7.2 mm; tens of amps go through zones on both sides or wires soldered to the pads, not through a trace. The current resolution cannot be better than the 2.5 µV LSB / shunt R. Common wrong results: CAL differs from the expected value by a factor of a thousand, meaning the shunt resistance was entered in milliohms instead of ohms; ERC complains about power, meaning a forgotten `PWR_FLAG`; on the assembled board the current reads high against the clamp meter, meaning the sense traces were taken from the power trace instead of a Kelvin pair from the shunt pads, or the driver has the wrong shunt resistance set.

## diagnostics
- **Symptom:** the current reading has a constant error that grows with current
  - Possible cause: not a Kelvin measurement; the drop in the copper gets into the reading.
  - What to do: sense pair from the shunt pads; refine the calibration against a reference.
- **Symptom:** the device is not found on I²C
  - Possible cause: wrong address on A0/A1, no pull-ups, SDA/SCL swapped in the connector.
  - What to do: check the address, the pull-ups, and the pinout against Dronecode.
- **Symptom:** the shunt or the traces get very hot
  - Possible cause: I²R power underestimated, narrow traces, too little copper.
  - What to do: a higher-power package or parallel shunts, zones, 2 oz, wires to the pads.
- **Symptom:** after installing the board the compass jumps or the gyro is noisy
  - Possible cause: power currents and a converter next to the sensors, a slotted ground.
  - What to do: separate them, short current loops, solid ground, compass on a mast.
- **Symptom:** the chip does not fit the board
  - Possible cause: the wrong footprint (package, pin pitch).
  - What to do: check the footprint against the datasheet before ordering; print the board 1:1 and lay the components on it.

## references
- KiCad — documentation | https://docs.kicad.org/ | primary | A
- Texas Instruments — INA226 datasheet | https://www.ti.com/lit/ds/symlink/ina226.pdf | primary | A
- Dronecode — Pixhawk Connector Standard (DS-009) | https://github.com/pixhawk/Pixhawk-Standards/blob/master/DS-009%20Pixhawk%20Connector%20Standard.pdf | primary | A
- ArduPilot — Power monitors and battery setup | https://ardupilot.org/copter/docs/common-powermodule-landingpage.html | primary | A
- Texas Instruments — PCB layout guidelines for switching power supplies (SNVA021) | https://www.ti.com/lit/an/snva021c/snva021c.pdf | primary | B

## checklist
- I know when to make my own board and when to buy a ready-made one
- I go through the KiCad cycle: schematic, ERC, footprints, layout, DRC, output files
- I calculate the shunt, resolution and calibration for the INA226
- I choose the trace width for current and make a Kelvin connection
- I lay out the board with EMC in mind: ground, current loops, sensitive circuits
- I test the finished board before connecting it to the aircraft
