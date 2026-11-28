---
id: el-wiring
title: "Soldering, harnesses and reliable connections"
level: L1
readingTime: 25 min
firmware: any firmware
status: published
added: 2026-11-08
tags:
  - soldering
  - harnesses
  - reliability
related:
  - el-power-design
  - f-frame-mech
next:
  - el-emi
source: content/electronics/el-wiring.md
source_hash: 24a991c4cbf9
---

## summary
Most "mysterious" failures are a cold solder joint, a chafed wire, or a connector that was hanging on by a thread. This module is about the craft: how to solder power pads and thin signal wires without cold joints, which solder and flux to use, how to tin, how to strip insulation, route harnesses, secure them and protect them from vibration, and how to check connections mechanically and electrically before flight.

## theory
### The physics of soldering
Solder wets metal only at a sufficient temperature and on a clean surface. Flux dissolves the oxides. A cold joint is solder that solidified without wetting one of the sides: dull, grainy, balled up. It conducts today and breaks from vibration tomorrow.

- **Temperature**: 330–370 °C for leaded solder (Sn63/Pb37, melts at 183 °C), 370–400 °C for lead-free. Starting point (a course guideline): the low end of the range for signal pads, the high end for power pads, XT60 and 12–14 AWG wires; if the pad does not wet within 2–3 s, first use a bigger tip, and only then a higher temperature. Large power pads need a big tip and power (60–80 W), otherwise the pad does not heat through and you get a cold joint; small FC pads need a fine tip and short contact (≤ 3 s), otherwise the pad lifts.
- **Solder**: 0.6–0.8 mm flux-core for signal work, 1.0 mm for power. Leaded is easier for beginners (lower temperature, better flow).
- **Flux**: no-clean or rosin; never active (acid) flux on electronics. Wash off rosin residue with isopropyl alcohol: it is hygroscopic and can conduct.
- **Tinning**: before joining, tin both the wire and the pad. To join, press the tinned wire against the tinned pad, heat until they merge, and hold still until it solidifies (1–2 s).

### Wires
- **Silicone insulation, stranded**: for everything on board: flexible and tolerant of soldering iron heat.
- Strip insulation with a stripper set to the gauge, not with a knife: nicked strands break.
- **Tinned length** = pad depth; an extra tinned section becomes stiff and breaks at its edge; the wire must flex at the insulation, not at the joint.
- Heat-shrink on every exposed section, especially on power wires.

### Wire gauge: calculate, don't guess
A copper wire is a resistor. Resistance per meter (20 °C) by gauge:

| AWG | mΩ/m | Where on board |
|---|---|---|
| 10 | 3.3 | battery → PDB on heavy aircraft (60–100 A) |
| 12 | 5.2 | 6S battery on a 10" and an X8 |
| 14 | 8.3 | battery on a 5", phases of powerful motors |
| 16–18 | 13–21 | 4-in-1 ESC on a 5", phases |
| 20–22 | 33–53 | 5 V BEC, VTX, camera |
| 26–28 | 134–213 | UART and I²C signals, sensors |

Worked example: a 10" on 6S, peak current 60 A, 15 cm each of plus and minus (a 0.3 m loop). 14 AWG: R = 8.3·0.3 = 2.5 mΩ, a 0.15 V drop and 9 W of heating in the wire at the peak. 18 AWG: 0.38 V and 23 W: the wire heats up, the insulation softens, and the drop adds to the battery sag. 12 AWG: 0.09 V and 5.6 W. The criterion (a course guideline, the same as in `el-power-design`): the drop across the power pair at peak current is ≤ 1 % of the pack voltage, which for 22.2 V is 0.22 V; the continuous current is no higher than the rule's line for the gauge in the same module. 14 AWG (0.15 V, 0.7 %) and 12 AWG (0.09 V) pass, 18 AWG (0.38 V, 1.7 %) does not. For a 5" the "14 AWG" row of the table holds with short leads: a 0.2 m loop at a 100 A peak drops 0.17 V. The conclusion: the power gauge is chosen by peak current and length, not "like everyone else"; short power wires are free extra voltage.

