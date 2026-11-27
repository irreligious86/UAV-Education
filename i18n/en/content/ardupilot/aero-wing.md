---
id: aero-wing
title: "Wing aerodynamics and fixed-wing modes"
level: L3
readingTime: 40 min
firmware: ArduPlane 4.7 (checked against 4.7.3) · INAV 9.1.0
status: published
added: 2026-11-08
tags:
  - fixed wing
  - stall
  - center of gravity
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
source_hash: 5a4747987a5a
---

## summary
A wing flies differently: lift depends on speed squared, it has a stall speed, the center of gravity decides whether it is stable at all, and the autopilot does not control "altitude" and "speed" separately but energy (TECS). This module gives the calculations you need to do before the first launch (lift and wing loading, stall speed and cruise speed, center of gravity position and static margin) and ties them to the parameters of ArduPlane (`ARSPD_*`, `TECS_*`, `AIRSPEED_CRUISE/MIN/MAX`, `TRIM_*`) and INAV (`nav_fw_*`, `fw_*`).

## theory
### Lift
L = ½ · ρ · V² · S · C_L: air density, speed squared, wing area, and the lift coefficient (which depends on the angle of attack α and the airfoil; it grows roughly linearly up to the critical angle of 10–15°, and then comes the **stall**). In level flight L = m·g.

- **Wing loading** W/S (g/dm² or N/m²): the higher it is, the faster you have to fly and the worse the aircraft is in thermals and on landing. FPV wings of 1–1.5 m: 30–60 g/dm²; mappers: 40–80; foam trainers: 20–35.
- **Stall speed**: V_s = √(2·m·g / (ρ·S·C_Lmax)). C_Lmax for simple airfoils without high-lift devices is 1.0–1.3. Example: m = 1.8 kg, S = 0.35 m², C_Lmax = 1.1 → V_s = √(2·1.8·9.81/(1.225·0.35·1.1)) ≈ 8.7 m/s. In a turn at bank angle φ the lift has to be higher: V_s(φ) = V_s/√cos φ, so at 60° of bank the stall comes 41% faster.
- **Cruise**: 1.3–1.6 V_s for economy (the best L/D is usually near 1.3 V_s), 2 V_s and above for speed or wind. The minimum safe airspeed in the autopilot is ≥ 1.2–1.3 V_s.
- **Drag** D = ½ρV²·S·C_D; C_D = C_D0 + k·C_L² (parasite plus induced). At low speed induced drag dominates (it grows as 1/V²), at high speed parasite drag does (V²). Minimum power is at a speed slightly below minimum drag: hence "fly slower than you think" for endurance.

### Center of gravity and stability
A wing is stable in pitch if the center of gravity (CG) is ahead of the **neutral point** (the aerodynamic center of the whole aircraft). The static margin = (x_np − x_cg)/MAC (mean aerodynamic chord); **5–15%** is normal; 0 is neutral (it flies but does not recover by itself); negative is unstable (the autopilot cannot save it once the surfaces saturate).

For a flying wing (no tailplane) the neutral point is ≈ 25% MAC (the quarter chord) with corrections for sweep; the CG goes at 15–20% MAC. Online CG calculators for wings (from span, root and tip chord, and sweep) do exactly this calculation. An aft CG gives sharp, twitchy responses and a tendency to spin; a forward CG gives a heavy nose, a high landing speed, and a need for a lot of up elevator.

Ground check: balance it on your fingers or on stands at the calculated point with the battery and the whole payload. Flight check, the "dive test": from level flight put it into a shallow dive and release the sticks: the plane pulls out to level by itself (with a forward CG it does so sharply; with an aft CG it keeps diving or tucks under).

### Controls and modes
Elevons (on a wing) mix elevator and ailerons; a conventional layout has separate surfaces. The autopilot stabilizes roll and pitch (`FBWA`), holds altitude and heading (`FBWB`, `CRUISE`), flies waypoints (`AUTO`), returns (`RTL`), and lands (the `AUTOLAND` mode, added in ArduPlane 4.7: a landing without a mission along the takeoff direction, with the approach point placed behind along the takeoff heading and offset by `AUTOLAND_DIR_OFF`; in a mission, `NAV_LAND`). Without an airspeed sensor the autopilot estimates airspeed from GPS and wind, which is worse in wind; with a pitot tube (`ARSPD_TYPE`, calibration with `ARSPD_AUTOCAL`, `ARSPD_RATIO`) it is accurate.

