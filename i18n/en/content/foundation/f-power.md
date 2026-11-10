---
id: f-power
title: "Power: LiPo, Li-Ion, BEC"
level: L1
readingTime: 20 min
firmware: any firmware
status: published
added: 2026-11-07
tags:
  - LiPo
  - Li-Ion
  - power
related:
  - f-physics
  - f-motors-esc
next:
  - f-motors-esc
source: content/foundation/f-power.md
source_hash: 8f2bad187c7c
---

## summary
The battery is the heaviest and the most dangerous part of a drone. This module explains how LiPo differs from Li-Ion, what “S”, “mAh” and “C” really mean, why voltage sags under load, how to estimate flight time, and how to burn down neither the battery nor the workshop. At the end — a real log from a heavy 10", where the voltage sag told more than any spec sheet.

## theory
### Designations
- **S** — the number of cells in series. 6S = 6 cells, the voltages add up.
- **mAh** — capacity. 1300 mAh = 1.3 Ah.
- **C** — discharge current as a multiple of capacity. 1300 mAh × 100C = 130 A according to the label. Marketing C ratings are almost always inflated; go by internal resistance and real tests.
- **P** — parallel cells in packs built from cylindrical cells (6S2P = 12 cells).

### LiPo vs. Li-Ion
- **LiPo:** nominal 3.7 V/cell, full charge 4.2 V (LiHV — 4.35 V). Delivers huge currents, but less energy per gram. For freestyle, racing, anything with high currents and short flights.
- **Li-Ion (18650, 21700):** nominal around 3.6 V, full 4.2 V, deeper discharge — down to 2.8–3.0 V. Noticeably more energy per gram, more modest currents. For long-range 7–10", wings, long hovers at moderate throttle.

Selection rule: if the average current per cell is low (long-range flight, a wing), Li-Ion gives more minutes. If you need peaks of tens of amps — LiPo.

### Voltage sag
Every cell has an internal resistance R. Under a current I the voltage drops by I × R. On a sharp throttle punch the sag is instant, and the flight controller sees not “how much is left” but “how much is left minus the sag”. Hence false low-voltage warnings on punches, and real ESC cutouts with a depleted battery.

### Flight time
Estimate: time, min ≈ usable capacity, Ah / average current, A × 60. Usable capacity is about 80% of nominal: never run it down to zero. Take the average current from the log, not out of your head.

### BEC and onboard voltages
The flight controller, receiver, camera and VTX run on 5, 9 or 12 V, not on 6S. These voltages come from BECs — regulators on the flight controller or the ESC. Before connecting peripherals, check: which pad it is powered from, whether the BEC has enough current (a VTX at high power can draw more than an amp), and that the VTX is not connected to 5 V if it needs 9–12 V.

### Case study: voltage sag on a 10"
A log from a heavy 10" on 6S (battery at 23.8 V at the start of the flight): median current 14–16 A, but p95 on an aggressive profile was 124 A, with a peak of 147 A. At those peaks the voltage dropped to 16.2 V, i.e. 2.7 V per cell. Conclusion: at such currents the battery is working at its limit, and the ESC must be checked for a continuous current of about 125 A. No label would have told you that — the log did.

### Calculating flight time honestly
t ≈ (capacity × usable fraction) / average current. The fraction: 0.8 for LiPo (land at 3.5 V/cell), 0.85 for Li-Ion (down to 3.0 V/cell). The average current comes from the log (`BAT.Curr`/`amperageLatest`), not from hover: a 5" freestyle — 25–40 A average with 60–100 A peaks; a 7" long range cruising — 8–12 A; a 15" X8 hover — 56 A. Example: a 6S 4000 mAh Li-Ion on a 7" at 10 A: 0.85 × 4 / 10 × 60 ≈ 20 min. Check after the flight: the mAh put back by the charger should match `CurrTot`/mAh drawn in the log within ±10% — otherwise the current sensor is calibrated wrong (`BATT_AMP_PERVLT`, `ibata_scale`).

