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

{{diagram:chart-power-lc-filter|LC-фильтр 22 мкГн + 470 мкФ ослабляет пульсации ESC на 24 кГц на десятки дБ, но на резонансе 1.6 кГц усиливает: низкий ESR даёт +11 дБ подъёма, ESR 0.15 Ом гасит его ценой ослабления на высоких частотах.}}

### Protection
- **Smoke stopper** — a bulb or a resistor/current limiter in series with the positive lead at the first power-up. A short circuit — the bulb lights up, the aircraft doesn't smoke.
- **Fuse** — on large aircraft on the power bus (not on the motors — the current is too high and pulsed) and on the companion bus.
- **Reverse polarity** — XT60/XT30 protect by their shape, but soldering one backwards kills the board in a second. A Schottky diode in series (0.3–0.5 V drop) or a P-MOSFET ideal diode for low-voltage branches.
- **Connectors** (course rule — Amass datasheets, links in the references): continuous current is the datasheet's recommended current for your wire gauge at ≤ 60 K temperature rise; short-term (up to 1 min) — no more than the datasheet's instantaneous current. XT30 — 15 A on 18 AWG (20 A on 16 AWG), up to 30 A briefly; XT60 — 30 A continuous and 60 A instantaneous on 12 AWG (datasheet V1.2 gives no conditions; Holybro gives the same 30 A for 4 h and 60 A for 1 min at < 60 K rise on 12 AWG); XT90 — 45 A on 12 AWG, 50 A on 10 AWG, 55 A on 8 AWG, up to 60 A for 1 min (UL1977 rating 30 A; 40 A appears only in retailer listings); AS150 — 75 A on 8 AWG, the Amass catalogue maximum at < 85 K rise, with no 1-minute figure. The catalogue is older than the datasheets and gives other XT figures (XT30 20 A, XT60 35 A, XT90 45 A — maximum at < 85 K); for XT the course uses the datasheets. A connector overloaded for its current (rated below the real current) heats up, a hot one oxidizes, an oxidized one heats up even more.

### Wire gauges
{{widget:wire-drop}}

Rule of thumb for short runs on board — **continuous** (cruise) current: 12 AWG up to ~60–80 A, 14 AWG up to ~40–50 A, 16 AWG up to ~25 A, 18 AWG up to ~15 A (course guideline), 20–22 AWG — signal and 5 V branches up to 2–3 A. **Peak** current (a punch, seconds) is checked not by this line but by the drop criterion: ≤ 1 % of the pack voltage on the power pair. So 14 AWG on a 5" with 60–100 A peaks (`f-power`) passes with short leads: a 0.2 m loop at 100 A gives 0.17 V, 0.75 % of 22.2 V. Long wires on a wing — one size up.

## practice
### Step 1. Power tree
Draw the tree for your build with the current on each branch (from the table and datasheets). The 5 V total and the 9–12 V total — separately.

### Step 2. Choosing BECs and wire gauges
For each branch: BEC type (buck/LDO), rating ≥ 1.5 × the total, input voltage with margin for a fully charged 6S (25.2 V). Wire gauge — from the table.

Calculation lab (no hardware): `power_lab.py` designs the power system of a 7-inch 6S quad: BEC branches, main lead gauge and connectors, bus capacitor voltage, the LC video filter for four capacitor ESR values, inrush and precharge, reverse-polarity protection. The script and its real output:

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
- Amass — XT90H-M datasheet (UL1977 30 A; 60 A for 1 min; recommended 45/50/55 A on 12/10/8 AWG at 60 K rise) | https://atta.szlcsc.com/upload/public/pdf/source/20220706/D6369ADC773D7B5378E901BEE0D5B60C.pdf | primary | A
- Amass — XT60H-M datasheet V1.2 (30 A continuous, 60 A instantaneous, 12 AWG) | https://cdn.eicom.ru/media/PDF/XT60H-M.pdf | primary | A
- Amass — XT30UPB datasheet (UL1977 15 A; 30 A for 1 min; 15 A on 18 AWG, 20 A on 16 AWG at 60 K rise) | https://atta.szlcsc.com/upload/public/pdf/source/20230412/7B5DFEF57C9EA5273853390C734B3AC5.pdf | primary | A
- Amass — product catalogue (AS150: 75 A MAX, 8 AWG, rise < 85 K) | https://www.rcscomponents.kiev.ua/datasheets/Amas-cat1.pdf | primary | B
- Holybro — Connector & Wire Rating (XT60 12 AWG: 30 A for 4 h and 60 A for 1 min at < 60 K rise) | https://docs.holybro.com/power-module-and-pdb/power-module/connector-and-wire-rating | secondary | B

## checklist
- The power tree is drawn with currents per branch
- BECs are chosen by type, current and input voltage
- Wire gauges and connectors are chosen by current
- The capacitor is installed, the effect is visible in the spectrum
- A smoke stopper is used at the first power-up