### Which speed the autopilot measures: IAS, EAS, TAS
A pitot tube measures dynamic pressure q = ½·ρ·V². ArduPilot converts it to airspeed as V = √(`ARSPD_RATIO`·Δp) (`AP_Airspeed.cpp:697–708`; `ARSPD_RATIO` defaults to 2 and is refined by calibration). With a correct calibration this is equivalent airspeed, EAS: the speed that would give the same pressure at the sea-level density of 1.225 kg/m³. Lift depends on q, not on true airspeed: L = q·S·C_L. So the stall speed in EAS is the same at any altitude, while true airspeed (TAS) grows as √(ρ₀/ρ). ArduPlane sets all `AIRSPEED_*` parameters in EAS, and TECS converts them to TAS by multiplying by EAS2TAS (`AP_TECS.cpp:420`). The module's example (V_s = 8.53 m/s EAS) in the standard atmosphere: at 1500 m ρ = 1.058, EAS2TAS = 1.076, V_s in TAS is 9.18 m/s; at 3000 m ρ = 0.909, EAS2TAS = 1.161, V_s in TAS is 9.90 m/s. The conclusion: you do not need to change `AIRSPEED_MIN` for a mountain field, but at the same EAS the ground speed at touchdown is higher, so the ground roll is longer. Ground speed = TAS ± wind, so you cannot see a stall in GPS speed: with an 8 m/s tailwind a wing with a V_s of 8.5 stalls at a ground speed of 16.5 m/s.

### Do you need an airspeed sensor
For an FPV wing in FBWA, no; for AUTO, RTL, and especially VTOL transitions, it is highly desirable. Without a sensor TECS sets the speed weighting to 0 (`AP_TECS.cpp:995–996`): pitch holds altitude only, and throttle starts from `TRIM_THROTTLE` and rises linearly with pitch to `THR_MAX` at the maximum climb pitch (and falls to `THR_MIN` in a dive), plus the turn compensation `TECS_RLL2THR` (`AP_TECS.cpp:930–958`), almost as in INAV. So `TRIM_THROTTLE` must be the throttle of the real cruise, otherwise the airspeed is uncontrolled in wind and in turns. Synthetic airspeed (`TECS_SYNAIRSPEED`, 0 by default) exists, but the firmware itself warns in the parameter description about a poor estimate when the wind is inaccurate. Connecting a sensor comes with two traps. `ARSPD_USE` defaults to 0: the airspeed is logged but not used for control; for control you need 1. `ARSPD_AUTOCAL` is for a single calibration flight: the firmware saves a new `ARSPD_RATIO` about once a minute at most, if it has changed by more than 5%, and leaving it enabled is not recommended. Tube installation and calibration are covered in the tuning module.

{{lesson:ap-plane-tuning|Where to mount the pitot tube, how to calibrate ARSPD_*, and how to set up TECS from test flights.}}

### TECS: energy control
The total energy of a plane = potential (altitude) + kinetic (speed). Throttle changes the **sum** of energy, the elevator changes its **distribution** between altitude and speed. TECS (Total Energy Control System) works with specific energies per kilogram of mass: SPE = g·h and SKE = ½·V². The error in the sum, STE, is closed by throttle, and the error in the balance, SEB = SPE·w_h − SKE·w_v, by pitch (`AP_TECS.cpp:738`, `:1022`). The exchange rate is easy to calculate: slowing from 12 to 10 m/s gives back (12² − 10²)/(2g) ≈ 2.2 m of altitude. That is why a wing sags when it is told to climb and accelerate at the same time.

`TECS_CLMB_MAX` (5 m/s by default) is not a wish but a model of the plane. TECS assumes that full throttle gives a specific energy rate of CLMB_MAX·g = 49 W/kg, and that `THR_MIN` throttle at `TECS_SINK_MIN` = 2 m/s gives a loss of 19.6 W/kg (`AP_TECS.cpp:1250–1251`). Between those points throttle is interpolated linearly (`:756`). If CLMB_MAX is too high, TECS demands a climb the motor cannot deliver: throttle hits the maximum and airspeed pays the difference. A demand to "climb at 5 m/s and accelerate at 1 m/s² at 12 m/s" needs 5·9.81 + 12·1 = 61 W/kg, more than the model, so something gives.

