---
id: des-sizing
title: "Designing for the mission: requirements → mass, energy, thrust, configuration"
level: L3
readingTime: 45 min
firmware: any firmware · ArduPilot 4.7 (checked against 4.7.3) for the log comparison
status: published
added: 2026-11-10
tags:
  - design
  - mass budget
  - energy
  - thrust
  - configuration
related:
  - f-aero-props
  - el-battery-packs
  - ap-heavy
  - aero-wing
  - ap-quadplane
next:
  - des-thrust-stand
source: content/design/des-sizing.md
source_hash: f110fab647a3
---

## summary
So far you have picked a motor and a battery for a frame that already existed. Here is the inverse problem: you have requirements (payload, time, wind) and need to arrive at the takeoff mass, the battery capacity, the motor and prop, and the vehicle configuration. The trouble is that everything depends on everything: a bigger battery means more mass, more mass means more power, and more power needs an even bigger battery. This module gives you a closed model: a mass budget through mass fractions, energy through Wh/kg with depth of discharge and reserve, hover power from momentum theory with a figure of merit (FM) taken from the motor datasheet, a check of T/W and wind margin, and the choice of configuration. Lab: a Python script that iterates the "mass ↔ battery ↔ power" loop to convergence on real T-Motor MN4014 and Molicel P45B datasheets, and on hardware, weighing the vehicle and comparing the hover current with the prediction.

## theory
### Requirements in numbers
A requirement like "it should fly a long time and carry a camera" cannot be designed for. Every requirement is a number with a criterion:

| Requirement | Value in the example | How it is checked |
|---|---|---|
| Payload | 1.0 kg (camera + gimbal) | mass, part of the budget |
| Time | 25 min of hover down to a 20 % reserve | battery energy |
| Wind | operating in 10 m/s, returning at 15 m/s (1.5 × wind) | tilt and thrust margin |
| Thrust margin | T/W ≥ 2 on a sagged battery | motor table |
| Onboard power | 10 W (FC, GPS, receiver, gimbal) | added to the power |

### Mass budget and mass fractions
Takeoff mass m = payload + avionics + propulsion + battery + frame. The frame is best given as a **fraction** f_frame of the takeoff mass (a guideline for 600–800 mm carbon frames is 15–20 %, refined by weighing), because the frame grows with the vehicle. Then the mass closes like this:

**m = (m_payload + m_avionics + m_motors + m_battery) / (1 − f_frame)**

Why flight time hits a ceiling: hover power P ∝ m^1.5 (see below), energy E ∝ m_battery = f_battery·m. So **t ∝ f_battery / √m** with the same props: every additional kilogram of battery drags up the power with it. The way out of the dead end is not "one more cell" but a larger disc: at a constant disc loading P ∝ m, and the time stops falling as the vehicle grows.

### Energy: Wh/kg, depth of discharge, reserve
The Molicel INR-21700-P45B datasheet: typically 4500 mAh, 3.6 V, **16.2 Wh**, mass **70 g (max)** → 231 Wh/kg per cell (the datasheet says 242 Wh/kg, apparently based on the typical mass of ≈ 67 g, while the datasheet gives only the maximum mass). From here the number only goes down:

- the pack build (nickel strip, wires, balance lead, heat shrink) adds about +10 % mass → **≈ 210 Wh/kg** per pack;
- **depth of discharge (DoD)**: under load and in the cold, not all the energy comes out before cutoff; we budget 85 %;
- **reserve** for landing and the unexpected: 20 % of what is available stays in the battery.

The result: 210 × 0.85 × 0.8 ≈ **143 Wh per kilogram of pack** actually goes into the flight. Time: **t = S·P·E_cell·0.85·0.8 / P_hover**.

### Hover power: momentum theory and FM
From actuator disc theory (Leishman, ch. 2), the ideal hover power at thrust T and total disc area A is:

**P_ideal = T^1.5 / √(2·ρ·A)**

A real prop spends more (profile drag, tip losses, swirl). The ratio **FM = P_ideal / P_actual** is the figure of merit. Full-size helicopter rotors have FM ≈ 0.7–0.8, small props lower. For the calculation a "system" FM is more convenient, referred to the electrical power from the motor table; then it already includes the motor and ESC efficiency.

