---
id: el-power-design
title: "Onboard power circuit design"
level: L2
readingTime: 55 min
firmware: any firmware (the calculation does not depend on the firmware)
status: published
added: 2026-11-08
tags:
  - power
  - BEC
  - capacitor
  - protection
  - LC filter
  - wire gauge
  - antispark
related:
  - f-power
  - el-measure
  - el-wiring
  - el-emi
  - el-battery-packs
next:
  - el-measure
source: content/electronics/el-power-design.md
source_hash: e9d1f023bf64
---

## summary
An aircraft has several power buses with different requirements: the motor power bus tolerates sag and ripple, while the flight controller, receiver, GPS and camera do not. This module teaches you to calculate the currents per branch, choose a BEC for current and voltage, choose the wire gauge for current and length, understand where sag and ripple come from, and see why a low-ESR capacitor on the bus is not an option but part of the circuit. Separately: an LC filter for video (and why a capacitor that is too good makes it worse), ground loops, inrush current when the battery is plugged in and antispark, protection: smoke stopper, fuse, reverse polarity. Every formula comes with the numbers of a worked 7″ 6S example. The lab: calculating the power design with a script with its actual output, then fitting the capacitor and testing on hardware.

## theory
### Load map
Before choosing components, draw the power tree: battery → power bus → (ESC ×4…8, 5 V BEC, 9–12 V BEC) → loads. Typical currents:

{{diagram:power-tree|The power tree: from the battery to the power bus and separate BECs; each load with its own current.}}

| Load | Voltage | Typical current |
|---|---|---|
| FC + gyro | 5 V (3.3 internal) | 0.1–0.2 A |
| ELRS receiver | 5 V | 0.1–0.3 A (a TX module on board up to 0.5) |
| GPS with compass | 5 V (3.3) | 0.05–0.1 A |
| Digital video system (air unit) | 9–12 V | 0.5–1.2 A, higher peaks |
| Analog VTX 800 mW–1 W | 9–12 V / 5 V | 0.4–0.7 A |
| Servos (wing) | 5–6 V / 7.4 V | 0.5–1 A each while moving |
| Companion (Pi 4/5) | 5 V | 1–3 A, peaks up to 5 |
| Lighting/LEDs | 5 V | 0.06 A per LED |

Add them up with a 50% margin: a 5 V BEC on an aircraft with GPS, receiver and FC but no companion needs 1 A; with a Raspberry Pi you need a separate 3–5 A BEC.

Sizing a branch takes three numbers. **Rating**: BEC ≥ 1.5 × the branch's peak total (a course guideline: the datasheet rating does not account for heating inside the frame without airflow or for the loads' inrush): in the worked 7″ 6S example the 5 V branch (FC, receiver, GPS, four LEDs) draws 0.69 A typical and 0.84 A peak, so BEC ≥ 1.26 A; the 12 V branch (an 800 mW analog VTX and a camera) draws 0.85 A peak, BEC ≥ 1.27 A. **Input current** of a buck: I_in = U_out·I_out / (η·U_in): 5 V × 0.84 A at 88 % efficiency draws 0.19 A from 6S on a full charge and 0.27 A at the end of the flight (18 V); a switching BEC draws more current the lower the pack voltage. **Input range**: the BEC's minimum input voltage from the datasheet must be below the pack voltage at the deepest sag at the end of the flight; otherwise the 5 V output collapses on a punch and the flight controller reboots.

### Linear vs switching BEC
- **Linear (LDO)**: dumps the excess voltage as heat: P = (U_in − U_out)·I; from 6S (25 V) to 5 V at 0.5 A it dissipates 10 W, and for the 5 V branch of the worked example (0.84 A) 17 W versus 0.57 W of losses in a buck. Unsuitable for high voltages and currents, but ripple-free, which is good for the gyro and RF.
- **Switching (buck)**: 85–95% efficiency, but produces ripple at the switching frequency (hundreds of kHz) and its harmonics; a poor buck next to the receiver costs LQ. Flight controllers carry a 5 V / 9 V buck with filtering.
- A good technique: a buck down to 5.5–6 V, then an LDO to 5 V for the sensitive part (many FCs are built this way: 3.3 V for the gyro through an LDO).

### Sag and internal resistance
Voltage under load is U = E − I·R_int. The R_int of a 6S Li-Ion 4P battery ≈ 20–40 mΩ per cell → 30–60 mΩ per pack (R × 6 / 4); at 60 A the sag is 1.8–3.6 V. Plus the wires: 12 AWG ≈ 5.2 mΩ/m, 14 AWG ≈ 8.3, 16 AWG ≈ 13.2 mΩ/m. 20 cm each of plus and minus in 14 AWG (a 0.4 m loop) at 60 A drops 0.2 V, which is little; but an XT60 with oxidized contacts can drop more.

Sag is dangerous not in itself but because the BEC on the flight controller gets an input voltage below its threshold (some bucks shut down below 7–8 V, which is already the level of an almost empty 2S): the FC reboots in flight.