`TECS_SPDWEIGHT` (0…2, default 1) decides what gives. With 0, pitch holds altitude only and throttle holds airspeed; when throttle saturates, airspeed goes. With 2, pitch holds airspeed only and throttle holds altitude (recommended for gliders); when throttle saturates, altitude goes. 1 is a mix. The firmware overrides the weighting by itself (`AP_TECS.cpp:994–1013`): without airspeed and in the VTOL stage of a QuadPlane it is 0; in an underspeed condition, on takeoff, in an aborted landing, and when gliding at zero throttle it is 2; on landing the weighting is scaled smoothly toward zero unless `TECS_LAND_SPDWGT` is set. The other controls: `TECS_SINK_MAX` (5 m/s), `TECS_TIME_CONST` (5 s), `TECS_PTCH_DAMP` (0.3), `TECS_THR_DAMP` (0.5), `TECS_PITCH_MAX` (15°, limits the climb in automatic modes). Airspeeds: `AIRSPEED_MIN` (≥ 1.2 V_s), `AIRSPEED_CRUISE`, `AIRSPEED_MAX`, `TRIM_THROTTLE` (cruise throttle), `THR_MIN/MAX`. `AIRSPEED_STALL` is the stall speed for STALL_PREVENTION and the minimum airspeed on the final stage of landing (the parameter description in `Parameters.cpp:306–312`).

INAV 9.1 is built differently, with no energy model. Pitch holds altitude within `nav_fw_climb_angle` (20°) and `nav_fw_dive_angle` (15°). Throttle is derived from pitch: throttle = `nav_fw_cruise_thr` − `nav_fw_pitch2thr`·pitch (1400 µs and 10 by default; pitch is negative in a climb, so throttle rises), within `nav_fw_min_thr`…`nav_fw_max_thr` (1200…1700). This loop does not hold airspeed; the code adds throttle if the GPS speed is below 7 m/s. `nav_fw_cruise_speed` (cm/s) is used only to estimate remaining flight time and distance, not as a speed target (the descriptions are in `src/main/fc/settings.yaml`). `fw_min_throttle_down_pitch` lowers the nose at zero throttle in ANGLE.

### Turns: load factor and STALL_PREVENTION
In a coordinated turn at bank angle φ the lift must be n = 1/cos φ times the weight: 1.15 at 30°, 1.41 at 45°, 2.0 at 60°. The stall speed grows as √n: for the module's example, 9.17, 10.15, and 12.07 m/s. ArduPlane calculates this by itself if `STALL_PREVENTION` = 1 (the default). From the demanded roll it gets the load factor (`Attitude.cpp:686`), and at the current airspeed V it allows no more than n_max = (V/V_s1g)², that is, a roll of no more than arccos(1/n_max) (`Attitude.cpp:723–746`). The lower limit is 25°, "so you can still steer with a poor airspeed estimate". With `FLIGHT_OPTIONS` bit 16, a sensor, and `AIRSPEED_STALL` set, the limit drops to `LEVEL_ROLL_LIMIT` (5°). At the same time TECS raises the minimum airspeed by a factor of √n (`AP_TECS.cpp:426–433`).

The trap is `AIRSPEED_STALL` = 0 (the default). The firmware then takes `AIRSPEED_MIN` as the stall speed, that is, the 1.2 V_s from our rule, and already limits the roll at that speed. For the module's example (`AIRSPEED_MIN` 10 m/s): at 10 m/s it allows 25°, at 11 m/s 34°, and only at 12 m/s the full 45° of `ROLL_LIMIT_DEG`. With `AIRSPEED_STALL` = 8.5 (the calculated V_s) you already get 43.7° at 10 m/s. The TECS minimum airspeed in a 45° turn is 11.9 m/s against 10.1. The parameter description advises setting `AIRSPEED_STALL` slightly above the true stall speed, so use the one measured in step 5 of the practice, not the calculated one.