{{widget:wire-drop}}

### The contact: where you lose more than in the wire
A bad solder joint or an old connector is 1–5 mΩ instead of a fraction of a mΩ. At 50 A every extra milliohm is 2.5 W of heat in a spot the size of a pea; the connector plastic melts before anything is noticeable in flight. Per the Amass datasheet an XT60 is 30 A continuous (60 A instantaneous); an XT90 is 45–55 A continuous depending on the wire (12–8 AWG), an AS150 75 A on 8 AWG (the rule and the table are in `el-power-design`). A connector that is warm after a flight while the wires are cold is a candidate for replacement.

### Crimping versus soldering
A crimp made with the right tool is a gas-tight connection that does not fear vibration; soldering a crimp makes the strands stiff at the edge, and the wire breaks next to it. Signs of a bad crimp: strands sticking out of the barrel, the insulation not gripped by the second pair of tabs, the wire rotates. Test: pull with 2–3 kg of force for 26–28 AWG; it must not come out.

### Connectors
Soldering an XT30/XT60: keep the connector mated (so that the plastic does not warp), heat the pads until the solder flows, insert the wire, add solder. JST-SH/GH pins are crimped, not soldered; crimp them with the right tool or buy ready-made harnesses. Secure connectors exposed to vibration (a drop of hot glue on the housing, not on the pins).

### Harnesses and vibration
- A wire breaks where one point is stiff and the next is not: at the joint, at the cable tie. Secure it 3–5 cm from the joint, not right next to it.
- A harness has a loose bend and is not under tension (especially to an FC on soft mounts).
- Chafe protection: braided sleeve/heat-shrink where it touches carbon; deburr sharp frame edges.
- Twist signal wires with ground and route them separately from power wires; twist power + and − (see interference).
- Nothing in the prop zone or in the folding path of a folding frame's arms.

### Checking
1. **Visually**: a shiny cone of solder, the outline of the wire visible, no balls and no bridges.
2. **Mechanically**: a light pull test on every wire; wiggle it at the joint.
3. **Electrically**: check adjacent pads for shorts; the resistance of a power connection is a fraction of a mΩ (a multimeter cannot see it, but heating under load will show it).
4. **Under load**: after a flight (or a tethered test with props, or a bench load of 20–30 A through the connection), a thermal camera or a finger (carefully) on each connection: a warm one is a bad one. Throttle without props will not show it: the current is only a few amps.
5. **Vibration test**: motors at low throttle without props for 30 s: nothing rattles or comes loose.

{{diagram:wiring-chain|A reliable connection: preparation, soldering, strain relief, harness securing and a check under current.}}

### 5″ build order: steps and checks
Input: frame, stack or AIO (the choice is in `f-components-choice`, Step 5a), motors, receiver, camera and VTX; tools from `f-starter-kit`: a 60–80 W soldering iron, a multimeter, a smoke stopper, hex drivers. The ordering rule: from the power section to the signal section, and every step is closed with a check that catches an error of exactly that step while it is still cheap to fix. Propellers do not go on until the last row.