An example from the T-Motor MN4014 KV330 table (22.2 V): a 15×5 prop at 75 % throttle gives 1430 g at 173.2 W. T = 14.03 N, A = π·0.1905² = 0.1140 m², P_ideal = 99.4 W, FM_sys = 99.4 / 173.2 = **0.574**. Over all rows of the table it is 0.55–0.59 for the 15×5 and 0.53–0.60 for the 17×5.8. This number calibrates the whole model.

### Disc loading
**Disc loading DL = T / A** (N/m²). From the formula above the specific power is P/T = √(DL / 2ρ) / FM: lower loading means more grams per watt. The same 4.29 kg vehicle on four 15″ props has 92 N/m² and 9.3 g/W, on four 17″ props 72 N/m² and 10.7 g/W. The 13 % difference in power is 3.7 minutes of flight in the example below.

### Prop, motor, KV
1. **Diameter**: the largest that fits the frame with clearance between the props (a large disc = low DL).
2. **KV**: so that at full throttle the motor spins the prop up to the required thrust: loaded RPM ≈ 0.75–0.85 × KV × U. For the MN4014: 330 × 22.2 = 7326 RPM unloaded, and per the table 6000 RPM with the 15×5 (0.82) and 5400 with the 17×5.8 (0.74). The tip speed of a 17″ blade at 5400 RPM is π·0.432·90 ≈ 122 m/s (M ≈ 0.36), far from the noisy transonic regimes.
3. **Hover current**: no more than ~40 % of the motor's continuous current: the MN4014 is rated 25 A continuous (180 s), and hovering 1073 g with the 17×5.8 takes about 4.8 A.
4. **T/W on a sagged battery**: the table was taken at 22.2 V, while Li-ion under load in the second half of the discharge gives about 3.4 V/cell (20.4 V). Thrust ∝ U², so the maximum drops by a factor of (20.4/22.2)² = 0.84.

### Wind and thrust margin
In a wind V the vehicle tilts by an angle θ = atan(D / mg), where D = ½·ρ·V²·CdA. To return against the wind you need an airspeed with a margin; we take 1.5 × wind (course guideline: then the ground speed against the wind is half the wind speed, and the return does not drag on). The thrust in steady flight, √((mg)² + D²), must leave a margin for control: no more than 80 % of the maximum (course guideline: the same 20 % margin as in `f-mechanics`, which a 10 % voltage sag eats up). The same 1.5 × wind is behind the gust rule in `ops-weather` (gusts ≤ 50–60 % of the maximum speed). T/W ≥ 2 is budgeted separately: that is the margin for maneuvering and stabilization. CdA is the weakest point of the model (in the example 0.06 m² is assumed, not measured); on hardware you refine it from the tilt angle in a known wind. The tilt limit in ArduPilot: `ATC_ANGLE_MAX` in degrees (default 30; before Copter 4.7, `ANGLE_MAX` in centidegrees, 3000).

We compute the energy from hover: at 8–12 m/s the induced power drops, so this is conservative. Manufacturer tables are taken on a new motor indoors and are usually optimistic by 5–10 %.

### Vehicle configuration
| Configuration | Pro | Con | When |
|---|---|---|---|
| Quad | fewest motors, simpler and lighter | motor failure = crash | inexpensive payload, up to ~25–30 min |
| Hexa / octo | survives a motor failure, larger total disc in the same frame | mass, cost, current | expensive payload; you still do not fly over people |
| Coaxial X8 | 8 motors in a quad's footprint | the lower prop is in the upper prop's wake | tight space, redundancy needed |
| Airplane | P = W·V / (L/D) / η, 3 times less than hover | needs a runway or a catapult | time > 1 h, a route |
| VTOL (QuadPlane) | takeoff without a runway + wing cruise | +20–30 % mass for the lift motors | time > 40 min, hover for minutes |

For a coaxial pair momentum theory gives an induced power factor κ_int ≈ 1.28 at equal thrusts (the lower prop in the far wake of the upper one); at the same power the pair's thrust is ≈ (1/1.28)^(2/3) = 0.85 of two single props, the same ~15 % as in `ap-heavy`.