{{diagram:chart-wing-stall-prevention|With AIRSPEED_STALL = 0, ArduPlane 4.7 treats AIRSPEED_MIN as the stall speed and holds the roll at 25° up to 10.5 m/s; with AIRSPEED_STALL = 8.5 the full ROLL_LIMIT_DEG of 45° is available from 10.1 m/s.}}

### Launch and landing
Hand launch or catapult: `TKOFF_THR_MINACC` (launch detection by acceleration), `TKOFF_THR_DELAY`, `TKOFF_LVL_ALT`; in INAV, autolaunch (`nav_fw_launch_*`). Landing: the final pitch `LAND_PITCH_DEG`, `LAND_FLARE_ALT/SEC`, a rangefinder for the flare; a wing lands on its belly into the wind at 1.1–1.2 V_s.

{{diagram:tecs-energy|TECS: the total energy error (altitude + speed) is closed by throttle, and the error in their balance by pitch; that is why a climb with no throttle margin eats airspeed.}}

### ArduPlane 4.7.2 parameter reference
The defaults come from the source of the 4.7.2 tag (`ArduPlane/Parameters.cpp`, `config.h`, `libraries/AP_TECS/AP_TECS.cpp`, `AP_Landing.cpp`, `AP_Airspeed_Params.cpp`). The old names were valid up to and including 4.4 and were renamed in 4.5.0 (`ArduPlane/ReleaseNotes.txt:2239–2253`).

| Parameter | Default | Unit | What it sets, how to choose it | Old name |
|---|---|---|---|---|
| `AIRSPEED_MIN` | 9 | m/s EAS | the lower airspeed limit in auto modes; ≥ 1.2·V_s | `ARSPD_FBW_MIN` |
| `AIRSPEED_CRUISE` | 12 | m/s EAS | cruise; 1.3–1.6·V_s | `TRIM_ARSPD_CM` (cm/s) |
| `AIRSPEED_MAX` | 22 | m/s EAS | the upper limit; below flutter and the airframe's Vne | `ARSPD_FBW_MAX` |
| `AIRSPEED_STALL` | 0 | m/s EAS | the 1g stall for STALL_PREVENTION; 0 = use `AIRSPEED_MIN` | — |
| `STALL_PREVENTION` | 1 | — | roll limiting and a higher minimum airspeed based on load factor | — |
| `ROLL_LIMIT_DEG` | 45 | ° | maximum bank angle | `LIM_ROLL_CD` (centidegrees) |
| `PTCH_LIM_MAX_DEG` / `PTCH_LIM_MIN_DEG` | 20 / −25 | ° | pitch limits | `LIM_PITCH_MAX` / `LIM_PITCH_MIN` |
| `TRIM_THROTTLE` | 45 | % | level cruise throttle; without a sensor, the basis of the TECS throttle | — |
| `THR_MIN` / `THR_MAX` | 0 / 100 | % | throttle limits in auto modes | — |
| `TECS_CLMB_MAX` | 5 | m/s | the climb at `THR_MAX` and cruise, from a test, not "with a margin" | — |
| `TECS_SINK_MIN` / `TECS_SINK_MAX` | 2 / 5 | m/s | the sink at `THR_MIN` / the maximum demand | — |
| `TECS_TIME_CONST` | 5 | s | how fast the height and speed loop is | — |
| `TECS_SPDWEIGHT` | 1 | — | 0 prioritizes height, 2 prioritizes speed | — |
| `TECS_PTCH_DAMP` / `TECS_THR_DAMP` | 0.3 / 0.5 | — | pitch and throttle damping | — |
| `TECS_PITCH_MAX` / `TECS_PITCH_MIN` | 15 / 0 | ° | pitch in auto modes; 0 = use `PTCH_LIM_*` | — |
| `TECS_SYNAIRSPEED` | 0 | — | synthetic airspeed without a sensor | — |
| `ARSPD_USE` | 0 | — | 1 uses the sensor for control, 0 only logs it | — |
| `ARSPD_RATIO` / `ARSPD_AUTOCAL` | 2 / 0 | — | V = √(ratio·Δp); automatic calibration for one flight | — |
| `TKOFF_THR_MINACC` / `TKOFF_THR_DELAY` | 0 / 2 | m/s² / 0.1 s | launch detection and the throttle delay | — |
| `LAND_PITCH_DEG` | 0 | ° | the pitch in the flare | `LAND_PITCH_CD` |
| `LAND_FLARE_ALT` / `LAND_FLARE_SEC` | 3 / 2 | m / s | the start of the flare | — |
| the `AUTOLAND` mode (number 26) | — | — | a landing without a mission along the takeoff direction (the approach point is `AUTOLAND_WP_DIST` behind along the takeoff heading, offset by `AUTOLAND_DIR_OFF`), since 4.7.0 | — |

