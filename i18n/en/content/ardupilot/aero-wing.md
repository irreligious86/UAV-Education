---
id: aero-wing
title: "Wing Aerodynamics and Plane Flight Modes"
level: L3
readingTime: 40 min
firmware: ArduPlane · INAV
status: published
added: 2026-11-08
tags:
  - wing
  - stall
  - CG
  - TECS
  - airspeed
related:
  - f-aero-props
  - f-mechanics
  - inav-wing
  - ap-quadplane
next:
  - ap-heavy
source: content/ardupilot/aero-wing.md
source_hash: 623a5c3792d4
---

## summary
A wing flies differently: lift depends on the square of airspeed, it has a stall speed, the CG decides whether it is stable at all, and the autopilot does not control “altitude” and “speed” separately but energy (TECS). This module gives you the calculations to do before the first hand launch: lift and wing loading, stall and cruise speed, CG position and static margin — and ties them to the ArduPlane parameters (`ARSPD_*`, `TECS_*`, `AIRSPEED_CRUISE/MIN/MAX`, `TRIM_*`) and INAV ones (`nav_fw_*`, `fw_*`).

## theory
### Lift
L = ½ · ρ · V² · S · C_L — air density, airspeed squared, wing area, lift coefficient (depends on the angle of attack α and the airfoil; it grows roughly linearly up to the critical angle of 10–15°, then comes the **stall**). In level flight L = m·g.

- **Wing loading** W/S (g/dm² or N/m²): the higher it is, the faster you have to fly, and the worse the wing does in thermals and on landing. 1–1.5 m FPV wings: 30–60 g/dm²; mapping planes: 40–80; foam trainers: 20–35.
- **Stall speed**: V_s = √(2·m·g / (ρ·S·C_Lmax)). C_Lmax for simple airfoils without high-lift devices is 1.0–1.3. Example: m = 1.8 kg, S = 0.35 m², C_Lmax = 1.1 → V_s = √(2·1.8·9.81/(1.225·0.35·1.1)) ≈ 8.7 m/s. In a turn with bank angle φ the lift has to be larger: V_s(φ) = V_s/√cos φ — at 60° of bank the stall speed is 41% higher.
- **Cruise**: 1.3–1.6 V_s for economy (the best L/D is usually near 1.3 V_s), 2 V_s and above for speed/wind. The minimum safe airspeed in the autopilot is ≥ 1.2–1.3 V_s.
- **Drag** D = ½ρV²·S·C_D; C_D = C_D0 + k·C_L² (parasitic + induced). At low speed induced drag dominates (grows as 1/V²), at high speed parasitic drag does (V²). Minimum power is at a speed slightly below the minimum-drag speed: hence “fly slower than it feels” for endurance.

### CG and stability
A wing is stable in pitch if the center of gravity (CG) is ahead of the **neutral point** (the aerodynamic center of the whole aircraft). Static margin = (x_np − x_cg)/MAC (mean aerodynamic chord) — **5–15%** is normal; 0 is neutral (it flies but does not return by itself); negative is unstable (the autopilot will not save you when the control surfaces saturate).

For a flying wing (no tailplane) the neutral point is ≈ 25% MAC (quarter chord) with corrections for sweep; the CG is set at 15–20% MAC. Online wing CG calculators (from span, root/tip chord and sweep) do exactly this calculation. An aft CG means sharp, “twitchy” responses and a tendency to spin; a forward CG means a heavy nose, high landing speed and lots of up elevator.

Ground check: balance it on your fingertips/stands at the calculated point with the battery and all the payload. Flight check: the “dive test” — from level flight, let go of the sticks in a shallow dive: the plane pulls out to level by itself (forward CG — sharply; aft CG — it keeps diving/tucks in).