{{diagram:sizing-config-tree|The configuration is chosen by the share of hover in the mission: if you do not need to hover, a wing is several times more economical; if hover is the main job, a multirotor, and the number of motors is set by the cost of a failure.}}

### Place in the system

- **Receives:** the requirements in numbers: payload, time, wind (`eng-systems`); the motor-and-prop thrust table (`f-aero-props`), refined on a thrust stand (`des-thrust-stand`); Wh/kg and cell sag (`el-battery-packs`).
- **Provides:** the takeoff mass, the S/P configuration, the motor and the prop to component selection (`f-components-choice`); hover power and current to the power bus calculation (`el-power-design`); the vehicle configuration (`ap-heavy`).
- **If you get it wrong here:** T/W taken from the table at 22.2 V instead of a sagged battery → at the end of the discharge thrust is ×0.84, there is no wind margin, the motors are at their limit; visible in `RCOU` (`ap-logs`). The manufacturer's table is optimistic by 5–10 % → the time is shorter than calculated, and the battery failsafe fires earlier than planned (`ap-safety-fs`).

## practice
### Step 1. Fix the requirements and the assumptions
The requirements come from the table in the theory. The assumptions are written down explicitly, because they are exactly what the hardware will check later: motor 171 g with leads (MN4014 datasheet), prop 20 g and ESC 30 g per motor (an estimate, weigh your own), avionics 250 g, frame 18 % of the takeoff mass, a 6S·nP battery of P45B with a 10 % allowance for the pack build, DoD 85 %, reserve 20 %, CdA = 0.06 m², voltage under load 20.4 V.

### Step 2. The script
Save it as `sizing.py` and run `python3 sizing.py` (Python 3.8+, no libraries):