### Place in the system

- **Receives:** the takeoff mass (`des-sizing`) and the wing area, from which wing loading and V_s are calculated; airspeed from the pitot tube: without it the autopilot estimates airspeed from GPS and wind.
- **Provides:** V_s and the cruise speed to `AIRSPEED_MIN`/`AIRSPEED_CRUISE` and the starting TECS values (`ap-plane-tuning`), and to the VTOL → fixed-wing transition threshold (`ap-quadplane`); the "CG ahead of the neutral point by 5–15% MAC" rule, calculated in `aero-stability`.
- **If you get it wrong here:** you underestimated V_s → `AIRSPEED_MIN` is too low → a stall right after the transition to the wing (`ap-quadplane`). An aft CG → sharp, twitchy pitch responses on the very first launch, which is why the CG is checked before AUTOTUNE (`ap-plane-tuning`).

## practice
### Step 1. Wing calculation
Measure the span, the root and tip chords, and the sweep; calculate S, MAC, wing loading, V_s (C_Lmax 1.1 for an airfoil without high-lift devices), a cruise speed of 1.4 V_s, and V_s in a 45° turn.

### Step 2. Center of gravity
Find the neutral point (a calculator for a wing, or 25% MAC for a conventional layout ignoring the tailplane; with it the formula is more involved, so use a calculator), choose a 10% margin, mark the CG point, and balance the aircraft with the battery. Record the mass, the CG, and the margin.

### Step 3. Script: ArduPlane's formulas on your numbers
So that the justification of the parameters in step 4 is not by eye, run the calculation with a script. It repeats the module's example and three functions of the 4.7.2 firmware covered in the theory: the roll limit in `apply_load_factor_roll_limits()`, the higher TECS minimum airspeed in a turn, and the `TECS_CLMB_MAX`/`TECS_SINK_MIN` energy model. All you need is Python 3. Save it as `wing_lab.py`, run `python3 wing_lab.py`, then replace `m, S, CL` and the speeds with your own.

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

The script output (Python 3, run while the module was being prepared):

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

How to read it. Line 1 is the step 1 table for the example: 50 g/dm², V_s 8.53 m/s, cruise 11.9, and a lower bound for `AIRSPEED_MIN` of 10.2. Block 2 shows that only TAS grows with altitude: in EAS, that is, in the units of `AIRSPEED_*`, the stall stays at 8.53 m/s. Block 3 is the main one for setup: with `AIRSPEED_STALL` = 0 the wing gets 34.3° of roll at 11 m/s instead of 45°. Block 4 is the same for airspeed: in a 45° turn TECS will not let it fly slower than 11.89 m/s. Block 5 converts energy into meters and shows when a demand exceeds the `TECS_CLMB_MAX` model.

### Step 4. Parameters
ArduPlane: `AIRSPEED_MIN/CRUISE/MAX`, `AIRSPEED_STALL` (after step 5, the measured stall speed), starting `TECS_*`, `TRIM_THROTTLE`, `ARSPD_*` if you have a pitot tube (and `ARSPD_USE` = 1). INAV: `nav_fw_*`. Justify every number with the calculation from steps 1 and 3.

### Step 5. Checking against a flight
A first flight in FBWA at altitude: slowly reduce the airspeed until the stall begins (wing rocking, a nose drop) and record the speed from the airspeed sensor or GPS; compare it with the calculated V_s (the difference is usually 10–20% because of C_Lmax and measurement errors). Do a dive test for the CG. Log: `TECS`, `ARSP`, `CTUN.NavPitch`.