### Control surfaces and modes
Elevons (on a wing) mix elevator and ailerons; a conventional plane has separate surfaces. The autopilot stabilizes roll and pitch (`FBWA`), holds altitude and heading (`FBWB`, `CRUISE`), flies waypoints (`AUTO`), returns home (`RTL`), lands (`AUTOLAND`/`LAND`). Without an airspeed sensor the autopilot estimates airspeed from GPS and wind — worse in wind; with a pitot tube (`ARSPD_TYPE`, calibration `ARSPD_AUTOCAL`, `ARSPD_RATIO`) it is accurate.

### TECS: energy control
The total energy of the plane = potential (altitude) + kinetic (speed). Throttle changes the **sum** of the energy, the elevator changes the **split** between altitude and speed. TECS (Total Energy Control System) controls it exactly that way: `TECS_CLMB_MAX` (max climb, m/s at full throttle), `TECS_SINK_MIN` (sink at idle), `TECS_SINK_MAX`, `TECS_TIME_CONST`, `TECS_SPDWEIGHT` (0 — hold altitude at the cost of speed, 2 — hold speed at the cost of altitude; 1 — balance, the default; 2 — pitch holds speed only, throttle holds altitude, recommended for gliders), `TECS_PTCH_DAMP`, `TECS_THR_DAMP`. Speeds: `AIRSPEED_MIN` (≥ 1.2 V_s), `AIRSPEED_CRUISE`, `AIRSPEED_MAX`, `TRIM_THROTTLE` (cruise throttle), `THR_MIN/MAX`. `AIRSPEED_STALL` is used for warnings/protection.

INAV: `nav_fw_cruise_speed`, `nav_fw_min_thr/max_thr/cruise_thr`, `nav_fw_climb_angle/dive_angle`, `fw_min_throttle_down_pitch` — simpler, no energy model, but the same idea: throttle for climb, pitch for speed.

### Launch and landing
Hand launch/catapult: `TKOFF_THR_MINACC` (launch detection by acceleration), `TKOFF_THR_DELAY`, `TKOFF_LVL_ALT`; INAV — autolaunch (`nav_fw_launch_*`). Landing: glide slope `LAND_PITCH_DEG`, `LAND_FLARE_ALT/SEC`, a rangefinder for the flare; a wing lands on its belly into the wind at 1.1–1.2 V_s.

{{diagram:chart-wing-stall-prevention|С AIRSPEED_STALL = 0 ArduPlane 4.7 считает сваливанием AIRSPEED_MIN и держит крен на 25° до 10.5 м/с; с AIRSPEED_STALL = 8.5 полный ROLL_LIMIT_DEG 45° доступен уже с 10.1 м/с.}}

{{diagram:tecs-energy|TECS: the total energy error (altitude + speed) is closed with throttle, the error in their balance with pitch; that is why climbing without throttle headroom eats your airspeed.}}

## practice
### Step 1. Wing calculation
Measure the span, root and tip chords, sweep; calculate S, MAC, wing loading, V_s (C_Lmax 1.1 for an airfoil without high-lift devices), cruise at 1.4 V_s, V_s in a 45° bank.

### Step 2. CG
Find the neutral point (a wing calculator, or 25% MAC for a conventional plane ignoring the tailplane — with it the formula gets more complex, use a calculator), pick a 10% margin, mark the CG point, balance it with the battery. Write down the mass, CG and margin.

### Step 2a. Script: ArduPlane formulas on your numbers (code and output as in the source module)