### Voltage sag and internal resistance in numbers
U under load = E − I·R. A “fresh” LiPo 6S 1300 mAh 100C: R ≈ 2 mΩ/cell → 12 mΩ/pack; at 80 A the sag is 1 V (4.0 → 3.84 V/cell). The same pack after 150 cycles — 6 mΩ/cell → 36 mΩ → 2.9 V of sag: that's why “old” packs trigger the OSD warning on the very first punch. A Li-Ion 6S4P P42A ≈ 40–50 mΩ/pack: at 60 A — 2.4–3 V, one cell's worth “disappears”; that's why warning thresholds are set by voltage **under load** or by mAh. Heat: 60 A × 60 A × 0.045 Ω = 160 W in the pack — a Li-Ion heats up noticeably; a 100C LiPo — 80 × 80 × 0.012 = 77 W. In detail (chemistries, packs, BMS) — the “Li-Ion Packs” module.

### Charging, storage, disposal
Balance charge at 1C (LiPo) / 0.5–1C (Li-Ion), up to 4.2 V/cell (4.1 gives longer life); storage at 3.8 V/cell (LiPo) / 3.6–3.7 (Li-Ion), no longer than a day at full charge; cell spread after charging ≤ 0.02 V, after a flight ≤ 0.05 — more means a weak cell; per-cell IR in the charger as a “health record”; puffing/puncture — retire it (discharge in salt water, dispose of it). In winter: below 10 °C a LiPo loses up to 30–50% of its output — warm it to 20–30 °C before flying.

### BEC rails: the budget
The 5 V sum: FC 0.2 + RX 0.2 + GPS 0.1 + LED 0.5 ≈ 1 A → the board's 5 V/2–3 A BEC is enough; add a Raspberry Pi (2–3 A) — not enough, use a separate BEC. 9–12 V: a digital air unit at 0.8–1.2 A → a 9 V/2 A BEC on the FC is cutting it close when it heats up; a separate 3 A BEC is more relaxed. All the numbers go into the build sheet (the “Power Circuit Design” module).

{{diagram:flight-time-chain|An honest flight-time calculation: the usable fraction of capacity, the average current over the whole profile, corrections for conditions.}}

{{diagram:chart-discharge|Discharge curves: under load a cell sags by I·R, so a LiPo at 40C hits 3.5 V sooner, and a Li-Ion at 3C loses a noticeable part of its capacity before cutoff. The curve shapes are typical, the resistances come from the module's examples.}}

## practice
### Handling LiPo safely
1. Charge at 1C, on a non-flammable surface, supervised, with balancing.
2. Storage — around 3.8 V/cell (Storage mode on the charger). A full battery sitting on a shelf for weeks degrades and puffs up.
3. A puffed, punctured battery or one with damaged wrap is taken out of service.
4. Transport — in a fireproof bag or box.
5. After a hard crash, set the battery aside and watch it before charging.

### Lab: calculate flight time and check it against the log
1. Take the battery capacity and the average current from the Blackbox or DataFlash log.
2. Calculate the estimate: 0.8 × capacity, Ah / current × 60.
3. Compare it with the real flight time up to the voltage warning.
4. Find the minimum voltage under load in the log and convert it to per-cell.

### Setting up voltage monitoring
In Betaflight, check the voltage and current sensor scale (Power & Battery) against a multimeter, and set up the OSD warnings so that you land with margin, not on a “too late already” signal.

## diagnostics
- **Symptom:** a low-voltage warning on every punch
  - Possible cause: sag under current, an old battery with high internal resistance.
  - What to do: look at the resting voltage after the flight, measure internal resistance with the charger.
- **Symptom:** flight time is much shorter than calculated
  - Possible cause: the average current is higher than it seemed, or the battery has lost capacity.
  - What to do: take the average current from the log, check the capacity with a charge cycle.
- **Symptom:** the VTX or camera reboots on throttle
  - Possible cause: sag on the BEC rail, or power from the wrong pad.
  - What to do: check the power pad, add a capacitor on the power bus, check the BEC current.
- **Symptom:** the battery is warm and puffed after a flight
  - Possible cause: current overload.
  - What to do: take the battery out of service, reconsider the capacity/C rating for the real current.

## references
- Betaflight App — tabs reference (Power & Battery) | https://betaflight.com/docs/wiki/app | primary | A
- Battery Monitors — ArduPilot Copter | https://ardupilot.org/copter/docs/common-powermodule-landingpage.html | primary | A
- LiPo Battery Guide — Oscar Liang | https://oscarliang.com/lipo-battery-guide/ | secondary | B

## checklist
- I understand the difference between S, P, mAh and C
- I know when to choose Li-Ion and when LiPo
- I calculated flight time and checked it against the log
- I checked the voltage sensor scale with a multimeter
- Batteries are stored at storage voltage and in a fireproof container