### Ripple and the capacitor
ESCs switch the windings at tens of kHz, and the current in the battery wires jerks. The inductance of the wires L (≈1 µH per meter, a course guideline) turns dI/dt into voltage spikes: U = L·dI/dt. These are the **ripple and spikes** on the power bus that get into the FC supply, the gyro (noise in the log) and the video (lines). The solution is a low-ESR electrolytic or polymer capacitor right on the ESC/PDB power pads: 470–1000 µF at 35 V for 4S, 1000 µF at 50 V for 6S (≥ 30% voltage margin). It acts as a local source: it supplies energy on the edge and absorbs the spike. Keep the leads short, otherwise the lead inductance spoils the effect.

Orders of magnitude: a 0.3 m power lead loop is about 0.3 µH; if the ESC current changes by 30 A in 10 µs, the spike is 0.9 V, and in 1 µs it is already 9 V on top of 25.2 V. Hence the capacitor voltage: the "30 % on top" rule is only the minimum: 1.3 × 25.2 = 32.8 V for 6S. On 6S the spikes during motor braking exceed 35 V, so the course uses 50 V, 1.98 × full charge (for 4S: 35 V, 2.1 ×; a course guideline), and 35 V on 6S is a common cause of bulging capacitors. The second capacitor parameter is the allowed ripple current from the datasheet: the AC component of the ESC current flows through the capacitor on the power bus and heats it by I²·ESR; a hot capacitor loses capacitance and fails. If there are several ESCs on the power bus (an octocopter, individual ESCs), each one gets a capacitor.

**Which capacitor for which class.** ESC manufacturers give a minimum, not a calculation: FETtec for its 35/45 A 4-in-1 ESCs on 6S specifies at least 470 µF at 50 V together with its own spike absorber (Spike Absorber); Holybro ships a 1000 µF 35 V capacitor with the Tekko32 F4 4-in-1 50 A and "highly recommends" it for 6S. On 6S the course uses 50 V per the calculation above (35 V is only 1.39 × the 25.2 V full charge): the 35 V from the Holybro kit is the manufacturer's minimum, not a margin.

| Class | Capacitor (course guideline) | Why |
|---|---|---|
| Whoop and AIO 1–2S | usually no separate one (an estimate) | low voltage and current, ceramics on the board |
| 3–5" on 4S | 470–1000 µF, 35 V, low ESR | 35 V = 2.1 × 16.8 V |
| 5–7" on 6S, 4-in-1 stack | 1000 µF, 50 V, low ESR (the FETtec minimum is 470 µF 50 V) | braking spikes above 35 V |
| 10" and X8, individual ESCs | a capacitor at each ESC, voltage with the same margin over full charge | a long bus, each ESC has its own wire inductance |

Add a second capacitor in parallel if the gyro noise above 300 Hz did not drop after the first one (the criterion is in the practice) or if the capacitor is warm after a flight, meaning the ripple current exceeds its rated ripple current. The check after fitting is the same: the gyro spectrum before and after, and a cold capacitor body after a flight.

### LC filter for video
Analog video (1 V peak to peak) and the VTX are sensitive to ripple at the ESC switching frequency (tens of kHz) and its harmonics. An LC filter, an inductor L in series and a capacitor C at the output, passes DC and attenuates everything above the resonance f₀ = 1 / (2π√(LC)) at 40 dB per decade. For 22 µH and 470 µF, f₀ = 1565 Hz: at 24 kHz the attenuation is up to −46 dB, at 48 kHz up to −55 dB.

Two traps. **Resonance**: at f₀ the filter does not attenuate but amplifies by Q = √(L/C) / R, where R is the inductor's resistance (DCR) plus the capacitor's ESR. With a polymer capacitor (ESR 0.01 Ω) Q = 3.6, a peak of +11.2 dB: interference around 1.5 kHz gets through three times stronger than with no filter at all. With an electrolytic at ESR 0.15 Ω the peak is only +2.9 dB, but the ESR limits the attenuation at high frequencies: at 24 kHz it is −26.8 dB instead of −45.6. The compromise is ESR + DCR ≈ √(L/C) = 0.216 Ω: with these L and C, an ESR of 0.15–0.18 Ω gives a peak of ≤ 3 dB (0.15 Ω: +2.9 dB) and still ≥ 25 dB at 24 kHz (0.18 Ω: −25.3 dB); 0.05 Ω already gives +7.1 dB. Or use a polymer plus a separate damping RC network. **Saturation**: an inductor with a saturation current below the branch current stops being an inductor exactly at the peak. Choose I_sat ≥ 1.5 × the branch's peak current (a course guideline) and calculate the drop: 0.85 A × 0.05 Ω = 42 mV, which is negligible. The filter goes at the VTX/camera input, not at the BEC: otherwise the wire after the filter picks up interference again.

