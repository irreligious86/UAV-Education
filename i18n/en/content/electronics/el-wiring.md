---
id: el-wiring
title: "Soldering, Harnesses and Connection Reliability"
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
source_hash: c2e851b398c5
---

## summary
Most “mysterious” failures are a cold solder joint, a chafed wire or a connector that was hanging by a thread. This module is about the craft: how to solder power pads and thin signal wires without cold joints, which solder and flux to use, how to tin, how to strip insulation, route harnesses, secure them and protect them from vibration, and how to check connections mechanically and electrically before flying.

## theory
### The physics of soldering
Solder wets metal only at a high enough temperature and on a clean surface. Flux dissolves the oxides. A cold joint is solder that set without wetting one of the sides: dull, grainy, balled up. It conducts today and breaks from vibration tomorrow.

- **Temperature**: 330–370 °C for leaded solder (Sn63/Pb37, melts at 183 °C), 370–400 °C for lead-free. Big power pads need a big tip and power (60–80 W), otherwise the pad won't heat through and you get a cold joint; small FC pads need a fine tip and brief contact (≤ 3 s), otherwise the pad lifts.
- **Solder**: 0.6–0.8 mm flux-core for signal wires, 1.0 mm for power. Leaded is easier for beginners (lower temperature, better flow).
- **Flux**: no-clean or rosin; active (acid) flux — never on electronics. Rosin residue — wash it off with isopropyl alcohol: it's hygroscopic and can conduct.
- **Tinning**: before joining, tin both the wire and the pad. The joint — press the tinned wire against the tinned pad, heat until they merge, hold still until it sets (1–2 s).

### Wires
- **Silicone insulation, stranded** — for everything on board: flexible, tolerates soldering-iron heat.
- Strip insulation with a gauge-matched stripper, not a knife: nicked strands break.
- **Tinned length** = pad depth; an extra tinned section becomes stiff and breaks at the boundary — the wire should bend at the insulation, not at the joint.
- Heat shrink on every exposed section, especially the power ones.

### Wire gauge: calculate, don't guess
A copper wire is a resistor. Resistance per meter (20 °C) by gauge:

| AWG | mΩ/m | Where on board |
|---|---|---|
| 10 | 3.3 | battery → PDB on heavy aircraft (60–100 A) |
| 12 | 5.2 | 6S battery on 10" and X8 |
| 14 | 8.3 | battery on 5", phases of powerful motors |
| 16–18 | 13–21 | 4-in-1 ESC on 5", phases |
| 20–22 | 33–53 | 5 V BEC, VTX, camera |
| 26–28 | 134–213 | UART, I²C signals, sensors |

Worked example: a 10" on 6S, 60 A peak current, positive and negative 15 cm each (0.3 m of loop). 14 AWG: R = 8.3·0.3 = 2.5 mΩ, a 0.15 V drop, 9 W of heating in the wire at peak. 18 AWG: 0.38 V and 23 W — the wire heats up, the insulation softens, and the drop adds to the battery sag. 12 AWG: 0.09 V and 5.6 W. Conclusion: power gauge is chosen by peak current and length, not “like everyone else”; short power wires are a free voltage bonus.

{{widget:wire-drop}}

### Contact: where you lose more than in the wire
A bad joint or an old connector is 1–5 mΩ instead of fractions of a mΩ. At 50 A every extra milliohm is 2.5 W of heat in a spot the size of a pea; the connector plastic melts before anything is noticeable in flight. An XT60 is rated for roughly 30 A continuous (more at peak); for 40–60 A continuous — XT90 or AS150. A connector that's warm after a flight while the wires are cold is a candidate for replacement.

### Crimping vs soldering
Crimping with the right tool gives a gas-tight joint that isn't afraid of vibration; soldering a crimp makes the strands stiff at the edge and the wire breaks next to it. Signs of a bad crimp: strands sticking out of the barrel, the insulation not gripped by the second pair of tabs, the wire rotates. Test: pull with 2–3 kg of force for 26–28 AWG — it shouldn't come out.