```python
#!/usr/bin/env python3
"""Wing lab for module aero-wing: the module's worked example plus the ArduPlane 4.7.2 formulas
for stall prevention and the TECS energy split (stdlib only). Run: python3 wing_lab.py

Firmware references (ArduPilot tag ArduPlane-4.7.2):
  ArduPlane/Attitude.cpp:677-762  update_load_factor(), apply_load_factor_roll_limits()
  libraries/AP_TECS/AP_TECS.cpp:420-433  _TASmin = AIRSPEED_MIN*EAS2TAS, raised by sqrt(load factor)
  libraries/AP_TECS/AP_TECS.cpp:1250-1251  STEdot_max = TECS_CLMB_MAX*g, STEdot_min = -TECS_SINK_MIN*g
"""
import math

G, RHO0 = 9.81, 1.225


def isa_rho(h_m):
    """ISA troposphere density, kg/m^3."""
    t = 288.15 - 0.0065 * h_m
    p = 101325 * (t / 288.15) ** 5.2559
    return p / (287.05 * t)


def stall_speed(m, s, cl_max, rho=RHO0):
    return math.sqrt(2 * m * G / (rho * s * cl_max))


def ap_roll_limit(v, airspeed_min, airspeed_stall=0.0, roll_limit=45, level_roll_limit=5):
    """apply_load_factor_roll_limits() for a demanded bank of 85 deg, default FLIGHT_OPTIONS."""
    vs1g = airspeed_stall if airspeed_stall > 0 else airspeed_min
    n_max = (v / max(vs1g, 1)) ** 2
    n_dem = 1 / math.cos(math.radians(85))
    if n_max <= 1:
        lim = 25
    elif n_max < n_dem:
        lim = max(math.degrees(math.acos(1 / n_max)), 25, level_roll_limit)
    else:
        lim = roll_limit
    return min(lim, roll_limit)


def tecs_min_speed(bank_deg, airspeed_min, airspeed_stall=0.0):
    """_TASmin at sea level with STALL_PREVENTION=1 (EAS2TAS = 1)."""
    n = 1 / math.cos(math.radians(bank_deg))
    if airspeed_stall > 0:
        return max(airspeed_min, airspeed_stall * math.sqrt(n))
    return airspeed_min * math.sqrt(n)


m, S, CL = 2.0, 0.4, 1.1
vs = stall_speed(m, S, CL)
print(f"1) W/S = {m / S:.1f} kg/m^2 = {m * 1000 / (S * 100):.0f} g/dm^2; V_s = {vs:.2f} m/s; "
      f"cruise 1.4*V_s = {1.4 * vs:.1f} m/s; AIRSPEED_MIN >= 1.2*V_s = {1.2 * vs:.1f} m/s")
for phi in (30, 45, 60):
    n = 1 / math.cos(math.radians(phi))
    print(f"   bank {phi:2} deg: n = {n:.2f} g, V_s(bank) = {vs * math.sqrt(n):.2f} m/s")

print("2) EAS vs TAS (AIRSPEED_* are EAS; TECS multiplies by EAS2TAS):")
for h in (0, 1500, 3000):
    rho = isa_rho(h)
    print(f"   {h:4} m ISA: rho = {rho:.3f}, EAS2TAS = {math.sqrt(RHO0 / rho):.3f}, "
          f"stall TAS = {vs * math.sqrt(RHO0 / rho):.2f} m/s, stall EAS = {vs:.2f} m/s")

print("3) Stall prevention bank limit (ROLL_LIMIT_DEG 45, LEVEL_ROLL_LIMIT 5):")
print("   V m/s | AIRSPEED_STALL=0 (uses MIN=10) | AIRSPEED_STALL=8.5")
for v in (9, 10, 11, 12, 13, 15):
    print(f"   {v:5} | {ap_roll_limit(v, 10):26.1f} | {ap_roll_limit(v, 10, 8.5):12.1f}")

print("4) TECS minimum airspeed in a turn (STALL_PREVENTION=1):")
for phi in (0, 30, 45, 60):
    print(f"   bank {phi:2}: MIN=10,STALL=0 -> {tecs_min_speed(phi, 10):5.2f} m/s; "
          f"MIN=10,STALL=8.5 -> {tecs_min_speed(phi, 10, 8.5):5.2f} m/s")

print("5) Energy trade at cruise:")
v1, v2 = 12.0, 10.0
print(f"   slowing {v1:.0f} -> {v2:.0f} m/s frees dh = (v1^2 - v2^2)/(2g) = {(v1**2 - v2**2) / (2 * G):.2f} m")
clmb, sink = 5.0, 2.0     # TECS_CLMB_MAX, TECS_SINK_MIN defaults (AP_TECS.cpp:27,35)
print(f"   STEdot_max = CLMB_MAX*g = {clmb * G:.1f} W/kg, STEdot_min = -SINK_MIN*g = {-sink * G:.1f} W/kg")
print(f"   climb demand 5 m/s while accelerating 1 m/s^2 at 12 m/s needs "
      f"{5 * G + 12 * 1.0:.1f} W/kg > STEdot_max -> speed or height has to give")
```