Procedure and abort. Altitude at least 50 m above obstacles (a margin for the stall and the recovery), `STALL_PREVENTION` = 1, a spotter next to you. Reduce the airspeed smoothly, 1 m/s every few seconds, wings level. Abort: at the first sign of a stall (rocking, a nose drop, a wing dropping) apply throttle and push the stick forward until you are back at cruise speed. If the wing rolls off sharply (one wing panel stalling), stop testing this aircraft until the CG and its symmetry are checked. Acceptance criterion: two runs gave stall onset speeds that differ by no more than 1 m/s; their mean, with a small margin on top, is your `AIRSPEED_STALL`.

### Worked calculation for the self-check
A wing with an area of 0.4 m² and a takeoff mass of 2 kg: the wing loading is 5 kg/m². Stall speed V_s = √(2·m·g / (ρ·S·C_Lmax)) = √(2·2·9.81 / (1.225·0.4·1.1)) ≈ 8.5 m/s. Cruise ≈ 1.4·V_s ≈ 12 m/s. In a turn at 45° of bank the stall speed grows by a factor of 1/√cos45° ≈ 1.19, to ≈ 10.1 m/s. That is why `AIRSPEED_MIN` is set no lower than ~1.2·V_s ≈ 10 m/s: in straight flight that is still a margin, in a steep turn it is already the limit.

{{diagram:chart-wing-stall-bank|For a 0.4 m², 2 kg wing (V_s ≈ 8.5 m/s) the stall speed in a turn catches up with AIRSPEED_MIN = 1.2·V_s at 46° of bank, and with a cruise of 1.4·V_s at 59°.}}

### What you should get and what to record
- **Calculation table:** S, MAC, wing loading, V_s, cruise, V_s in a 45° turn. You can reproduce every number with a formula.
- **Center of gravity:** the CG point is marked on the wing with a margin of 10% of MAC. The plane, held on your fingers at that point, hangs slightly nose-down.
- **Checking against a flight:** the measured stall onset speed usually differs from the calculated one by 10–20% because of C_Lmax and the airspeed measurement error. Record both and the difference, and refine `AIRSPEED_MIN` from the measurement.
- **Parameters:** for `AIRSPEED_MIN/CRUISE/MAX`, `TRIM_THROTTLE`, and the starting `TECS_*`, one line of justification from the calculation or a measurement. The "Tuning ArduPlane" module refines them further.

Self-check: the lab is done when your formulas give the same ≈ 8.5, 12, and 10.1 m/s on the data of the worked calculation (0.4 m², 2 kg, C_Lmax 1.1) and only then have you calculated your own table, the CG point with a 10% MAC margin is marked on the wing and the plane held on your fingers at that point hangs slightly nose-down, the stall onset speed measured in flight is recorded next to the calculated one and differs from it by no more than 10–20%, `AIRSPEED_MIN` is no lower than ~1.2·V_s, and every airspeed and TECS parameter has a line of justification from the calculation or a measurement. For the step 3 script (the path without hardware): on the example's inputs your output matches the reference to the last digit: V_s 8.53 m/s, stall TAS 9.18 m/s at 1500 m, a roll limit of 34.3° at 11 m/s with `AIRSPEED_STALL` = 0 and 43.7° at 10 m/s with 8.5, a TECS minimum of 11.89 m/s in a 45° turn, and the 12 → 10 m/s exchange = 2.24 m.

**Reference for the self-check.** A correct result: every number in the table can be reproduced with a formula, the calculation and the flight differ by 10–20%, and `AIRSPEED_MIN` is refined from the measured speed. Typical wrong results: (1) a difference noticeably above 20% means an error in the assumed C_Lmax or in the airspeed measurement, in which case trust the measurement and not the calculation; (2) `AIRSPEED_MIN` equals the straight-flight V_s: in a 45° turn the stall comes at ≈ 1.19·V_s already, so there is no margin; (3) in block 3 of the script you get 45° at any airspeed: your function does not use `AIRSPEED_MIN` when `AIRSPEED_STALL` = 0 (which is what the firmware does, `Attitude.cpp:719–721`), or the load factor is calculated as cos φ instead of 1/cos φ.

## diagnostics
- **Symptom:** the plane drops its nose and sinks in a turn
  - Possible cause: a stall; the airspeed in the turn is below V_s/√cos φ.
  - What to do: a higher `AIRSPEED_MIN`, limit the roll (`ROLL_LIMIT_DEG`), a higher cruise speed.