### Connectors
Soldering XT30/XT60: connector mated to its pair (so the plastic doesn't warp), heat the pads until the solder flows, insert the wire, add more solder. JST-SH/GH pins — crimp, don't solder; crimp with the right tool or buy ready-made harnesses. Connectors under vibration — secure them (a drop of hot glue on the housing, not on the pins).

### Harnesses and vibration
- A wire breaks where one point is rigid and the next one isn't: at the joint, at the zip tie. Secure it 3–5 cm from the joint, not right next to it.
- A harness has a loose bend, it's not pulled tight (especially to an FC on soft mounts).
- Chafe protection: sleeving/heat shrink where it touches carbon; sharp frame edges — dress them.
- Signal wires — twisted with ground, routed separately from power; power + and − — twisted (see interference).
- Nothing in the prop zone or in the folding path of a folding frame's arms.

### Checking
1. **Visually**: a shiny cone of solder, the wire outline is visible, no balls or bridges.
2. **Mechanically**: a light pull test on each wire; wiggle it at the joint.
3. **Electrically**: continuity test of neighboring pads for shorts, the resistance of a power joint — fractions of a mΩ (a multimeter can't see it, but heating under load will show it).
4. **Under load**: props off, throttle for a minute, a thermal camera or a finger (carefully) on each joint: a hot one is a bad one.
5. **Vibration test**: motors at low throttle without props for 30 s — nothing rattles or comes loose.

{{diagram:wiring-chain|A reliable connection: preparation, soldering, strain relief, harness mounting and a check under current.}}

## practice
### Step 1. Practice
On a scrap board/old ESC: 10 joints with 20 AWG, 10 joints with 28 AWG. Cut one power joint crosswise — the solder should fill the whole cross-section with no voids.

### Step 2. Power soldering on the build
XT60 → PDB/ESC with 14 AWG. Check: pull test, continuity, heating under load (without props).

### Step 3. Signal harness
Receiver → FC (5 V, GND, TX, RX): twist, length with slack for bending, secured 3–5 cm from the joint, heat shrink.

### Step 3b. Joint resistance by the voltage-drop method
A multimeter can't measure fractions of a milliohm, but a current plus a millivoltmeter can. A bench power supply in 5 A current-limit mode, pass the current through the power connection (XT60 + solder joint), the multimeter probes in mV mode — directly on both sides of the connection.

R = U / I. Example: 1.2 mV at 5 A → 0.24 mΩ — good. 8 mV → 1.6 mΩ — redo it: at 50 A that's 4 W in the connector. Measure three connections: your best joint, an old connector from the box, a deliberately bad (cold) joint — and record a table.

### Step 4. Routing and securing
Photos of the build from above and below: nothing in the prop zone, no contact with sharp edges, harnesses not pulled tight. Lab: a power joint checked under load and measured with the voltage-drop method, the power wire gauge justified by calculation, the harness secured.

## diagnostics
- **Symptom:** a motor stutters or cuts out on throttle
  - Possible cause: a cold joint on a phase or a chafed wire.
  - What to do: resolder, continuity test, vibration test.
- **Symptom:** the XT60 heats up
  - Possible cause: a bad solder joint or oxidized contacts.
  - What to do: resolder with proper heating, replace the connector.
- **Symptom:** intermittent receiver/GPS dropouts
  - Possible cause: a cracked strand at the joint or in a JST crimp.
  - What to do: wiggle the wire with the aircraft powered, resolder and secure.
- **Symptom:** an FC pad lifted
  - Possible cause: overheating or a yanked wire.
  - What to do: solder to the nearest trace/via, secure the wire with glue.
- **Symptom:** a short after assembly
  - Possible cause: a solder bridge between neighboring pads, a wire touching carbon.
  - What to do: continuity test before power-up, smoke stopper.

## references
- NASA-STD-8739.4 — Crimping, Interconnecting Cables, Harnesses, and Wiring | https://standards.nasa.gov/standard/nasa/nasa-std-87394 | primary | A
- Adafruit — Guide to Excellent Soldering | https://learn.adafruit.com/adafruit-guide-excellent-soldering | secondary | B
- Oscar Liang — A Beginner's Guide to Soldering for FPV Drones | https://oscarliang.com/soldering-guide | secondary | B

## checklist
- Joints are shiny, cone-shaped, without balls
- The wire bends at the insulation and is secured 3–5 cm from the joint
- Power connections are checked by heating under load
- I choose the gauge by peak current and length, and calculate the drop and heating
- I measure joint resistance by the voltage-drop method
- Harnesses don't touch props or sharp edges and aren't pulled tight
- Continuity test for shorts and a smoke stopper before the first power-up