```text
1) W/S = 5.0 kg/m^2 = 50 g/dm^2; V_s = 8.53 m/s; cruise 1.4*V_s = 11.9 m/s; AIRSPEED_MIN >= 1.2*V_s = 10.2 m/s
   bank 30 deg: n = 1.15 g, V_s(bank) = 9.17 m/s
   bank 45 deg: n = 1.41 g, V_s(bank) = 10.15 m/s
   bank 60 deg: n = 2.00 g, V_s(bank) = 12.07 m/s
2) EAS vs TAS (AIRSPEED_* are EAS; TECS multiplies by EAS2TAS):
      0 m ISA: rho = 1.225, EAS2TAS = 1.000, stall TAS = 8.53 m/s, stall EAS = 8.53 m/s
   1500 m ISA: rho = 1.058, EAS2TAS = 1.076, stall TAS = 9.18 m/s, stall EAS = 8.53 m/s
   3000 m ISA: rho = 0.909, EAS2TAS = 1.161, stall TAS = 9.90 m/s, stall EAS = 8.53 m/s
3) Stall prevention bank limit (ROLL_LIMIT_DEG 45, LEVEL_ROLL_LIMIT 5):
   V m/s | AIRSPEED_STALL=0 (uses MIN=10) | AIRSPEED_STALL=8.5
       9 |                       25.0 |         26.9
      10 |                       25.0 |         43.7
      11 |                       34.3 |         45.0
      12 |                       45.0 |         45.0
      13 |                       45.0 |         45.0
      15 |                       45.0 |         45.0
4) TECS minimum airspeed in a turn (STALL_PREVENTION=1):
   bank  0: MIN=10,STALL=0 -> 10.00 m/s; MIN=10,STALL=8.5 -> 10.00 m/s
   bank 30: MIN=10,STALL=0 -> 10.75 m/s; MIN=10,STALL=8.5 -> 10.00 m/s
   bank 45: MIN=10,STALL=0 -> 11.89 m/s; MIN=10,STALL=8.5 -> 10.11 m/s
   bank 60: MIN=10,STALL=0 -> 14.14 m/s; MIN=10,STALL=8.5 -> 12.02 m/s
5) Energy trade at cruise:
   slowing 12 -> 10 m/s frees dh = (v1^2 - v2^2)/(2g) = 2.24 m
   STEdot_max = CLMB_MAX*g = 49.1 W/kg, STEdot_min = -SINK_MIN*g = -19.6 W/kg
   climb demand 5 m/s while accelerating 1 m/s^2 at 12 m/s needs 61.1 W/kg > STEdot_max -> speed or height has to give
```

### Step 3. Parameters
ArduPlane: `AIRSPEED_MIN/CRUISE/MAX`, starting `TECS_*`, `TRIM_THROTTLE`, `ARSPD_*` if you have a pitot tube. INAV: `nav_fw_*`. Justify every number with the calculation from step 1.

### Step 4. Checking against flight
First flight in FBWA at altitude: slowly bleed off speed until the stall begins (wobbling, nose drop) — write down the speed from airspeed/GPS; compare it with the calculated V_s (the difference is usually 10–20% because of C_Lmax and measurement errors). Dive test for the CG. Log: `TECS`, `ARSP`, `CTUN.NavPitch`.

