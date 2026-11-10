---
id: el-power-design
title: "On-Board Power Circuit Design"
level: L2
readingTime: 35 min
firmware: any firmware
status: published
added: 2026-11-08
tags:
  - power
  - BEC
  - capacitor
  - protection
related:
  - f-power
  - el-measure
  - el-wiring
next:
  - el-measure
source: content/electronics/el-power-design.md
source_hash: 5ed30d1d2160
---

## summary
An aircraft has several power buses with different requirements: the motor power bus tolerates sags and ripple, but the flight controller, receiver, GPS and camera don't. This module teaches you to compute the currents per branch, pick a BEC by current and voltage, pick wire gauge by current and length, understand where sags and ripple come from and why a low-ESR capacitor on the bus isn't an option but part of the circuit. Separately — protection: smoke stopper, fuse, reverse polarity.

## theory
### Load map
Before choosing components, draw the power tree: battery → power bus → (ESC ×4…8, 5 V BEC, 9–12 V BEC) → loads. Typical currents:

{{diagram:power-tree|Power tree: from the battery to the power bus and separate BECs; each load with its own current.}}

| Load | Voltage | Typical current |
|---|---|---|
| FC + gyro | 5 V (3.3 internal) | 0.1–0.2 A |
| ELRS receiver | 5 V | 0.1–0.3 A (on-board TX module up to 0.5) |
| GPS with compass | 5 V (3.3) | 0.05–0.1 A |
| Digital video system (air unit) | 9–12 V | 0.5–1.2 A, higher peaks |
| Analog VTX 800 mW–1 W | 9–12 V / 5 V | 0.4–0.7 A |
| Servos (wing) | 5–6 V / 7.4 V | 0.5–1 A each while moving |
| Companion (Pi 4/5) | 5 V | 1–3 A, peaks up to 5 |
| Lighting/LEDs | 5 V | 0.06 A per LED |

Add them up with a 50% margin: a 5 V BEC on an aircraft with GPS, receiver and FC and no companion — 1 A is enough; with a Raspberry you need a separate 3–5 A BEC.

### Linear vs switching BEC
- **Linear (LDO)** — dumps the excess voltage as heat: at 6S (25 V) → 5 V and 0.5 A it dissipates 10 W. Unsuitable for high voltages and currents, but has no ripple — good for the gyro and RF.
- **Switching (buck)** — 85–95% efficiency, but produces ripple at the switching frequency (hundreds of kHz) and its harmonics; a bad buck next to the receiver means lost LQ. Flight controllers have a filtered 5 V / 9 V buck.
- A good trick: buck down to 5.5–6 V, then an LDO to 5 V for the sensitive part (many FCs are built this way: 3.3 V for the gyro through an LDO).

### Sag and internal resistance
Voltage under load U = E − I·R_int. R_int of a 6S 4P Li-Ion battery ≈ 20–40 mΩ per cell → 30–60 mΩ per pack (R × 6 / 4); at 60 A the sag is 1.8–3.6 V. Plus the wires: 12 AWG ≈ 5.2 mΩ/m, 14 AWG ≈ 8.3, 16 AWG ≈ 13.2. 20 cm out and back of 14 AWG at 60 A is 0.2 V, which is small; but an XT60 connector with oxidized contacts can add more.

The sag isn't dangerous in itself, but because the BEC on the flight controller gets an input voltage below its threshold (some bucks shut off below 7–8 V on 2S) — an FC reboot in flight.

### Ripple and the capacitor
ESCs switch the windings at tens of kHz, and the current in the battery wires jerks. The inductance of the wires L (≈1 µH per meter) turns dI/dt into voltage spikes: U = L·dI/dt. These are **ripple and spikes** on the power bus that pass into the FC supply, into the gyro (noise in the log) and into the video (lines). The fix is a low-ESR electrolytic or polymer capacitor right on the ESC/PDB power pads: 470–1000 µF at 35 V for 4S, 1000 µF at 50 V for 6S (≥ 30% voltage margin). It acts as a local source: it delivers energy on the edge and absorbs the spike. Short leads — otherwise the lead inductance spoils the effect.