| Step | What you do | Check before the next step | If it fails |
|---|---|---|---|
| 1 | Motors onto the arms | the bell turns by hand without friction; the screws do not touch the windings | use a shorter screw: a long one presses into the windings |
| 2 | ESC onto the standoffs; a 12 AWG power lead with an XT60 (the wire gauge is chosen by the peak: 14 AWG is good to ~40–50 A per `el-power-design`, while 5″ ESCs allow up to 4 × 38 A; such punches last fractions of a second and exceed the XT60's 60 A instantaneous current, which the datasheet does not rate, so check the connector temperature after a flight); a 1000 µF 50 V capacitor (6S) on the power pads with short leads (`el-power-design`) | continuity + to − does not beep continuously; the resistance rises to hundreds of ohms and above as the capacitor charges, which is normal | a continuous beep means a solder bridge or a wire touching carbon: find it before the battery |
| 3 | Motor phases to the ESC; the order of the three wires does not matter | a pull test on each wire; adjacent pads do not show continuity with each other | a wrong direction is changed later in the ESC firmware (`f-motors-esc`), no resoldering needed |
| 4 | First power-up of the power section: battery through a smoke stopper | the bulb flashed briefly and went out, the ESCs played the startup tones | the bulb stays bright: a short; disconnect, go back to step 2 |
| 5 | FC onto the standoffs, ESC → FC ribbon cable | over USB without a battery: the board is visible in the configurator, the model on the Setup tab follows the tilts; then the battery through the smoke stopper and the Motors tab without props | motors do not spin: the cable or the protocol; direction: the table in `f-motors-esc` |
| 6 | Receiver: TX → RX crossed over, 5 V, GND | Receiver tab: AETR channels, endpoints 988–2012 (`link-protocols`) | channels do not move: TX/RX swapped or the wrong UART |
| 7 | Camera and VTX, the antenna before applying power | a picture in the goggles at minimum power | never power a VTX without an antenna (`rf-antennas`) |
| 8 | Harness routing, securing 3–5 cm from the joint | after a flight (or a 20–30 A bench load): connections no warmer than the wire next to them; a 30 s vibration test | a warm connection: resolder it (the "Checking" subsection) |
| 9 | Setup from scratch (`bf-setup-scratch`), failsafe by switching off the transmitter | `RXLOSS` in `status` with the transmitter off | no props without a failsafe (`bf-failsafe`) |

Propellers go on only after row 9 and before the first hover. Record every check on the aircraft's card: when hunting a failure, it tells you which step was already clean.

### Where it fits in the system

- **Takes in:** branch currents, wire gauges and connector types (`el-power-design`, `el-redundancy`); routing rules against interference: twisted power wires, signal wires separate (`el-emi`).
- **Puts out:** connections with a resistance of a fraction of a milliohm to the whole power chain (`f-power`); harnesses without tension to the soft-mounted flight controller (`f-frame-mech`); an aircraft built step by step with checks to the first setup (`bf-setup-scratch`).
- **If you get this wrong:** a cold joint on a phase → the motor twitches and will not start, or fails in flight (tree 2 in `diag-troubleshooting`). A harness pulled tight to the flight controller → vibration bypasses the soft mounts, gyro noise rises, the motors heat up (`f-frame-mech`, `bf-filters`). An extra milliohm in the power connector → heating and extra battery sag (`f-power`).

## practice
### Step 1. Practice
On a scrap board/old ESC: 10 joints with 20 AWG, 10 joints with 28 AWG. Cut one power joint across: the solder must fill the whole cross-section without voids.

### Step 2. Power soldering on the build
XT60 → PDB/ESC in 14 AWG. Check: pull test, continuity, heating under load (after a flight or under a 20–30 A bench load).

### Step 3. Signal harness
Receiver → FC (5 V, GND, TX, RX): twist the wires, leave length for bending, secure 3–5 cm from the joint, heat-shrink.

### Step 3b. Connection resistance by the voltage-drop method
A multimeter cannot measure fractions of a milliohm, but a current plus a millivoltmeter can. A bench power supply in current-limit mode at 5 A, the current passed through the power connection (XT60 + solder joint), the multimeter probes in mV mode right on both sides of the connection.

R = U / I. Example: 1.2 mV at 5 A → 0.24 mΩ, good. 8 mV → 1.6 mΩ, redo it: at 50 A that is 4 W in the connector. Measure three connections: your best joint, an old connector from the parts box, and a deliberately bad (cold) joint, and record a table.

### Step 4. Routing and securing
Photos of the build from above and below: nothing in the prop zone, no contact with sharp edges, harnesses not under tension. Self-check: the lab is done when the power joint has been tested under load (after a flight or under a 20–30 A bench load: to the touch or on a thermal camera the connection is no warmer than the wire 3–5 cm from it; a warm connector with cold wires is a candidate for replacement) and measured by the voltage-drop method: less than 5 mV across the connection at 5 A, i.e. R = U / I below 1 mΩ (fractions of a milliohm; 1 mΩ at 50 A is already 2.5 W in one spot), the power wire gauge is justified by a calculation of the drop and heating at peak current, and the harness is secured 3–5 cm from the joint and not under tension.

**Reference answer for self-check.** A good power connection is a fraction of a milliohm: 1.2 mV at 5 A → 0.24 mΩ; 8 mV → 1.6 mΩ means redo it. In the table of three connections the best joint gives the lowest R and the deliberately cold one the highest (a bad joint or an old connector is 1–5 mΩ). Check the gauge calculation against the worked example: a 0.3 m loop of 14 AWG at 60 A is 2.5 mΩ, 0.15 V and 9 W; 18 AWG is 0.38 V and 23 W. The cross-section of the practice joint: the solder filled the whole section without voids. Common wrong results: all three connections showed almost the same value, because the probes were not right at the connection and you measured the wire, not the contact; a cold joint is electrically "no worse" than a good one: it conducts today and breaks from vibration tomorrow, so the measurement does not replace the pull test.

## diagnostics
- **Symptom:** a motor twitches or cuts out under throttle
  - Possible cause: a cold joint on a phase or a chafed wire.
  - What to do: resolder, check continuity, vibration test.
- **Symptom:** the XT60 gets hot
  - Possible cause: a bad solder joint or oxidized contacts.
  - What to do: resolder with proper heating, replace the connector.
- **Symptom:** intermittent loss of the receiver/GPS
  - Possible cause: a cracked strand at the joint or in a JST crimp.
  - What to do: wiggle the wire with the aircraft powered, resolder and secure it.
- **Symptom:** an FC pad lifted
  - Possible cause: overheating or a yank on the wire.
  - What to do: solder to the nearest trace/via, secure the wire with glue.
- **Symptom:** a short after assembly
  - Possible cause: a solder bridge between adjacent pads, a wire touching carbon.
  - What to do: continuity check before power-up, smoke stopper.

## references
- NASA-STD-8739.4 — Crimping, Interconnecting Cables, Harnesses, and Wiring | https://standards.nasa.gov/standard/nasa/nasa-std-87394 | primary | A
- Adafruit — Guide to Excellent Soldering | https://learn.adafruit.com/adafruit-guide-excellent-soldering | secondary | B
- Oscar Liang — A Beginner's Guide to Soldering for FPV Drones | https://oscarliang.com/soldering-guide | secondary | B
- Amass — XT90H-M datasheet (UL1977 30 A; 60 A for 1 min; recommended current 45/50/55 A on 12/10/8 AWG at a 60 K rise) | https://atta.szlcsc.com/upload/public/pdf/source/20220706/D6369ADC773D7B5378E901BEE0D5B60C.pdf | primary | A
- Amass — XT60H-M datasheet V1.2 (30 A continuous, 60 A instantaneous, 12 AWG) | https://cdn.eicom.ru/media/PDF/XT60H-M.pdf | primary | A
- Amass — XT30UPB datasheet (UL1977 15 A; 30 A for 1 min; 15 A on 18 AWG, 20 A on 16 AWG at a 60 K rise) | https://atta.szlcsc.com/upload/public/pdf/source/20230412/7B5DFEF57C9EA5273853390C734B3AC5.pdf | primary | A
- Amass — product catalog (AS150: 75 A MAX, 8 AWG, rise < 85 K) | https://www.rcscomponents.kiev.ua/datasheets/Amas-cat1.pdf | primary | B
- Holybro — Connector & Wire Rating (XT60 12 AWG: 30 A for 4 h and 60 A for 1 min at a rise < 60 K) | https://docs.holybro.com/power-module-and-pdb/power-module/connector-and-wire-rating | secondary | B

## checklist
- Joints are shiny, cone-shaped, without balls
- The wire flexes at the insulation and is secured 3–5 cm from the joint
- Power connections have been checked by heating under load
- I choose the gauge by peak current and length and calculate the drop and heating
- I measure connection resistance by the voltage-drop method
- Harnesses do not touch props or sharp edges and are not under tension
- Continuity check for shorts and a smoke stopper before the first power-up
- I build in the order "power section → FC → receiver → video" and close every step with its own check