```python
"""Multirotor sizing: mission -> mass, energy, thrust (des-sizing lab)."""
import math

RHO, G = 1.225, 9.81
# T-Motor MN4014 KV330 @ 22.2 V (store.tmotor.com, report MN.00026): thrust g, power W
MN4014 = {"15x5": [(830, 79.92), (1150, 130.98), (1430, 173.16), (1690, 224.22), (1920, 264.18)],
          "17x5.8": [(1050, 104.34), (1580, 177.60), (1970, 237.54), (2300, 319.68), (2600, 377.40)]}
CELL_WH, CELL_G = 16.2, 70.0          # Molicel INR-21700-P45B: 4500 mAh x 3.6 V, 70 g max

def disc_area(d_in):
    return math.pi * (d_in * 0.0254 / 2) ** 2

def p_ideal(t_n, area):               # momentum theory, hover: P = T^1.5 / sqrt(2 rho A)
    return t_n ** 1.5 / math.sqrt(2 * RHO * area)

def fm_system(prop, d_in):            # electrical FM = ideal power / power from the datasheet
    return [p_ideal(t / 1000 * G, disc_area(d_in)) / p for t, p in MN4014[prop]]

def size(prop, d_in, n_rot=4, payload=1.0, t_min=25, p_av=10.0, frame_frac=0.18,
         m_motor=0.171, m_prop=0.020, m_esc=0.030, m_avionics=0.25,
         usable=0.85, reserve=0.20, s=6, n_p=None, verbose=True):
    fm = sum(fm_system(prop, d_in)[:3]) / 3          # 50-75 % throttle rows: the hover range
    area = n_rot * disc_area(d_in)
    m, it = 3.0, 0
    while True:
        it += 1
        p_h = p_ideal(m * G, area) / fm + p_av
        e_pack = p_h * t_min / 60 / (usable * (1 - reserve))
        np_ = n_p or math.ceil(e_pack / (s * CELL_WH))
        m_bat = s * np_ * CELL_G / 1000 * 1.10       # +10 % nickel, wires, wrap
        m_new = (payload + m_avionics + n_rot * (m_motor + m_prop + m_esc) + m_bat) / (1 - frame_frac)
        if verbose:
            print(f"it{it}: m={m:.3f} kg  P={p_h:5.0f} W  E_need={e_pack:4.0f} Wh  {s}S{np_}P  m_bat={m_bat:.3f}  -> {m_new:.3f}")
        if abs(m_new - m) < 0.001 or it > 30:
            break
        m = m_new
    m = m_new
    p_h = p_ideal(m * G, area) / fm + p_av
    endur = s * np_ * CELL_WH * usable * (1 - reserve) / p_h * 60
    return dict(m=m, fm=fm, p=p_h, np=np_, m_bat=m_bat, endur=endur, area=area, n_rot=n_rot)

def check(prop, r, wind=10.0, cda=0.06, v_sag=20.4):
    w = r["m"] * G
    t_mot = r["m"] * 1000 / r["n_rot"]                     # g per motor
    tab = MN4014[prop]
    p_tab = next(p0 + (p1 - p0) * (t_mot - t0) / (t1 - t0)
                 for (t0, p0), (t1, p1) in zip(tab, tab[1:]) if t0 <= t_mot <= t1) if t_mot >= tab[0][0] \
        else tab[0][1] * (t_mot / tab[0][0]) ** 1.5       # below the table: P ~ T^1.5
    t_max = tab[-1][0] * (v_sag / 22.2) ** 2 * r["n_rot"] / 1000 * G   # thrust ~ V^2 at sagged pack
    v_ret = 1.5 * wind
    drag = 0.5 * RHO * v_ret ** 2 * cda
    need = math.hypot(w, drag)
    print(f"disc loading {w / r['area']:.0f} N/m2, per motor {t_mot:.0f} g, "
          f"P_table {p_tab * r['n_rot']:.0f} W vs model {r['p'] - 10:.0f} W (+10 W avionics)")
    tw, use = t_max / w, need / t_max
    print(f"hover current {p_tab * r['n_rot'] / 22.2:.1f} A @22.2 V; T/W at {v_sag} V: {tw:.2f}; "
          f"return at {v_ret:.0f} m/s: drag {drag:.1f} N, tilt {math.degrees(math.atan2(drag, w)):.1f} deg, "
          f"thrust use {use * 100:.0f} %")
    print("VERDICT:", "PASS" if tw >= 2.0 and use <= 0.8 and r["endur"] >= 25 else "FAIL",
          "(need T/W >= 2.0, thrust use <= 80 %, endurance >= 25 min)")

if __name__ == "__main__":
    for prop, d, n in (("15x5", 15, 4), ("17x5.8", 17, 4), ("15x5", 15, 6)):
        print(f"--- {n} x MN4014 KV330 + {prop}: FM_sys per row",
              " ".join(f"{f:.3f}" for f in fm_system(prop, d)))
        r = size(prop, d, n_rot=n, verbose=(n == 4 and d == 15))
        print(f"=> m={r['m']:.2f} kg, FM={r['fm']:.3f}, hover {r['p']:.0f} W, "
              f"6S{r['np']}P ({r['m_bat']:.2f} kg), endurance {r['endur']:.1f} min")
        check(prop, r)
    print("--- endurance vs parallel count (same masses for both props)")
    for n in range(1, 9):
        a, b = (size(p, d, n_p=n, verbose=False) for p, d in (("15x5", 15), ("17x5.8", 17)))
        print(f"6S{n}P m={a['m']:.2f} kg | 15x5 {a['p']:.0f} W {a['endur']:.1f} min"
              f" | 17x5.8 {b['p']:.0f} W {b['endur']:.1f} min")
    print("--- same mass as a wing / VTOL: P = W*V/(L/D)/eta + avionics")
    e_use = 6 * 3 * CELL_WH * 0.85 * 0.8
    for name, m, ld, v, hover_min in (("wing", 4.29, 10, 18, 0), ("VTOL +25% mass", 5.36, 9, 18, 2)):
        p_cruise = m * G * v / ld / 0.55 + 10
        p_hov = p_ideal(m * G, 4 * disc_area(15)) / 0.557 + 10
        t = (e_use - p_hov * hover_min / 60) / p_cruise * 60 + hover_min
        print(f"{name}: m={m} kg, cruise {p_cruise:.0f} W, hover {p_hov:.0f} W x {hover_min} min -> {t:.0f} min")
```