### Protection
- **Smoke stopper** — a bulb or a resistor/current limiter in series with the positive lead at the first power-up. A short circuit — the bulb lights up, the aircraft doesn't smoke.
- **Fuse** — on large aircraft on the power bus (not on the motors — the current is too high and pulsed) and on the companion bus.
- **Reverse polarity** — XT60/XT30 protect by their shape, but soldering one backwards kills the board in a second. A Schottky diode in series (0.3–0.5 V drop) or a P-MOSFET ideal diode for low-voltage branches.
- **Connectors**: XT30 up to ~15–30 A continuous, XT60 ~30 A continuous (briefly up to ~60 A), XT90 ~45 A continuous; AS150/XT150 for high currents. A connector overloaded for its current (rated below the real current) heats up, a hot one oxidizes, an oxidized one heats up even more.

### Wire gauges
{{widget:wire-drop}}

Rule of thumb for short runs on board: 12 AWG up to ~60–80 A, 14 AWG up to ~40–50 A, 16 AWG up to ~25 A, 18 AWG up to ~15 A, 20–22 AWG — signal and 5 V branches up to 2–3 A. The criteria are insulation heating and the acceptable drop; long wires on a wing — one size up.

## practice
### Step 1. Power tree
Draw the tree for your build with the current on each branch (from the table and datasheets). The 5 V total and the 9–12 V total — separately.

### Step 2. Choosing BECs and wire gauges
For each branch: BEC type (buck/LDO), rating ≥ 1.5 × the total, input voltage with margin for a fully charged 6S (25.2 V). Wire gauge — from the table.

### Step 3. Capacitor
Choose the capacitance and voltage, solder it to the ESC/PDB pads with leads no longer than 10–15 mm. Record a hover log before/after: gyro noise in the band above 300 Hz (spectrum) should drop.

### Step 4. Protection
A smoke stopper at every first power-up after soldering. Check with a multimeter that there's no short between + and − before connecting the battery (the resistance shouldn't be below hundreds of ohms; with a capacitor it rises at first).

### Step 5. Measure (link to the measurements module)
Sag under load: battery voltage with no load and in hover (from the log). 5 V ripple — with an oscilloscope with AC coupling: typically < 50–100 mV p-p.

## diagnostics
- **Symptom:** the FC reboots on a sharp throttle punch
  - Possible cause: a sag below the BEC threshold or a bad connector contact.
  - What to do: VBAT log, check the XT connector, the capacitor, a higher-capacity/fresher battery.
- **Symptom:** lines in the analog video on throttle
  - Possible cause: power bus ripple gets into the VTX.
  - What to do: a capacitor on the power bus, power the VTX from a filtered BEC, an LC filter.
- **Symptom:** gyro noise went up after replacing the ESC
  - Possible cause: a different switching frequency, no capacitor.
  - What to do: a capacitor on the pads, check the FC grounding.
- **Symptom:** the BEC is hot
  - Possible cause: a linear BEC with a high input voltage, or current above the rating.
  - What to do: recompute the dissipated power, a buck instead of an LDO, offload the branch.
- **Symptom:** the receiver loses LQ when the video turns on
  - Possible cause: a switching BEC or the VTX next to the receiver antenna.
  - What to do: separate them, shielding, power the RX from a separate LDO.

## references
- Oscar Liang — Capacitors for noise filtering in mini quad | https://oscarliang.com/capacitors-mini-quad | secondary | B
- ArduPilot — Powering the Flight Controller | https://ardupilot.org/copter/docs/common-powering-the-pixhawk.html | primary | A
- INAV — Battery documentation | https://github.com/iNavFlight/inav/blob/master/docs/Battery.md | primary | A

## checklist
- The power tree is drawn with currents per branch
- BECs are chosen by type, current and input voltage
- Wire gauges and connectors are chosen by current
- The capacitor is installed, the effect is visible in the spectrum
- A smoke stopper is used at the first power-up