- **Symptom:** twitchy in pitch, does not hold trim
  - Possible cause: an aft CG, a small margin.
  - What to do: move the CG forward by 2–5% MAC, do a dive test.
- **Symptom:** it loses altitude while gaining airspeed in AUTO
  - Possible cause: `TECS_SPDWEIGHT` close to 2 with weak throttle, or `TECS_CLMB_MAX` set too high.
  - What to do: a real `TECS_CLMB_MAX` from a full-throttle test, SPDWEIGHT 1.
- **Symptom:** the airspeed reads nonsense on the ground
  - Possible cause: the tube is not calibrated, is covered, or has condensation.
  - What to do: `ARSPD_AUTOCAL`, warm it up, blow it out; the airspeed pre-arm check.
- **Symptom:** in FBWA or AUTO the wing will not bank more than 25–35° at a normal airspeed
  - Possible cause: `AIRSPEED_STALL` = 0, so STALL_PREVENTION treats `AIRSPEED_MIN` as the stall speed: below ≈ 1.19·`AIRSPEED_MIN` the roll is limited to less than 45° (`Attitude.cpp:719–746`).
  - In the log: `CTUN.NavRoll` sits at a single value below `ROLL_LIMIT_DEG`, and the airspeed is close to `AIRSPEED_MIN`.
  - What to do: set `AIRSPEED_STALL` = the measured stall speed (slightly above), check the sensor calibration; there is no need to disable `STALL_PREVENTION`.
- **Symptom:** without an airspeed sensor the wing alternately slows to a stall and speeds up in turns when it is windy
  - Possible cause: without airspeed TECS holds altitude only, and throttle follows pitch from `TRIM_THROTTLE` (`AP_TECS.cpp:930–958`); `TRIM_THROTTLE` is below the real cruise throttle.
  - What to do: set `TRIM_THROTTLE` from a log of level flight, with a higher cruise speed as a margin for wind; for AUTO and VTOL, fit a sensor (`ARSPD_USE` = 1).
- **Symptom:** the sensor is connected and `ARSP` is in the log, but TECS behaves as if it were not there
  - Possible cause: `ARSPD_USE` = 0, so the airspeed is only logged.
  - What to do: `ARSPD_USE` = 1 after checking the readings on the ground and calibrating.
- **Symptom:** the autopilot does not apply throttle on a hand launch
  - Possible cause: `TKOFF_THR_MINACC` is not reached, or the delay.
  - What to do: a harder throw, a lower threshold, check arming and the mode.

## references
- ArduPlane — TECS (Total Energy Control System) tuning | https://ardupilot.org/plane/docs/tecs-total-energy-control-system-for-speed-height-tuning-guide.html | primary | A
- ArduPlane — Airspeed sensor setup and calibration | https://ardupilot.org/plane/docs/airspeed.html | primary | A
- ArduPilot source, tag Copter-4.7.2 (contains ArduPlane V4.7.2): ArduPlane/Attitude.cpp (load factor roll limits) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/ArduPlane/Attitude.cpp | primary | A
- ArduPilot source, tag Copter-4.7.2: libraries/AP_TECS/AP_TECS.cpp (parameters, weighting, min airspeed) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_TECS/AP_TECS.cpp | primary | A
- INAV 9.1.0 source: src/main/fc/settings.yaml (nav_fw_* descriptions and defaults) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/settings.yaml | primary | A
- NASA Glenn — Lift equation (Beginner's Guide to Aeronautics) | https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/lift-equation/ | primary | A
- NASA — Earth Atmosphere Model (standard atmosphere) | https://www.grc.nasa.gov/www/k-12/airplane/atmosmet.html | primary | B

## checklist
- I have calculated S, MAC, wing loading, and V_s for my wing
- I know how V_s grows in a turn and why AIRSPEED_MIN ≥ 1.2 V_s
- The CG is set with a 5–15% margin and checked with a dive test
- I understand TECS: throttle is energy, pitch is its distribution
- I know that `AIRSPEED_*` is EAS, I set `AIRSPEED_STALL` from a measurement, and `ARSPD_USE` = 1 with a working sensor
- The airspeed and TECS parameters are justified by calculation and checked against a flight