### Step 3. Output (a real run)
```
--- 4 x MN4014 KV330 + 15x5: FM_sys per row 0.550 0.547 0.574 0.570 0.585
it1: m=3.000 kg  P=  281 W  E_need= 172 Wh  6S2P  m_bat=0.924  -> 3.729
it2: m=3.729 kg  P=  386 W  E_need= 236 Wh  6S3P  m_bat=1.386  -> 4.293
it3: m=4.293 kg  P=  474 W  E_need= 290 Wh  6S3P  m_bat=1.386  -> 4.293
=> m=4.29 kg, FM=0.557, hover 474 W, 6S3P (1.39 kg), endurance 25.1 min
disc loading 92 N/m2, per motor 1073 g, P_table 475 W vs model 464 W (+10 W avionics)
hover current 21.4 A @22.2 V; T/W at 20.4 V: 1.51; return at 15 m/s: drag 8.3 N, tilt 11.1 deg, thrust use 67 %
VERDICT: FAIL (need T/W >= 2.0, thrust use <= 80 %, endurance >= 25 min)
--- 4 x MN4014 KV330 + 17x5.8: FM_sys per row 0.529 0.574 0.597 0.560 0.570
=> m=4.29 kg, FM=0.567, hover 413 W, 6S3P (1.39 kg), endurance 28.8 min
disc loading 72 N/m2, per motor 1073 g, P_table 430 W vs model 403 W (+10 W avionics)
hover current 19.4 A @22.2 V; T/W at 20.4 V: 2.05; return at 15 m/s: drag 8.3 N, tilt 11.1 deg, thrust use 50 %
VERDICT: PASS (need T/W >= 2.0, thrust use <= 80 %, endurance >= 25 min)
--- 6 x MN4014 KV330 + 15x5: FM_sys per row 0.550 0.547 0.574 0.570 0.585
=> m=4.83 kg, FM=0.557, hover 462 W, 6S3P (1.39 kg), endurance 25.7 min
disc loading 69 N/m2, per motor 805 g, P_table 458 W vs model 452 W (+10 W avionics)
hover current 20.6 A @22.2 V; T/W at 20.4 V: 2.01; return at 15 m/s: drag 8.3 N, tilt 9.9 deg, thrust use 50 %
VERDICT: PASS (need T/W >= 2.0, thrust use <= 80 %, endurance >= 25 min)
--- endurance vs parallel count (same masses for both props)
6S1P m=3.17 kg | 15x5 304 W 13.1 min | 17x5.8 265 W 15.0 min
6S2P m=3.73 kg | 15x5 386 W 20.6 min | 17x5.8 336 W 23.6 min
6S3P m=4.29 kg | 15x5 474 W 25.1 min | 17x5.8 413 W 28.8 min
6S4P m=4.86 kg | 15x5 568 W 27.9 min | 17x5.8 494 W 32.1 min
6S5P m=5.42 kg | 15x5 668 W 29.7 min | 17x5.8 581 W 34.1 min
6S6P m=5.98 kg | 15x5 773 W 30.8 min | 17x5.8 672 W 35.4 min
6S7P m=6.55 kg | 15x5 884 W 31.4 min | 17x5.8 768 W 36.1 min
6S8P m=7.11 kg | 15x5 999 W 31.8 min | 17x5.8 868 W 36.5 min
--- same mass as a wing / VTOL: P = W*V/(L/D)/eta + avionics
wing: m=4.29 kg, cruise 148 W, hover 474 W x 0 min -> 81 min
VTOL +25% mass: m=5.36 kg, cruise 201 W, hover 658 W x 2 min -> 55 min
```