An LC filter does not cure interference that comes in through the ground; for that you need order in the grounding.

{{diagram:chart-power-lc-filter|A 22 µH + 470 µF LC filter attenuates 24 kHz ESC ripple by tens of dB, but amplifies at the 1.6 kHz resonance: a low ESR gives an +11 dB peak, an ESR of 0.15 Ω damps it at the cost of high-frequency attenuation.}}

### Ground and ground loops
Ground is not an ideal point but wires and planes with resistance. Motor current returns to the battery through the negative; if the reference wire of the video or a signal runs over the same stretch of ground, the drop across it adds to the signal. A 1 mΩ stretch of shared ground carrying 30 A is 30 mV, 3 % of the analog video swing: lines under throttle. A **ground loop** appears when two units are connected by ground through two paths, for example a camera powered from the flight controller's BEC and a VTX from a separate BEC, with the grounds tied both through the flight controller and through the video cable shield: interference current is induced and flows in the loop.

Rules: camera and VTX from one source, the video ground runs next to the video signal, the power negative and the signal grounds meet at one point (a star at the PDB or at the ESC power pads), power + and − twisted (smaller loop area means less radiation and pickup). In detail, with measurements, in `el-emi`.

### Protection
- **Smoke stopper**: a bulb or a resistor/current limiter in series with the positive at the first power-up. On a short circuit the bulb lights up and the aircraft does not smoke.
- **Fuse**: on large aircraft, on the power bus (not on the motors: the current is too high and pulsed) and on the companion bus. Rating: ≥ 1.33 × the branch's maximum continuous current (I / 0.75), rounded up to the next standard rating, more in a hot frame (Littelfuse rule 3), a time-delay type; DC voltage rating ≥ the full-charge pack voltage and interrupting rating ≥ the pack's short-circuit current (rules 2 and 5); details in `el-redundancy`, "Fuses".
- **Reverse polarity**: XT60/XT30 protect by their shape, but soldering them backwards kills a board in a second. A Schottky diode in series (0.3–0.5 V drop) or a P-MOSFET as an ideal diode for low-voltage branches. On a 2 A branch a Schottky with a 0.4 V drop dissipates 0.8 W, a 10 mΩ MOSFET 0.04 W.
- **Inrush current and antispark.** When the battery is plugged in, the power bus capacitor charges from zero; the current is limited only by the loop resistance, up to hundreds of amps: with a fresh 6S LiPo (12 mΩ pack + 2.5 mΩ lead + 20 mΩ ESR, as in the script) the upper bound is 730 A, with the Li-Ion 6S4P from the sag section (30–60 mΩ) it is 300–480 A; the wire inductance (0.3 µH) lowers the peak further. The energy in the capacitor is ½CU² = 0.33 J at 1040 µF and 25.2 V, and the same amount is lost in the wires and contacts while charging, as a spark on the connector pins. The spark burns the contacts, and their resistance rises with it (see the connector table below). Antispark means precharging through a resistor: a connector with an antispark pin (XT90-S and similar) or a button with a resistor. A 10 Ω resistor limits the current to 2.5 A, the time constant is τ = RC = 10.4 ms, after 5τ = 52 ms the capacitor is 99 % charged, and then the main contact closes. The resistor's 64 W peak power lasts milliseconds: you need a pulse-rated resistor, not an 0402 SMD.
- **Connectors** (the course rule is the Amass datasheets, linked in the sources): continuous current is the datasheet's "recommended current" for your wire gauge at a temperature rise ≤ 60 K; short-term current (up to 1 min) must not exceed the datasheet's instantaneous figure. XT30: 15 A on 18 AWG (20 A on 16 AWG), up to 30 A short-term; XT60: 30 A continuous and 60 A instantaneous on 12 AWG (datasheet V1.2 gives no conditions; Holybro gives the same 30 A for 4 h and 60 A for 1 min at a rise < 60 K for 12 AWG); XT90: 45 A on 12 AWG, 50 A on 10 AWG, 55 A on 8 AWG, up to 60 A short-term (the UL1977 rating is 30 A; 40 A appears only in sellers' descriptions); AS150: 75 A on 8 AWG, which is the maximum from the Amass catalog at a rise < 85 K; the catalog gives no one-minute current. The catalog is older than the datasheets and gives different figures for the XT series (XT30 20 A, XT60 35 A, XT90 45 A, maximum at < 85 K); for the XT series the course uses the datasheets. A connector overloaded with current (rated below the real current) heats up, a heated one oxidizes, and an oxidized one heats up even more.

| Connector | Continuous / short-term (Amass datasheet) | Where | Heat in a mated pair at 0.3 / 1 / 3 mΩ at the row's short-term current |
|---|---|---|---|
| XT30 | 15 A (18 AWG), 20 A (16 AWG) / 30 A up to 1 min | whoop, 3″, branches, 2S–4S up to 15–20 A | at 30 A: 0.27 / 0.9 / 2.7 W |
| XT60 | 30 A / 60 A instantaneous (12 AWG, datasheet V1.2) | 5″, packs up to ~1500 mAh | at 60 A: 1.1 / 3.6 / 10.8 W |
| XT90 / XT90-S | 45 A (12 AWG) … 55 A (8 AWG) / 60 A up to 1 min (XT90H datasheet; XT90-S the same per the catalog; S means antispark) | 7–10″, Li-Ion 6S4P, X8 | at 60 A: 1.1 / 3.6 / 10.8 W |
| AS150 | 75 A (8 AWG, catalog maximum at < 85 K) / — | heavy copters, X8 on 12S | at 75 A: 1.7 / 5.6 / 16.9 W |

The currents come from the Amass datasheets (linked in the sources): the UL1977 rating is conservative (30 A for the XT90), and the recommended current depends on the wire gauge and the allowed temperature rise. For another manufacturer's connector or a clone, use its datasheet, and without a datasheet treat the table values as a ceiling. The heat column is calculated the same way for any connector: P = I²·R of the contact. A new pair is a fraction of a mΩ (0.3 mΩ: 1.9 W at 80 A), a worn one or one with spark craters is 1–3 mΩ, and then on a punch 6–19 W are released in a spot the size of a pea. The 80 A punch from the 7″ example is above the one-minute current of the XT60 and XT90: it survives seconds of it, but the datasheet does not rate that mode, and the heat grows as I².

### Wire gauges
{{widget:wire-drop}}

The rule for short runs on board is the **continuous** (cruise) current: 12 AWG up to ~60–80 A, 14 AWG up to ~40–50 A, 16 AWG up to ~25 A, 18 AWG up to ~15 A (a course guideline), 20–22 AWG for signal and 5 V branches up to 2–3 A. The **peak** current (a punch, seconds) is checked not against this line but against the drop criterion below: ≤ 1 % of the pack voltage across the power pair. So 14 AWG on a 5" with 60–100 A peaks (`f-power`) passes with short leads: a 0.2 m loop at 100 A drops 0.17 V, 0.75 % of 22.2 V. Long wires on a wing go one size up.

Where the numbers come from. Wire resistance R = ρ·L / A, with copper ρ = 1.724·10⁻⁸ Ω·m at 20 °C and the AWG diameter d = 0.127 mm × 92^((36 − n)/39). That gives 12 AWG 5.21 mΩ/m, 14 AWG 8.28, 16 AWG 13.17 (the same table as in `el-wiring`). Resistance rises by 0.393 % per degree: a hot wire at 80 °C is 1.236 times worse than a cold one. For the 7″ power lead (15 cm each of plus and minus, a 0.3 m loop) on an 80 A punch: 12 AWG drops 0.125 V (0.6 % of 22.2 V) with 10 W of heat in the wire, 14 AWG 0.20 V and 15.9 W, 16 AWG 0.32 V and 25 W. The course criterion (a guideline): a drop across the power lead at peak current of ≤ 1 % of the pack voltage, and heat that the wire can shed over the duration of the punch; for the continuous cruise current (35 A) the same calculation: 14 AWG 3 W, 12 AWG 1.9 W.

{{lesson:el-wiring|How to solder and crimp power wires and how to measure joint resistance with the voltage-drop method: the practical half of this calculation.}}

| Quantity | Formula | Module example (7″ 6S) |
|---|---|---|
| BEC rating | ≥ 1.5 × the branch's peak total | 5 V: 0.84 A → ≥ 1.26 A |
| Buck input current | U_out·I_out / (η·U_in) | 0.27 A at 18 V |
| LDO heat | (U_in − U_out)·I | 17 W (25.2 → 5 V, 0.84 A) |
| Wire drop | I·ρ·L/A | 14 AWG, 0.3 m, 80 A: 0.20 V |
| Spike without a capacitor | L·dI/dt | 0.3 µH, 30 A in 1 µs: 9 V |
| LC resonance | 1 / (2π√(LC)) | 22 µH + 470 µF: 1565 Hz |
| LC quality factor | √(L/C) / (DCR + ESR) | 3.6 at ESR 0.01 Ω |
| Capacitor energy | ½CU² | 1040 µF, 25.2 V: 0.33 J |
| Precharge | τ = R·C, done in 5τ | 10 Ω: 10.4 ms, 52 ms |

### Where it fits in the system

- **Takes in:** the battery voltage and internal resistance (`f-power`, `el-battery-packs`); the motors' peak current (`f-motors-esc`); the load currents on the 5 and 9–12 V branches (`el-peripherals`).
- **Puts out:** stable 5 and 9–12 V to the flight controller, receiver, GPS and video; a power bus with a capacitor to the ESCs; wire gauges and connectors to the build (`el-wiring`); a circuit with fuses to redundancy (`el-redundancy`).
- **If you get this wrong:** no low-ESR capacitor on the power bus, or a 35 V one on 6S → spikes get into the gyro (noise in the log that is mistaken for a filter problem, `bf-filters`) and into the video (lines). Sag drops the BEC input below its threshold → the flight controller reboots in the air (trees 3 and 6 in `diag-troubleshooting`). A poor buck next to the receiver → LQ drops (`el-emi`).

## practice
### Step 1. Power tree
Draw the tree for your build with the currents on each branch (from the table and datasheets). The 5 V total and the 9–12 V total separately.

### Step 2. Choosing BECs and wire gauges
For each branch: BEC type (buck/LDO), a rating ≥ 1.5 × the total, an input voltage with margin for a fully charged 6S (25.2 V). Wire gauge per the table.

### Step 3. Calculating the design with the script
The main path is a calculation without hardware. The script calculates the worked 7″ 6S: the BEC branches, the power lead in four gauges and the connectors, the spike and the capacitor voltage, the video LC filter at four ESRs, the inrush current and precharge, and reverse polarity protection. Put your own loads into `B5` and `B12`, your wire length and currents, and you get your own design.

```python
# power_lab.py — power distribution design for a 7" 6S quad: BEC sizing, wire drop,
# capacitor, LC filter for analog video, inrush and precharge.  python3 power_lab.py
import math

V_FULL, V_NOM, V_MIN = 25.2, 22.2, 18.0      # 6S: full, nominal, empty under load (3.0 V/cell)
# --- 1. BEC branches: (name, volts, amps typical, amps peak)
B5 = [("FC + gyro", 5, 0.2, 0.2), ("ELRS RX", 5, 0.15, 0.3), ("GPS + compass", 5, 0.1, 0.1),
      ("LED x4", 5, 0.24, 0.24)]
B12 = [("analog VTX 800 mW", 12, 0.6, 0.7), ("FPV camera", 12, 0.1, 0.15)]
for name, br, eta in (("5 V", B5, 0.88), ("12 V", B12, 0.90)):
    v = br[0][1]; i_typ = sum(b[2] for b in br); i_pk = sum(b[3] for b in br)
    rating = 1.5 * i_pk
    p_out = v * i_pk
    print(f"BEC {name}: typ {i_typ:.2f} A, peak {i_pk:.2f} A -> rating >= {rating:.2f} A; "
          f"buck input at {V_MIN} V: {p_out / (eta * V_MIN):.2f} A, at {V_FULL} V: {p_out / (eta * V_FULL):.2f} A")
    print(f"   LDO instead from {V_FULL} V: {(V_FULL - v) * i_pk:.1f} W of heat "
          f"(buck loss {p_out * (1 / eta - 1):.2f} W)")

# --- 2. Main lead: AWG -> resistance, drop and heat, 2 x 0.15 m, cruise 35 A, punch 80 A
def awg_ohm_per_m(n, t=20.0):
    d = 0.127e-3 * 92 ** ((36 - n) / 39)                  # ASTM B258 diameter, m
    return 1.724e-8 * (1 + 0.00393 * (t - 20)) / (math.pi * d * d / 4)
for n in (10, 12, 14, 16):
    r = awg_ohm_per_m(n) * 0.30
    print(f"{n} AWG: {awg_ohm_per_m(n) * 1e3:5.2f} mOhm/m; 0.30 m loop {r * 1e3:4.2f} mOhm; "
          f"35 A: {35 * r:.3f} V {35 * 35 * r:4.1f} W; 80 A: {80 * r:.3f} V "
          f"({80 * r / V_NOM * 100:.1f} % of {V_NOM} V) {80 * 80 * r:4.1f} W; at 80 C {awg_ohm_per_m(n, 80) / awg_ohm_per_m(n):.3f}x")
for r_c in (0.3e-3, 1.0e-3, 3.0e-3):                       # one connector pair: good, worn, burnt
    print(f"connector {r_c * 1e3:.1f} mOhm at 35 A: {35 * 35 * r_c:4.2f} W, at 80 A: {80 * 80 * r_c:5.2f} W")

# --- 3. Bus capacitor and spike U = L di/dt
L_wire = 1e-6 * 0.30                                      # ~1 uH per metre of lead (loop 0.30 m)
for di, dt in ((30, 10e-6), (30, 1e-6)):
    print(f"spike without cap: L={L_wire * 1e6:.2f} uH, {di} A in {dt * 1e6:g} us -> {L_wire * di / dt:.1f} V")
print(f"cap voltage: 1.3 x {V_FULL} = {1.3 * V_FULL:.1f} V minimum; 50 V gives {50 / V_FULL:.2f}x full charge")

# --- 4. LC filter for the 12 V video branch: L = 22 uH (DCR 0.05 Ohm), C = 470 uF
L, C, DCR = 22e-6, 470e-6, 0.05
f0 = 1 / (2 * math.pi * math.sqrt(L * C)); Z0 = math.sqrt(L / C)
def gain_db(f, esr):
    w = 2 * math.pi * f
    zc = esr + 1 / complex(0, w * C)                      # capacitor with its ESR
    return 20 * math.log10(abs(zc / (zc + DCR + complex(0, w * L))))
print(f"LC: f0 = {f0:.0f} Hz, Z0 = sqrt(L/C) = {Z0:.3f} Ohm, DC drop at 0.85 A {0.85 * DCR * 1e3:.0f} mV")
for esr in (0.01, 0.05, 0.15, 0.25):                     # polymer ... ordinary electrolytic
    pk = max(gain_db(f0 * k / 100, esr) for k in range(30, 300))
    print(f"   ESR {esr:.2f} Ohm: Q = {Z0 / (DCR + esr):.2f}, peak {pk:+.1f} dB, "
          f"24 kHz {gain_db(24e3, esr):6.1f} dB, 48 kHz {gain_db(48e3, esr):6.1f} dB")

# --- 5. Inrush at plug-in and precharge
C_bus = 1000e-6 + 4 * 10e-6                               # bulk cap + 4 x 10 uF ceramics on ESCs
R_loop = 0.012 + 0.0025 + 0.020                           # LiPo pack + lead + cap ESR, Ohm
E = 0.5 * C_bus * V_FULL ** 2
print(f"inrush: I_peak <= {V_FULL / R_loop:.0f} A (resistive limit), energy in cap {E:.2f} J, "
      f"same {E:.2f} J lost in the contacts and wires while charging")
for Rp in (5.0, 10.0):
    tau = Rp * C_bus
    print(f"precharge {Rp:g} Ohm: I_peak {V_FULL / Rp:.1f} A, tau {tau * 1e3:.1f} ms, 5tau {5 * tau * 1e3:.0f} ms, "
          f"P_peak {V_FULL ** 2 / Rp:.0f} W")
# --- 6. Reverse polarity on a 2 A branch
print(f"reverse protection 2 A: Schottky 0.4 V -> {0.4 * 2:.1f} W; P-MOSFET 10 mOhm -> {2 * 2 * 0.010:.2f} W")
```

Actual output of `python3 power_lab.py`:

```text
BEC 5 V: typ 0.69 A, peak 0.84 A -> rating >= 1.26 A; buck input at 18.0 V: 0.27 A, at 25.2 V: 0.19 A
   LDO instead from 25.2 V: 17.0 W of heat (buck loss 0.57 W)
BEC 12 V: typ 0.70 A, peak 0.85 A -> rating >= 1.27 A; buck input at 18.0 V: 0.63 A, at 25.2 V: 0.45 A
   LDO instead from 25.2 V: 11.2 W of heat (buck loss 1.13 W)
10 AWG:  3.28 mOhm/m; 0.30 m loop 0.98 mOhm; 35 A: 0.034 V  1.2 W; 80 A: 0.079 V (0.4 % of 22.2 V)  6.3 W; at 80 C 1.236x
12 AWG:  5.21 mOhm/m; 0.30 m loop 1.56 mOhm; 35 A: 0.055 V  1.9 W; 80 A: 0.125 V (0.6 % of 22.2 V) 10.0 W; at 80 C 1.236x
14 AWG:  8.28 mOhm/m; 0.30 m loop 2.49 mOhm; 35 A: 0.087 V  3.0 W; 80 A: 0.199 V (0.9 % of 22.2 V) 15.9 W; at 80 C 1.236x
16 AWG: 13.17 mOhm/m; 0.30 m loop 3.95 mOhm; 35 A: 0.138 V  4.8 W; 80 A: 0.316 V (1.4 % of 22.2 V) 25.3 W; at 80 C 1.236x
connector 0.3 mOhm at 35 A: 0.37 W, at 80 A:  1.92 W
connector 1.0 mOhm at 35 A: 1.23 W, at 80 A:  6.40 W
connector 3.0 mOhm at 35 A: 3.68 W, at 80 A: 19.20 W
spike without cap: L=0.30 uH, 30 A in 10 us -> 0.9 V
spike without cap: L=0.30 uH, 30 A in 1 us -> 9.0 V
cap voltage: 1.3 x 25.2 = 32.8 V minimum; 50 V gives 1.98x full charge
LC: f0 = 1565 Hz, Z0 = sqrt(L/C) = 0.216 Ohm, DC drop at 0.85 A 42 mV
   ESR 0.01 Ohm: Q = 3.61, peak +11.2 dB, 24 kHz  -45.6 dB, 48 kHz  -54.7 dB
   ESR 0.05 Ohm: Q = 2.16, peak +7.1 dB, 24 kHz  -36.1 dB, 48 kHz  -42.4 dB
   ESR 0.15 Ohm: Q = 1.08, peak +2.9 dB, 24 kHz  -26.8 dB, 48 kHz  -32.9 dB
   ESR 0.25 Ohm: Q = 0.72, peak +1.4 dB, 24 kHz  -22.4 dB, 48 kHz  -28.5 dB
inrush: I_peak <= 730 A (resistive limit), energy in cap 0.33 J, same 0.33 J lost in the contacts and wires while charging
precharge 5 Ohm: I_peak 5.0 A, tau 5.2 ms, 5tau 26 ms, P_peak 127 W
precharge 10 Ohm: I_peak 2.5 A, tau 10.4 ms, 5tau 52 ms, P_peak 64 W
reverse protection 2 A: Schottky 0.4 V -> 0.8 W; P-MOSFET 10 mOhm -> 0.04 W
```

### Step 4. Checking the formulas by hand
Recalculate four numbers without the script and compare them with the output:
- the 5 V buck input current at the end of the flight: 5 × 0.84 / (0.88 × 18) = **0.27 A**;
- the drop across 14 AWG, a 0.3 m loop, 80 A: 8.28 mΩ/m × 0.3 × 80 = **0.199 V**;
- the LC resonance: 1 / (2π√(22·10⁻⁶ × 470·10⁻⁶)) = **1565 Hz**; Q at ESR 0.01 Ω: 0.216 / 0.06 = **3.6**;
- precharge through 10 Ω: τ = 10 × 1040·10⁻⁶ = **10.4 ms**, peak current 25.2 / 10 = **2.5 A**.

Then decide for your build: which power lead gauge passes the ≤ 1 % criterion at the peak, which ESR the LC filter capacitor should have (a peak at resonance of ≤ 3 dB and an attenuation at the ESC frequency of ≥ 25 dB, a course guideline), and whether you need antispark (6S packs and above with a power capacitor of ≥ 1000 µF: yes (a course guideline), by the 0.33 J spark energy on every plug-in).

### Moving to real hardware
Props are off for every step; until the first successful power-up the battery is connected only through a smoke stopper.

**1. Capacitor.** Choose the capacitance and voltage and solder it to the ESC/PDB pads with leads no longer than 10–15 mm. Record a hover log before and after: the gyro noise in the band above 300 Hz (spectrum) should drop.

**2. Protection.** A smoke stopper at every first power-up after soldering. Check with a multimeter that there is no short between + and − before connecting the battery (the resistance should not be below hundreds of ohms (a course guideline); on a capacitor it rises at first).

**3. Measure (tie-in with the measurements module).** Sag under load: the battery voltage at no load and in hover (from the log). 5 V ripple with a scope on AC coupling: typically < 50–100 mV p-p. Heat: after a flight (or a tethered test with props, or a bench load of 20–30 A through the connection), the connector feels no warmer than the wire next to it; throttle without props will not show it, the current is only a few amps (`el-wiring`).

Abort if the smoke stopper stays brightly lit (a short), the BEC or the capacitor heats up with no load, or the 5 V ripple is above 200 mV p-p: find the cause first. Hardware criteria: 5 V ripple < 100 mV p-p under load (a course guideline), sag from the log within the calculation U = E − I·R plus the wire drop, gyro noise above 300 Hz lower after fitting the capacitor than before.

Self-check: the lab is done when (calculation path) the step 3 script produced output matching the one shown, the four hand calculations of step 4 agreed with it (0.27 A, 0.199 V, 1565 Hz and Q 3.6, 10.4 ms and 2.5 A), and for your build you have chosen the power lead gauge by the ≤ 1 % criterion at the peak, BECs rated ≥ 1.5 × the branch peak with a minimum input below the pack voltage at the end of the flight, and an LC filter capacitor ESR with a peak of ≤ 3 dB; (hardware) 5 V ripple < 100 mV p-p, the sag from the log agrees with the calculation, and the gyro noise above 300 Hz dropped after the capacitor.

**Reference answer for self-check.** Check the tree against the module's guidelines: an aircraft with FC, receiver and GPS but no companion fits in a 1 A 5 V BEC, with a Raspberry Pi you need a separate 3–5 A BEC; each BEC is rated ≥ 1.5 × its branch total. Capacitor: 470–1000 µF at 35 V for 4S, 1000 µF at 50 V for 6S. Compare the sag from the log with U = E − I·R_int: for a 6S 4P Li-Ion at 60 A that is 1.8–3.6 V, plus about 0.2 V for 20 cm of 14 AWG pair. Common wrong results: the gyro noise above 300 Hz did not drop after fitting the capacitor, meaning the leads are longer than 10–15 mm or the capacitor is not on the power pads; the sag is noticeably larger than calculated, so check the connector first (an oxidized XT60), then the wires; 5 V ripple above 100 mV p-p, so before blaming the BEC, check that there is a capacitor on the power bus. Calculation errors: the buck input current calculated at full charge (0.19 A) instead of at the end of the flight (0.27 A), so the branch wire and fuse are chosen with no margin; the drop calculated for one 0.15 m conductor instead of the 0.3 m loop, half the real value; the lowest ESR chosen for the LC "because it is better", so a filter with a +11 dB peak at resonance amplifies interference around 1.5 kHz.

## diagnostics
- **Symptom:** the FC reboots on a throttle punch
  - Possible cause: sag below the BEC threshold or a bad connector contact.
  - What to do: VBAT log, check the XT connector, the capacitor, a higher-capacity/fresher battery.
- **Symptom:** lines in the analog video under throttle
  - Possible cause: power bus ripple gets into the VTX.
  - What to do: a capacitor on the power bus, power the VTX from a filtered BEC, an LC filter.
- **Symptom:** gyro noise went up after replacing the ESC
  - Possible cause: a different switching frequency, no capacitor.
  - What to do: a capacitor on the pads, check the FC grounding.
- **Symptom:** the BEC is hot
  - Possible cause: a linear BEC on a high input, or current above the rating.
  - What to do: recalculate the dissipated power, a buck instead of an LDO, offload the branch.
- **Symptom:** lines in the video remain after fitting an LC filter
  - Possible cause: the interference comes through the ground (camera and VTX from different sources, a ground loop) or the filter resonates with a polymer capacitor (a peak of up to +11 dB around f₀).
  - What to do: camera and VTX from one source, the video ground next to the signal; a filter capacitor with an ESR of 0.15–0.18 Ω (for 22 µH + 470 µF) or a damping RC network.
- **Symptom:** a spark and a snap on every battery plug-in, connector pins covered in black craters
  - Possible cause: the inrush current charging the power bus capacitor (hundreds of amps, 0.33 J per plug-in at 1000 µF on 6S).
  - What to do: an antispark connector or precharge through a 5–10 Ω resistor; replace a worn connector, as its resistance is already 1–3 mΩ.
- **Symptom:** the flight controller reboots on a punch at the end of the flight, but not at the start
  - Possible cause: the pack voltage under load drops below the BEC's minimum input.
  - What to do: compare the BEC's minimum input from the datasheet with the voltage at the end of the flight at the peak; a BEC with a lower minimum input or a separate BEC for the FC.
- **Symptom:** the receiver loses LQ when the video is switched on
  - Possible cause: a switching BEC or the VTX next to the receiver antenna.
  - What to do: separate them, shield, power the RX from a separate LDO.

## references
- ArduPilot — Powering the Flight Controller (flight controller power, power module, redundancy) | https://ardupilot.org/copter/docs/common-powering-the-pixhawk.html | primary | A
- Oscar Liang — Capacitors for noise filtering in mini quad | https://oscarliang.com/capacitors-mini-quad | secondary | B
- FETtec — How to use caps and FETtec Spike Absorber (6S: at least 470 µF 50 V) | https://fettec.freshdesk.com/support/solutions/articles/60000468482-how-to-use-caps-and-fettec-spike-absorber- | primary | A
- Holybro — Tekko32 F4 4in1 50A ESC spec (1000 µF 35 V capacitor included, "highly recommended for 6s") | https://cdn.shopify.com/s/files/1/0604/5905/7341/files/Holybro_Tekko32_F4_4in1_50A_ESC_spec_7f900ab6-7c29-483f-86a9-260c69b669fd.pdf | primary | A
- INAV — Battery documentation | https://github.com/iNavFlight/inav/blob/master/docs/Battery.md | primary | A
- Amass — XT90H-M datasheet (UL1977 30 A; 60 A for 1 min; recommended current 45/50/55 A on 12/10/8 AWG at a 60 K rise) | https://atta.szlcsc.com/upload/public/pdf/source/20220706/D6369ADC773D7B5378E901BEE0D5B60C.pdf | primary | A
- Amass — XT60H-M datasheet V1.2 (30 A continuous, 60 A instantaneous, 12 AWG) | https://cdn.eicom.ru/media/PDF/XT60H-M.pdf | primary | A
- Amass — XT30UPB datasheet (UL1977 15 A; 30 A for 1 min; 15 A on 18 AWG, 20 A on 16 AWG at a 60 K rise) | https://atta.szlcsc.com/upload/public/pdf/source/20230412/7B5DFEF57C9EA5273853390C734B3AC5.pdf | primary | A
- Amass — product catalog (AS150: 75 A MAX, 8 AWG, rise < 85 K) | https://www.rcscomponents.kiev.ua/datasheets/Amas-cat1.pdf | primary | B
- Holybro — Connector & Wire Rating (XT60 12 AWG: 30 A for 4 h and 60 A for 1 min at a rise < 60 K) | https://docs.holybro.com/power-module-and-pdb/power-module/connector-and-wire-rating | secondary | B

## checklist
- The power tree is drawn with the currents per branch
- The BECs are chosen by type, current and input voltage
- Wire gauges and connectors are chosen for the current
- The capacitor is fitted, and the effect is visible in the spectrum
- A smoke stopper is used at the first power-up
- The LC filter is calculated: f₀, Q and the attenuation at the ESC frequency
- The inrush current is calculated, and antispark is chosen by the spark energy