### Worked calculation for self-check
A wing with an area of 0.4 m², takeoff mass 2 kg: wing loading 5 kg/m². Stall speed V_s = √(2·m·g / (ρ·S·C_Lmax)) = √(2·2·9.81 / (1.225·0.4·1.1)) ≈ 8.5 m/s. Cruise ≈ 1.4·V_s ≈ 12 m/s. In a turn with 45° of bank the stall speed grows by a factor of 1/√cos45° ≈ 1.19 — to ≈ 10.1 m/s. That is why `AIRSPEED_MIN` is set no lower than ~1.2·V_s ≈ 10 m/s: in a straight line that is still a margin, in a steep turn it is already the edge.

{{diagram:chart-wing-stall-bank|Для крыла 0.4 м², 2 кг (V_s ≈ 8.5 м/с) скорость сваливания в вираже догоняет AIRSPEED_MIN = 1.2·V_s при крене 46°, а крейсер 1.4·V_s — при 59°.}}

### What you should end up with and what to record
- **Calculation table:** S, MAC, loading, V_s, cruise, V_s in a 45° bank. Every number can be reproduced from the formula.
- **CG:** the CG point is marked on the wing, a margin of 10 % of MAC. The plane, held on your fingertips at this point, hangs slightly nose down.
- **Flight check:** the measured stall onset speed usually differs from the calculated one by 10–20 % — because of C_Lmax and airspeed measurement error. Write down both and the difference, and refine `AIRSPEED_MIN` from the measurement.
- **Parameters:** for `AIRSPEED_MIN/CRUISE/MAX`, `TRIM_THROTTLE` and the starting `TECS_*` — one line of justification from the calculation or a measurement. From there the “ArduPlane Tuning” module refines them.

The lab counts as done when the CG and margin are calculated and marked on the wing, the stall and cruise speeds are estimated by calculation and checked against flight, and the speed and TECS parameters are explained through the calculation.

## diagnostics
- **Symptom:** the plane “nose-drops” and sinks in a turn
  - Possible cause: a stall — the speed in the turn is below V_s/√cos φ.
  - What to do: raise `AIRSPEED_MIN`, limit bank (`ROLL_LIMIT_DEG`), raise cruise.
- **Symptom:** twitchy in pitch, won't hold trim
  - Possible cause: aft CG, small margin.
  - What to do: move the CG forward by 2–5% MAC, dive test.
- **Symptom:** loses altitude when speeding up in AUTO
  - Possible cause: `TECS_SPDWEIGHT` close to 2 with weak throttle / `TECS_CLMB_MAX` set too high.
  - What to do: a real `TECS_CLMB_MAX` from a full-throttle test, SPDWEIGHT 1.
- **Symptom:** airspeed reads garbage on the ground
  - Possible cause: the tube is not calibrated, blocked, condensation.
  - What to do: `ARSPD_AUTOCAL`, warm-up, blow it out; a pre-arm airspeed check.
- **Symptom:** on a hand launch the autopilot does not give throttle
  - Possible cause: `TKOFF_THR_MINACC` not reached / the delay.
  - What to do: throw harder, lower the threshold, check arming and the mode.

## references
- ArduPlane — TECS (Total Energy Control System) tuning | https://ardupilot.org/plane/docs/tecs-total-energy-control-system-for-speed-height-tuning-guide.html | primary | A
- ArduPlane — Airspeed sensor setup and calibration | https://ardupilot.org/plane/docs/airspeed.html | primary | A
- NASA Glenn — Lift equation (Beginner's Guide to Aeronautics) | https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/lift-equation/ | primary | A

## checklist
- I calculated S, MAC, wing loading and V_s for my wing
- I know how V_s grows in a turn and why AIRSPEED_MIN ≥ 1.2 V_s
- The CG is set with a 5–15% margin and verified with a dive test
- I understand TECS: throttle is energy, pitch is the split
- The speed and TECS parameters are justified by calculation and checked against flight