### Step 4. Reading the result
- **Convergence.** The loop converged in three iterations, but in steps: the number of parallel cells is an integer, and the mass jumps 3.0 → 3.73 → 4.29 kg. If the loop oscillates between nP and nP+1, fix nP by hand and choose from the time table.
- **The 15″ quad fails.** The 25.1 min is formally there, but T/W on a sagged battery is 1.51: the vehicle has no margin for maneuvering, and by the end of the discharge it will hover at 66 % of its maximum thrust (`MOT_THST_HOVER` ≈ 0.66). Note that judging by "flight time" alone you would have accepted it.
- **The 17″ quad passes** with the same mass: DL 72 instead of 92 N/m², 61 W less, 28.8 min, T/W 2.05, an 11° tilt returning into a 15 m/s wind, 50 % of the thrust in use. This is the chosen option; for a 17″ frame (diagonal ~700–800 mm), check that its mass fits within the same 18 %.
- **The 15″ hexa** also passes (25.7 min, T/W 2.01) and survives a motor failure, but it is 0.54 kg heavier and borderline on T/W. The choice between it and the 17″ quad is a question of the cost of a failure, not of physics.
- **Model versus table.** The FM model differs from the table interpolation by 2 % (15″) and 6 % (17″): good enough for a sketch, but the final numbers come from the table and the log.
- **The battery ceiling.** From 6S4P to 6S8P the mass grows by 2.3 kg and the time by 4.4 min; that is t ∝ f_battery/√m in numbers.
- **A wing of the same mass** stays up 81 min on the same battery, a VTOL with +25 % mass and two minutes of hover 55 min. If the mission does not require hovering over a point, a multirotor is the wrong configuration.

{{diagram:chart-sizing-endurance|Time grows ever more slowly with the number of parallel cells: 6S3P meets the 25 min requirement, while 6S8P adds 2.3 kg for 4.4 min. The 17″ prop at the same mass gives +3.7 min thanks to the lower disc loading.}}

### Step 5. Sensitivity
Change one parameter at a time and record the value at which the verdict for the 17″ quad changes to FAIL: payload (1.0 → 1.5 kg), time (25 → 30 min), `frame_frac` (0.18 → 0.22), `usable` (0.85 → 0.75, a winter battery), `cda` (0.06 → 0.12). Note which parameter moves the mass the most: that is the one you have to measure most accurately.

### Moving to real hardware
The goal is to check the model on an assembled vehicle with a known motor table.

1. **Weighing.** Without props, on a scale with 1–2 g resolution: every group from the budget (frame, motors, ESCs, avionics, battery, payload). Record the actual frame fraction and the Wh/kg of your pack, plug them into the script and recompute the prediction.
2. **Current calibration on the bench.** Props removed. Check `BATT_VOLT_MULT` against a multimeter and `BATT_AMP_PERVLT` against a clamp meter (the load is Motor Test without props, or a resistor): a current error > 5 % makes the comparison meaningless.
3. **Hover.** Fit the props only now, in an open area, with people no closer than 30 m, and the RC and battery failsafes checked. Wind < 3 m/s, a full battery, 60–90 s of hover at 3–5 m in AltHold or Loiter with logging enabled.
4. **The log.** Averages over the hover segment: `BAT.Volt`, `BAT.Curr` (power P = U·I), `CTUN.ThO`; after landing, the learned `MOT_THST_HOVER` (`MOT_HOVER_LEARN` = 2 by default). Per its description in the source it is the "Motor thrust needed to hover expressed as a number from 0 to 1", so the actual T/W ≈ 1 / `MOT_THST_HOVER` (taking into account the voltage compensation `MOT_BAT_VOLT_MAX`/`MOT_BAT_VOLT_MIN`). For the example the prediction is ≈ 0.4–0.5.
5. **Comparison.** Compute the system FM of your vehicle: FM = P_ideal(m) / (P_log − 10 W). If it differs from the datasheet value by more than 15 %, look for the cause in the troubleshooting below.

Hardware path criteria: the mass is weighed by group and differs from the budget by no more than 10 % (or the budget has been recomputed); the hover power from the log is within ±15 % of the script's prediction with the actual mass; `MOT_THST_HOVER` is no higher than 0.5 (T/W ≥ 2).

Self-check: the lab is done when (calculation path) the script has been reproduced and its output matches step 3 (convergence in three iterations, mass 3.0 → 3.73 → 4.29 kg; the 17″ quad at 28.8 min and T/W 2.05), the option has been chosen by all three verdict criteria with numbers, the difference between the model and the motor table has been computed and does not exceed 10 %, and the sensitivity table is filled in; (hardware) the mass is weighed by group, the current is calibrated with a clamp meter, and the hover power from the log and `MOT_THST_HOVER` agree with the prediction within ±15 %.

## diagnostics
- **Symptom:** the loop in the script does not converge or jumps between 6S3P and 6S4P
  - Possible cause: the integer number of parallel cells; with a large frame fraction or a heavy payload the mass grows faster than the energy (no solution).
  - What to do: fix `n_p` and go through the time table; if the time does not grow with nP, change the prop diameter or the configuration, not the battery.
- **Symptom:** the hover current in the log is 20–30 % above the prediction
  - Possible cause: the real mass is above the budget; the motor table was taken with a different prop or voltage; the current sensor is not calibrated.
  - What the log shows: `BAT.Curr` higher, `CTUN.ThO` higher than expected.
  - What to do: weigh the vehicle, check `BATT_AMP_PERVLT` with a clamp meter, recompute the FM from the actual data.
- **Symptom:** the hover current matches, but the flight time is 25 % shorter
  - Possible cause: a cold battery, capacity below nominal, a cutoff higher than budgeted (less than 85 % comes out).
  - What to do: check the capacity with a cycle on the charger, reduce `usable` in the model, warm the battery in winter.
- **Symptom:** `MOT_THST_HOVER` above 0.5
  - Possible cause: T/W below 2: the model underestimated the mass or overestimated the thrust on a sagged battery.
  - Consequences: no margin for wind and stabilization by the end of the discharge.
  - What to do: a larger-diameter prop, a motor with more margin, or a lighter build; repeat the calculation.
- **Symptom:** in wind the vehicle does not hold position and leans to the limit angle
  - Possible cause: CdA underestimated, the `ATC_ANGLE_MAX` tilt limit reached.
  - What to do: estimate CdA from the tilt angle in a known wind (tan θ = D/mg), recompute the margin, limit operations by wind.
- **Symptom:** the motors are hot after hover
  - Possible cause: the hover current is above ~40 % of the motor's continuous current.
  - What to do: check the operating point in the table, take a larger motor or a lower-pitch prop.

## checklist
- The requirements are rewritten as numbers with acceptance criteria
- The mass budget is built with a frame fraction and checked by weighing
- The energy is computed with DoD and reserve, not from the nominal value
- FM is taken from the motor table, and the disc loading is computed
- T/W is checked on a sagged battery, and the wind margin is computed
- The configuration is chosen by the share of hover and the cost of a failure
- The prediction is checked against a hover log

## references
- T-Motor MN4014 KV330 — specification and test data (report MN.00026) | https://store.tmotor.com/product/mn4014-kv330-motor-navigator-type.html | primary | A
- Molicel INR-21700-P45B Product Data Sheet v1.2 | https://www.imrbatteries.com/content/molicel_p45b.pdf | primary | A
- Leishman J. G. Principles of Helicopter Aerodynamics, 2nd ed., Cambridge University Press (momentum theory, FM) | https://openlibrary.org/books/OL3409514M/Principles_of_helicopter_aerodynamics | primary | A
- Propeller Thrust — NASA Glenn Research Center (actuator disc) | https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/propeller-thrust/ | primary | A
- ArduPilot: AP_MotorsMulticopter.cpp (`MOT_THST_HOVER`, `MOT_HOVER_LEARN`, `MOT_BAT_VOLT_MAX`) | https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_Motors/AP_MotorsMulticopter.cpp | primary | A
- ArduPilot: ArduCopter/Log.cpp (CTUN fields: ThO, ThH) | https://github.com/ArduPilot/ardupilot/blob/master/ArduCopter/Log.cpp | primary | A
- ArduPilot Copter 4.7.2: AC_AttitudeControl.cpp (`ATC_ANGLE_MAX`, degrees; in 4.6, `ANGLE_MAX` in Parameters.cpp, cdeg) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AC_AttitudeControl/AC_AttitudeControl.cpp | primary | A
- Lift to Drag Ratio — NASA Glenn Research Center | https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/lift-to-drag-ratio/ | primary | B
- Simões C. M. Optimizing a Coaxial Propulsion System to a Quadcopter, extended abstract, IST Lisboa (κ_int = 1.281 from momentum theory) | https://fenix.tecnico.ulisboa.pt/downloadFile/566729524644716/CedricSimoes_ExtendedAbstract.pdf | secondary | B

