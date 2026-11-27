---
id: bf-motor-balance
title: "Mechanics before PID: motor balance from the log"
level: L2
readingTime: 45 min
firmware: Betaflight 4.5 (checked against the 4.5.3 and 4.5.5 source); the Quad X mixer and the log fields are the same in 2025.12
status: published
added: 2026-11-25
tags:
  - Betaflight
  - Blackbox
  - motors
  - mechanics
  - diagnostics
related:
  - bf-blackbox
  - bf-pid
  - bf-filters
  - f-motors-esc
  - f-frame-mech
  - bf-setup-scratch
  - ctl-allocation
  - des-thrust-stand
  - bf-tuning-method
next:
  - bf-pid
source: content/betaflight/bf-motor-balance.md
source_hash: d39ec3bf241d
---

## summary
Before tuning PID it is worth checking the mechanics. In level flight, unequal motor outputs show that the controller is constantly compensating for a physical imbalance: an offset center of gravity (CG), a weak motor, a damaged prop, a tilted motor or a bent arm. This module gives a method. You pick a steady 10–20 s segment of the log, take the median of each `motor[0..3]` and convert it to percent of travel using the `motorOutput` header. Three imbalance indices are computed from the medians: rear–front, left–right and diagonal (yaw). Their combination points to the cause, and a swap test confirms it. The lab is a Python script. It finds the steady segment in the CSV from `blackbox_decode` by itself. You check the script on synthetic logs with defects injected in advance: the CG 4 % to the rear and motor 4 at +6 %. Then you do the same on your own aircraft, with a bench procedure and a field procedure.

## theory
### Why mechanics come before PID
In a steady hover the angular rates on all axes are near zero, and the P and D terms do almost nothing. A constant disturbance torque is held by the I term: it accumulates a correction until the error is zero and then keeps it. That is why a mechanical imbalance always looks the same in the log: a non-zero median of `axisI[0..2]` and a constant difference between `motor[0..3]` with the sticks centered. Raising yaw I is useless here: I will reach the same correction faster, but the correction itself will remain.

You pay for it with control headroom:

- The mixer adds the correction to the throttle: `motor = motorOutputMin + motorOutputRange · (throttle + Σ pidSum/1000 · mixer coefficient)` (`flight/mixer.c`, `applyMixToMotors`, `PID_MIXER_SCALING` = 1000). A motor that already needs 8 % more in hover will be the first to hit 100 % in a punch-out. If the spread of the corrections `motorMixRange` is greater than 1, the `LEGACY` mixer compresses the corrections on all axes together (`applyMixerAdjustment`), and all axes lose part of their authority at once.
- `iterm_windup` = 85: when `motorMixRange` exceeds 0.85, the I term starts to accumulate more slowly, and at 1.0 it stops altogether (`flight/pid.c`, `dynCi`). Part of this window is already spent on the mechanical imbalance.
- Yaw has the least headroom. Yaw torque is produced only by the reaction torque of the props: the reaction-torque arm K_M = Q/T is 1–2 cm against a 15–25 cm arm in roll and pitch (the estimate is below). In addition, `pidsum_limit_yaw` = 400 against 500 for roll and pitch. A constant diagonal imbalance eats exactly this headroom, which is why the heading “drifts” in a sharp turn at full throttle.

A motor that constantly needs a higher command than the others runs hotter — a frequent answer to the question “why is one motor hotter”. A weak motor or prop also produces vibration that the filters will not remove (`bf-filters`). Hence the order: mechanics and balance, then filters, then PID.

### Quad X: numbers, log fields, rotation
In Betaflight 4.5 the Quad X motors are numbered as follows: **1 — rear right (RR), 2 — front right (FR), 3 — rear left (RL), 4 — front left (FL)**. In the log the indices start from zero: `motor[0]` = motor 1, …, `motor[3]` = motor 4. The `mixerQuadX[]` table (`flight/mixer_init.c`, the columns throttle, roll, pitch, yaw) sets the signs as follows:

| Motor | Log field | roll | pitch | yaw | Rotation, props-in |
|---|---|---|---|---|---|
| 1 RR | `motor[0]` | −1 | +1 | −1 | CW |
| 2 FR | `motor[1]` | −1 | −1 | +1 | CCW |
| 3 RL | `motor[2]` | +1 | +1 | +1 | CCW |
| 4 FL | `motor[3]` | +1 | −1 | −1 | CW |

The default rotation is props-in: the front props at the camera spin inward. The Betaflight page “Running with Reversed Motors” describes the opposite: with props-out the front left spins counterclockwise and the front right clockwise. For props-out, set `yaw_motors_reversed = ON`. The parameter changes neither the table nor the numbers; it only inverts the sign of the yaw PID before the mixer (`if (!mixerConfig()->yaw_motors_reversed) scaledAxisPidYaw = -scaledAxisPidYaw;`). The motors themselves are not reversed by it: the direction is changed in the ESC configurator or by swapping two phase wires. The yaw pairs: motors 1 and 4 spin one way, motors 2 and 3 the other.

One more detail: `motor_output_reordering` reorders only the physical outputs (in the motor drivers: `dshot_bitbang.c`, `dshot_dpwm.c`, `pwm_output.c`), while the log records the mixer indices. So `motor[0]` is always the rear right, whichever pad that motor is soldered to. If the order or the direction is wrong, there is no point in computing the balance: go through the Motors tab first (`bf-setup-scratch`).

{{diagram:bf-quadx-motor-map|The motor number and the log field differ by one, and the diagonals 1+4 and 2+3 rotate in opposite directions. Three pair comparisons separate the causes: the CG gives only pitch and roll, a motor tilt — only yaw, one weak motor — all three indices of the same magnitude.}}

### What is in `motor[0..3]` and how to convert it to percent
The log records the motor command after the mixer and the limits (`blackbox.c`: `blackboxCurrent->motor[i] = lrintf(motor[i])`). With DShot this is the protocol value, not a percentage. The range limits are written to the log header as the line `motorOutput:low,high`, taken from `getMotorOutputLow()` and `getMotorOutputHigh()`. For DShot without 3D (`drivers/dshot.c`):

- low = 48 + `dshot_idle_value`/10000 · 1999. With the default of 550 that is 48 + 0.055 · 1999 = 157.9, and the header shows **158**;
- high = 2047 − 1999 · (1 − `motor_output_limit`/100). At 100 % that is **2047**, at 80 % — 1647;
- with dynamic idle enabled (`dyn_idle_min_rpm` > 0, bidirectional DShot is required) the lower limit is reset to 48 (`mixerInitProfile`), and the header will show `48,2047`.

Percent of travel: **p = (motor − low) / (high − low) · 100**. A value of 876 with `158,2047` gives 38.01 %. If `48,2047` is taken by mistake, the result is 41.42 %. For the imbalance indices this hardly matters, because they are relative. For the headroom to 100 % and for comparing logs with different settings it does. The easiest way to get the range line is from the log file itself: `grep -a motorOutput LOG00001.BFL` (the header there is text), or from the header view in Blackbox Explorer.

`blackbox_decode` writes a CSV with a header made of the log field names: `motor[0]`…`motor[3]`, `rcCommand[3]` (throttle, 1000–2000), `gyroADC[0..2]`, `axisI[0..2]`, `eRPM[0..3]` (eRPM/100, only with DShot telemetry). The unit is added in parentheses, for example `time (us)`. The gyro is output in raw units by default (`--unit-rotation raw`). In Betaflight 4.x the raw units are °/s, the header has `gyro_scale` = 1.0, and with `blackbox_high_resolution = ON` the values are multiplied by 10.

### The method: segment, medians, three indices
1. **The segment.** A hover or a level straight pass of 10–20 s without throttle transitions. The script below cuts the log into 0.5 s blocks and takes the longest run of blocks in which the throttle span of `rcCommand[3]` per block is ≤ 20 units (≈ 40 /s), the gyro RMS is ≤ 20 °/s and the throttle is above 1150 (the aircraft is airborne). The run is trimmed to 20 s around its center. These are course guidelines, not firmware values.
2. **The medians.** The median of each `motor[i]` over the segment, converted to percent: p₁…p₄, the mean p̄. The median, not the mean: a gust of wind shifts the mean and hardly touches the median.
3. **The indices** in percent of the mean; these are differences of pair averages:
   - I_pitch = [(p₁ + p₃) − (p₂ + p₄)] / 2 / p̄ · 100 — rear minus front;
   - I_roll = [(p₃ + p₄) − (p₁ + p₂)] / 2 / p̄ · 100 — left minus right;
   - I_yaw = [(p₁ + p₄) − (p₂ + p₃)] / 2 / p̄ · 100 — diagonal 1+4 minus 2+3.

A positive I_yaw means that the pair 1+4 works harder. With props-in its props spin clockwise (viewed from above), and their reaction turns the frame counterclockwise. If the pattern is pure yaw (I_pitch ≈ I_roll ≈ 0), the controller is canceling a disturbance torque that pulls the nose to the right; with props-out it is the other way around. If all three indices have the same magnitude, it is a weak motor of that pair, and there is no disturbance torque: the thrusts are equal, so the reactions are equal too. There is a quick cross-check against the controller: with linearization off (`thrust_linear` = 0), `motorMixRange` < 1 and airmode on (or throttle ≥ 50 %), a constant yaw pidSum S gives every motor ±S/10 % of travel. Without airmode at a throttle g < 0.5 the `LEGACY` mixer multiplies the correction by 0.5 + g (`applyMixerAdjustment`): at a 30 % hover that is ×0.8. So with airmode a median `axisI[2]` = 20 (P, D and F are near zero in hover) corresponds to a diagonal difference of 4 percentage points; at p̄ = 38 % that is I_yaw ≈ 10.5 %.

**A course guideline** (not a firmware value): |I| ≤ 2 % — normal for an assembled aircraft, 2–5 % — see whether it repeats from flight to flight, more than 5 % consistently in several logs — look for a mechanical cause before any tuning.

### Signatures of the causes
The four medians are tied to four quantities: the collective throttle and the three indices. Every cause leaves its own pattern.

- **An offset CG** gives I_pitch and/or I_roll with I_yaw ≈ 0. The thrust moments about the CG balance when T_front · (L/2 + x) = T_rear · (L/2 − x). Hence the rearward CG offset x = I_T · L/4, where L is the distance between the front and rear motor axes and I_T is the index in terms of thrust. Thrust grows as the square of the RPM (`f-aero-props`), but the RPM grows more slowly than the command: per the T-Motor 15×5 table from `des-thrust-stand`, thrust ∝ command^k with k ≈ 1.1–1.8 (2 is the upper bound, if the RPM is taken as proportional to the command). So I_T ≈ k · I_pitch and **x ≈ k · I_pitch · L/4**. With L = 300 mm and I_pitch = 4 % this gives x ≈ 3–5 mm (6 mm at k = 2). It is an order-of-magnitude estimate; the exact k of your motor and prop comes from a thrust stand.
- **One weak motor** (motor k needs w more command for the same thrust) gives three indices of the same magnitude ≈ w/2. The signs point to the corner: for motor 4 (FL) that is front, left and the diagonal 1+4. If the CG is the only cause, then in the linear model p₁ + p₄ = p₂ + p₃. So motor k “should” have p_k = (the sum of its neighbors) − (the opposite motor), and w = p_k / [(the sum of the neighbors) − the opposite one] − 1. Four medians are described exactly by four solutions, one per motor: a “weak” motor on the loaded diagonal (two corners, w > 0) or a “strong” one on the other (two corners, w < 0 — for example, a prop with more pitch). The script prints all four, and treats as weak only those with w > 1 % (a course guideline). A weak motor cannot be told apart from the motor in the opposite corner of the same diagonal: only the swap test distinguishes them.
- **A tilted motor or a bent arm** gives I_yaw with I_pitch ≈ I_roll ≈ 0. A motor tilted tangentially by an angle δ produces a yaw torque T · r · sin δ. It is canceled by the difference in the reactions of the pairs: 2 · K_M · T · I_T, where K_M = Q/T is the ratio of the prop's reaction torque to its thrust. Hence I_T = r · sin δ / (2K_M), and in terms of the command it is k times smaller (k ≈ 1.1–1.8, no more than 2). Per the T-Motor 15×5 table from `des-thrust-stand`, K_M = 0.15 N·m / (0.805 · 9.81 N) ≈ 0.019 m. For a 10" prop with the same pitch-to-diameter ratio K_M ≈ 0.013 m (scaled by diameter, an estimate; a 10×5 has relatively more pitch, so K_M is higher and the index lower). With r = 0.21 m a tilt of 1° gives I_T ≈ 14.5 %, that is, ≈ 7–13 % in terms of the command, and 0.5° — ≈ 4–7 %.
- **Different props** (batches, pitch, repairs) give different thrust and different torque at the same RPM. Depending on where the “odd” prop ended up, the result is the one-motor pattern or pure yaw.

{{diagram:bf-motor-balance-tree|The decision is made from the pattern of the three indices, not from a single motor: only pitch/roll — the CG, only yaw — a tilt or the props, three indices of the same magnitude — one corner, and whether it is the motor or the prop is decided by the swap test.}}

### Diagnostic table

| Cause | Index pattern | What else is in the log | Check |
|---|---|---|---|
| The CG is offset | I_pitch and/or I_roll, I_yaw ≈ 0 | `axisI[0]`/`axisI[1]` are constant | move the battery by 5–10 mm, repeat the flight: the index changes in proportion |
| A weak motor (bearing, winding) | three indices ≈ w/2, the signs point to the corner | the `eRPM` of that motor is the same as the others at a higher command | swap the motors: the imbalance moves with the motor |
| A damaged or mismatched prop | the corner pattern or yaw | the `eRPM` of that motor is higher at a higher command, the prop gives less thrust per revolution; the 1× RPM peak in the spectrum grows | swap the props: the imbalance moves with the prop |
| A motor tilt, a bent arm | only I_yaw | a constant `axisI[2]` | a level or a straightedge along the shaft axis, inspection of the arm; a swap does not move the imbalance |
| Different timing or ESC settings | the one-corner pattern | in flight like a weak motor; on the bench without props the `eRPM` is lower at the same command | compare the settings of all the ESCs in the ESC configurator, one firmware and the same values |
| Motor order or direction | the aircraft does not take off or spins | runaway, the `RUNAWAY` flag | the Motors tab without props (`bf-setup-scratch`) |

A swap test does not move any mass, so the CG does not change after it. The correct hypothesis is the one whose CG estimate stayed the same after the swap while the “weak” corner moved together with the swapped part.

### A case: a 10" with a yaw imbalance
A 10-inch quadcopter. In level flight the yaw imbalance stayed at 6–8 % from flight to flight. Raising the yaw PID gains changed nothing. That is how it should be: a constant torque is held by the I term, and the diagonal difference remains with any PID. The medians of the level-flight segments showed two contributions at once: a pitch index (an offset CG) and a diagonal with the one-corner pattern (a weak motor). If the whole diagonal imbalance comes from one motor, then by the formula it needs about twice the index: w ≈ 2 · I_yaw, that is, 12–16 % of extra command. That is already a fault, not batch spread. By the estimate above, a 1° motor tilt on a 10" frame would give the same order (7–13 %), so the yaw index alone is not enough; the whole pattern decides. Both causes were fixed: the battery was moved and the motor replaced. After that a new log was recorded with the same flight program. It is the repeat log, not the feel, that closes the question. The medians of the real log are not given here: the lab below reproduces the same structure (the CG plus a weak motor) on synthetic data with known contributions, so that the method can be checked with a number.

### The order of work before tuning
1. Motor order and direction, `yaw_motors_reversed` according to the actual props (the Motors tab, props off).
2. Mechanics on the bench: motor play, free rotation, shafts, the arm and the motor mount, identical props from one batch, prop balancing (`f-frame-mech`).
3. The CG at the geometric center: hang the aircraft from points on the motor axes or rest it on two fingers under the lines 1–3 and 2–4.
4. A log of a hover and level flight of 10–20 s, the medians, the three indices. While the indices are above 5 %, fix the mechanics.
5. Only then the filters (`bf-filters`, `bf-rpm-filter`) and PID (`bf-pid`).

{{lesson:bf-pid|When the indices are within the norm, the next step is tuning by metrics: one parameter per flight, medians over maneuvers.}}

### Reference table (Betaflight 4.5)

| Parameter / field | Default | Range | Role in the balance |
|---|---|---|---|
| `yaw_motors_reversed` | OFF | OFF, ON | ON for props-out: the sign of the yaw PID is inverted, the numbers are the same |
| `motor_output_reordering` | 0,1,2,3… | output indices | reorders only the physical outputs, the log stays in mixer order |
| `dshot_idle_value` (in 2025.12 `motor_idle`) | 550 | 0–2000 | the lower limit of `motorOutput`: 158 at 550 |
| `motor_output_limit` | 100 | 1–100 % | the upper limit: 2047 at 100, 1647 at 80 |
| `dyn_idle_min_rpm` | 0 | 0–200 (×100 RPM) | > 0 → the lower limit in the header is 48 |
| `thrust_linear` | 0 | 0–150 | ≠ 0 distorts the pidSum ↔ command relation |
| `mixer_type` | LEGACY | LEGACY, LINEAR, DYNAMIC, EZLANDING | how the mixer compresses the corrections on saturation |
| `iterm_windup` | 85 | 30–100 % | the `motorMixRange` threshold above which I grows more slowly (a different meaning in 2025.12: 80, 20–100 % — the I limit in % of `pidsum_limit`) |
| `iterm_limit` (removed in 2025.12) | 400 | 0–500 | the I-term limit |
| `pidsum_limit` / `pidsum_limit_yaw` | 500 / 400 | 100–1000 | the limit of the P+I+D+F sum, lower for yaw |
| `blackbox_disable_motors` | OFF | OFF, ON | never enable it: without `motor[]` there is no balance |
| `blackbox_high_resolution` | OFF | OFF, ON | ON → gyro, rcCommand, setpoint ×10 in the log |
| the `motorOutput` header | 158,2047 | — | low, high for the conversion to percent |

In 2025.12 `mixerQuadX[]`, the sign of `yaw_motors_reversed`, the `motor[]` fields and the `motorOutput` line are unchanged. `dshot_idle_value` was renamed to `motor_idle` (the same default, 550), `iterm_limit` was removed, and `iterm_windup` became the I-term limit: 80 % of `pidsum_limit` (`flight/pid_init.c`), that is, 400 for roll and pitch and 320 for yaw.

### Place in the system
- **Receives:** a log with `motor[0..3]`, `axisI`, `rcCommand`, gyro and `eRPM` (`bf-blackbox`); the correct motor order and direction (`bf-setup-scratch`); the quadratic relation of thrust to RPM and the torque-to-thrust ratio (`f-aero-props`, `des-thrust-stand`).
- **Provides:** a mechanically trued aircraft with control headroom — to the filters (`bf-filters`) and to tuning (`bf-pid`); the conclusion “motor, prop or ESC” — to motor and ESC maintenance (`f-motors-esc`).
- **If you get it wrong here:** the imbalance is left in, and PID holds it with the I term. In a punch-out one motor hits 100 %, the heading drifts in a turn, and that motor runs hot. The pilot “treats” this by raising I or D (`bf-pid`) and gets hot motors and noise, which is then taken for a filter problem (`bf-filters`).

## practice
The main path needs no hardware. The script reads the CSV from `blackbox_decode`, finds the steady segment by itself, and computes the medians, the indices and the “CG + one motor” hypotheses. There is no log of your own yet, so the script generates three synthetic logs with known defects and checks that the method finds them. Only Python 3 is needed; `numpy` is optional: without it the medians are computed by `statistics` with the same result.

### Step 1. The range and percent
Before computing anything, convert the values to percent of travel. By default the header is `motorOutput:158,2047`, so 876 → (876 − 158)/1889 · 100 = 38.01 %. With dynamic idle the header is `48,2047`, and the same 876 gives 41.42 %. Work it out yourself for `motor_output_limit = 80`: the upper limit is 1647, and the value 876 gives (876 − 158)/(1647 − 158) · 100 = 48.22 %. Note for yourself: the range is taken from the header of the particular log, not from memory.

### Step 2. The script
Save it as `motor_balance.py`. The `make_log` function writes a CSV in the `blackbox_decode` format. Takeoff 0–3 s, hover 3–19 s, maneuvers 19–22 s (throttle ±400, gyro up to 150 °/s), level flight 22–34 s, landing. Every output carries 2.5 % of noise and a slow “PID correction” of ±1.5 % at 1.3 Hz.

```python
#!/usr/bin/env python3
"""Motor balance from a blackbox_decode CSV (Betaflight 4.5, Quad X, motors 1 RR, 2 FR, 3 RL, 4 FL).

  python3 motor_balance.py LOG00001.01.csv --motor-range 158,2047   # own log; range = header "motorOutput"
  python3 motor_balance.py LOG00001.01.csv --hires                  # log header blackbox_high_resolution:1
  python3 motor_balance.py --demo                                   # synthetic logs A, B, C with known faults
Standard library only; numpy is used for the medians if it is installed.
"""
import argparse, csv, math, os, random, re, statistics, sys, tempfile

try:
    import numpy as np
    median = lambda xs: float(np.median(xs))
except ImportError:
    median = statistics.median

#        motor[0] 1 RR, motor[1] 2 FR, motor[2] 3 RL, motor[3] 4 FL
SIGN = {"pitch": (+1, -1, +1, -1),   # rear pair (1,3) minus front pair (2,4)
        "roll":  (-1, -1, +1, +1),   # left pair (3,4) minus right pair (1,2)
        "yaw":   (+1, -1, -1, +1)}   # diagonal 1+4 minus diagonal 2+3
NAME = ("1 RR", "2 FR", "3 RL", "4 FL")
NEIGH = {0: (1, 2, 3), 1: (0, 3, 2), 2: (0, 3, 1), 3: (1, 2, 0)}   # motor: (neighbour, neighbour, opposite)


def read_csv(path):
    with open(path, newline="") as f:
        rd = csv.reader(f)
        head = [re.sub(r"\s*\(.*\)$", "", h.strip()) for h in next(rd)]   # 'time (us)' -> 'time'
        need = ["time", "rcCommand[3]"] + [f"gyroADC[{a}]" for a in range(3)] + [f"motor[{i}]" for i in range(4)]
        miss = [n for n in need if n not in head]
        if miss:
            sys.exit(f"{path}: no columns {miss} (blackbox_decode CSV of a quad expected)")
        pos = {n: head.index(n) for n in need}
        cols = {n: [] for n in need}
        for row in rd:
            if len(row) >= len(head):
                for n in need:
                    cols[n].append(float(row[pos[n]]))
    return cols


def steady_segment(c, block_s=0.5, thr_span_max=20.0, gyro_rms_max=20.0, thr_min=1150, min_s=10, max_s=20, scale=1.0):
    """Longest run of 0.5 s blocks with throttle span <= 20 and gyro RMS <= 20 deg/s, trimmed to 20 s.
    All thresholds are course guidelines; scale = 10 for blackbox_high_resolution (rcCommand and gyro x10)."""
    t = c["time"]
    fs = (len(t) - 1) / ((t[-1] - t[0]) / 1e6)
    blk = max(1, int(round(fs * block_s)))
    good = []
    for b in range(len(t) // blk):
        sl = slice(b * blk, (b + 1) * blk)
        thr = c["rcCommand[3]"][sl]
        rms = math.sqrt(sum(v * v for a in range(3) for v in c[f"gyroADC[{a}]"][sl]) / (3 * blk))
        good.append(max(thr) - min(thr) <= thr_span_max * scale and rms <= gyro_rms_max * scale
                    and min(thr) >= thr_min * scale)
    best, start = (0, 0), None
    for i, ok in enumerate(good + [False]):
        if ok and start is None:
            start = i
        elif not ok and start is not None:
            best = max(best, (start, i), key=lambda r: r[1] - r[0])
            start = None
    n = best[1] - best[0]
    if n * block_s < min_s:
        return None
    keep = min(n, int(max_s / block_s))
    i0 = (best[0] + (n - keep) // 2) * blk
    return i0, i0 + keep * blk, fs


def analyse(path, lo, hi, props_out=False, scale=1.0):
    c = read_csv(path)
    seg = steady_segment(c, scale=scale)
    if seg is None:
        print(f"{os.path.basename(path)}: no steady segment >= 10 s - fly 10-20 s of level hover/cruise")
        return None
    i0, i1, fs = seg
    t0 = (c["time"][i0] - c["time"][0]) / 1e6
    pct = [median([(v - lo) / (hi - lo) * 100 for v in c[f"motor[{i}]"][i0:i1]]) for i in range(4)]
    mean = sum(pct) / 4
    ind = {k: sum(s * p for s, p in zip(sg, pct)) / 2 / mean * 100 for k, sg in SIGN.items()}
    print(f"{os.path.basename(path)}: steady {t0:.1f}-{t0 + (i1 - i0) / fs:.1f} s ({(i1 - i0) / fs:.0f} s, {fs:.0f} Hz)")
    print("  medians, % of motorOutput range: " + "  ".join(f"{NAME[i]} {pct[i]:.2f}" for i in range(4)) + f"  mean {mean:.2f}")
    for k, txt in (("pitch", "rear-front"), ("roll", "left-right"), ("yaw", "diag 1+4 - 2+3")):
        v = ind[k]
        verdict = "ok" if abs(v) <= 2 else ("watch" if abs(v) <= 5 else "find the hardware cause")   # course guideline
        print(f"  {k:5s} {txt:15s} {v:+6.2f} %  {verdict}")
    if abs(ind["yaw"]) > 2:
        pair = "1+4" if ind["yaw"] > 0 else "2+3"
        cw = (ind["yaw"] > 0) != props_out          # props-in: motors 1 and 4 spin CW
        print(f"  pair {pair} works harder: if the pattern is pure yaw, a parasitic torque turns the nose "
              f"{'right (CW)' if cw else 'left (CCW)'} seen from above; if all three indices match, one motor of it is weak")
    cands = []
    for k, (a, b, o) in NEIGH.items():
        base = pct[a] + pct[b] - pct[o]           # what motor k would need if only the CG were off
        w = (pct[k] / base - 1) * 100
        fixed = pct[:k] + [base] + pct[k + 1:]
        cg = {ax: sum(s * p for s, p in zip(SIGN[ax], fixed)) / 2 / (sum(fixed) / 4) * 100 for ax in ("pitch", "roll")}
        kind = "weak" if w > 1.0 else ("strong" if w < -1.0 else "")     # 1 %: course guideline
        if kind:
            print(f"  exact fit: motor {NAME[k]} {kind:6s} {w:+.1f} % + CG offset pitch {cg['pitch']:+.1f} % roll {cg['roll']:+.1f} %")
        if kind == "weak":
            cands.append((k, w, cg))
    if not cands:
        print("  hypothesis: no single weak motor; pitch/roll = CG offset, yaw = tilted motors / props")
    return {"pct": pct, "ind": ind, "cands": cands}


def make_log(path, cg_rear=0.0, cg_left=0.0, weak=None, seed=1, fs=1000, dur=40.0, lo=158, hi=2047, hover=38.0):
    """Synthetic blackbox_decode CSV: take-off, 16 s hover, manoeuvres, 12 s cruise, landing.
    cg_rear / cg_left: rear-front / left-right imbalance in % of the mean; weak = (motor index, extra %)."""
    rnd = random.Random(seed)
    base = []
    for i in range(4):
        m = 1 + SIGN["pitch"][i] * cg_rear / 200 + SIGN["roll"][i] * cg_left / 200
        if weak and weak[0] == i:
            m *= 1 + weak[1] / 100
        base.append(m)
    head = ["loopIteration", "time (us)", "rcCommand[3]"] + [f"gyroADC[{a}]" for a in range(3)] + [f"motor[{i}]" for i in range(4)]
    with open(path, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(head)
        for n in range(int(dur * fs)):
            t = n / fs
            if t < 3:   thr, k, g = 1000 + 150 * t, t / 3, 40.0                # take-off ramp
            elif t < 19: thr, k, g = 1450, 1.0, 6.0                              # hover
            elif t < 22: thr, k, g = 1450 + 400 * math.sin(2 * math.pi * t), 1 + 0.6 * math.sin(2 * math.pi * t), 150.0
            elif t < 34: thr, k, g = 1470, 1.03, 8.0                             # level cruise
            else:        thr, k, g = 1470 - 70 * (t - 34), 1 - (t - 34) / 7, 30.0   # landing
            wob = 1.5 * math.sin(2 * math.pi * 1.3 * t)                         # PID corrections around trim
            row = [n, int(t * 1e6), int(thr)] + [round(rnd.gauss(0, g)) for _ in range(3)]
            for i in range(4):
                p = hover * k * base[i] + SIGN["roll"][i] * wob + rnd.gauss(0, 2.5)
                row.append(int(round(lo + max(0.0, min(100.0, p)) / 100 * (hi - lo))))
            wr.writerow(row)


def demo():
    d = tempfile.mkdtemp(prefix="bfmb_")
    logs = [("A", "CG rear 4 %, motor 4 FL +6 %", dict(cg_rear=4.0, weak=(3, 6.0), seed=1)),
            ("B", "swap test: motors 1 and 4 swapped, CG unchanged", dict(cg_rear=4.0, weak=(0, 6.0), seed=2)),
            ("C", "battery moved forward, weak motor replaced", dict(seed=3))]
    res = {}
    for name, what, kw in logs:
        p = os.path.join(d, f"LOG_{name}.csv")
        make_log(p, **kw)
        print(f"== {name}: injected {what}")
        res[name] = analyse(p, 158, 2047)
    print("== A vs B: the swap moved no mass, so the true hypothesis keeps its CG and its motor moves 4 <-> 1")
    swap = {0: 3, 3: 0, 1: 1, 2: 2}
    for k, wa, cga in res["A"]["cands"]:
        hb = next((h for h in res["B"]["cands"] if h[0] == swap[k]), None)
        if hb is None:
            print(f"  motor {NAME[k]}: no matching hypothesis in B -> rejected")
            continue
        dcg = max(abs(cga[ax] - hb[2][ax]) for ax in ("pitch", "roll"))
        print(f"  motor {NAME[k]} (A) -> {NAME[hb[0]]} (B): CG change {dcg:.1f} % -> {'confirmed' if dcg < 1.0 else 'rejected'}")  # 1 %: course guideline


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="*")
    ap.add_argument("--motor-range", default="158,2047", help="header line motorOutput: low,high")
    ap.add_argument("--props-out", action="store_true", help="yaw_motors_reversed = ON")
    ap.add_argument("--hires", action="store_true", help="blackbox_high_resolution = ON: rcCommand, gyro x10")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    if a.demo or not a.csv:
        demo()
    lo, hi = (float(x) for x in a.motor_range.split(","))
    for p in a.csv:
        analyse(p, lo, hi, a.props_out, 10.0 if a.hires else 1.0)
```

### Step 3. A run on synthetic data
`python3 motor_balance.py --demo`. The generator is deterministic (`random.Random(seed)`), and the output must match to the hundredths:

```text
== A: injected CG rear 4 %, motor 4 FL +6 %
LOG_A.csv: steady 3.0-19.0 s (16 s, 1000 Hz)
  medians, % of motorOutput range: 1 RR 38.75  2 FR 37.22  3 RL 38.80  4 FL 39.54  mean 38.58
  pitch rear-front       +1.03 %  ok
  roll  left-right       +3.09 %  watch
  yaw   diag 1+4 - 2+3   +2.95 %  watch
  pair 1+4 works harder: if the pattern is pure yaw, a parasitic torque turns the nose right (CW) seen from above; if all three indices match, one motor of it is weak
  exact fit: motor 1 RR weak   +6.2 % + CG offset pitch -1.9 % roll +6.1 %
  exact fit: motor 2 FR strong -5.8 % + CG offset pitch -1.9 % roll +0.1 %
  exact fit: motor 3 RL strong -5.5 % + CG offset pitch +3.9 % roll +5.9 %
  exact fit: motor 4 FL weak   +6.1 % + CG offset pitch +4.0 % roll +0.1 %
== B: injected swap test: motors 1 and 4 swapped, CG unchanged
LOG_B.csv: steady 3.0-19.0 s (16 s, 1000 Hz)
  medians, % of motorOutput range: 1 RR 41.08  2 FR 37.27  3 RL 38.75  4 FL 37.22  mean 38.58
  pitch rear-front       +6.93 %  find the hardware cause
  roll  left-right       -3.09 %  watch
  yaw   diag 1+4 - 2+3   +2.95 %  watch
  pair 1+4 works harder: if the pattern is pure yaw, a parasitic torque turns the nose right (CW) seen from above; if all three indices match, one motor of it is weak
  exact fit: motor 1 RR weak   +5.9 % + CG offset pitch +4.0 % roll -0.1 %
  exact fit: motor 2 FR strong -5.8 % + CG offset pitch +3.9 % roll -5.9 %
  exact fit: motor 3 RL strong -5.5 % + CG offset pitch +9.7 % roll -0.1 %
  exact fit: motor 4 FL weak   +6.5 % + CG offset pitch +10.0 % roll -6.1 %
== C: injected battery moved forward, weak motor replaced
LOG_C.csv: steady 3.0-19.0 s (16 s, 1000 Hz)
  medians, % of motorOutput range: 1 RR 38.01  2 FR 38.06  3 RL 38.01  4 FL 38.01  mean 38.02
  pitch rear-front       -0.07 %  ok
  roll  left-right       -0.07 %  ok
  yaw   diag 1+4 - 2+3   -0.07 %  ok
  hypothesis: no single weak motor; pitch/roll = CG offset, yaw = tilted motors / props
== A vs B: the swap moved no mass, so the true hypothesis keeps its CG and its motor moves 4 <-> 1
  motor 1 RR (A) -> 4 FL (B): CG change 12.3 % -> rejected
  motor 4 FL (A) -> 1 RR (B): CG change 0.3 % -> confirmed
```

The analysis. **Log A** shows the main trap: I_pitch = +1.03 %, “normal”, although a CG offset of 4 % was injected. The weak front motor 4 raised the front and masked the heavy rear. Yet roll of +3.09 % appeared, although there is no lateral CG offset. The indices are not the causes; they are only a pattern. The solver returns four exact solutions. The two “strong” ones (motors 2 and 3, w ≈ −5.5…−5.8 %) are plausible only if the diagonal 2+3 carries props of a different batch or pitch. Two “weak” ones remain, and they describe the medians equally well: “motor 4 +6.1 %, CG rearward 4.0 %” and “motor 1 +6.2 %, CG to the left 6.1 % and forward 1.9 %”. One log is not enough to choose. Note that w is the same in both (about 6 %): it depends only on the diagonal imbalance, and the CG does not affect the diagonal. **Log B** is the swap test: motors 1 and 4 are swapped, and no mass was moved. The “motor 4” hypothesis turns into “motor 1” with the same CG (+4.0 %), a change of 0.3 %, and the hypothesis is confirmed. The alternative would give a CG jump of 12.3 % with no mass moved; that is impossible, and the hypothesis is rejected. **Log C** — after the battery was moved and the motor replaced, all the indices are −0.07 %. That is the check of the repair.

{{lesson:bf-tuning-method|Check a motor or prop replacement as an A/B test: the same maneuver, a control flight and a comparison of the medians of two logs, not one “before” and one “after”.}}

### Step 4. Your own log
Decode the log: `blackbox_decode LOG00001.BFL`. Without `--index` all the logs of the file are decoded into `LOG00001.01.csv`, `.02.csv`…, and with `--index N` — only the Nth. Check `grep -a blackbox_high_resolution LOG00001.BFL`: with a value of 1 the throttle and the gyro in the log are multiplied by 10, so run the script with `--hires`, otherwise it will not find a steady segment. Get the range: `grep -a motorOutput LOG00001.BFL`. Run: `python3 motor_balance.py LOG00001.01.csv --motor-range 158,2047`, and add `--props-out` for props-out. If the script prints `no steady segment >= 10 s`, the flight had no level segment: fly 15–20 s of hover. For a cross-check, open `axisI[2]` over the same segment in Blackbox Explorer: the median S should give a diagonal difference of about S/5 percentage points (a guideline for `thrust_linear` = 0, airmode on and no saturation; without airmode multiply by 0.5 + throttle).

### Moving to real hardware
**The bench, props off.** Save `diff all`.
1. The Motors tab: the motors one at a time at 5–10 %, the order 1 RR, 2 FR, 3 RL, 4 FL, the direction props-in (or props-out with `yaw_motors_reversed = ON`).
2. The battery is disconnected. Turn each motor by hand: no grinding, no contact between the bell and the stator, no axial play. The shaft has no runout.
3. Tilt: put a straightedge or a level against the shaft axis of each motor relative to the plane of the frame. If a tilt is visible by eye, the arm or the mount is corrected before flight: by the estimate in the theory, 1° on a 10" is already about 7 % in yaw.
4. The CG: the aircraft with the battery and the full payload on two fingers under the line of motors 1–3, then 2–4. If it tips — move the battery and record the position (a mark on the frame).

**The field; the props go on here.** Calm air or wind of no more than 3–4 m/s (a course guideline), a height of 2–3 m, Blackbox ≥ 1 kHz, ANGLE or ACRO as you prefer, one mode in all the flights. The program: 20 s of hover, 15 s of level straight flight, landing. Repeat on a second battery. If I_yaw or I_pitch is above 5 % in both logs — the swap test. First swap the props of the suspect corner and its diagonal partner: motors 1 and 4 (and 2 and 3) have the same rotation, so the props are interchangeable. A flight, a log. If the imbalance did not move with the prop — swap the motors (the ESCs stay on their pads). **Right after swapping the motors, check the direction in the Motors tab without props:** the rotation is set by the ESC setting and the phase order at the pad, not by the motor itself, and the swapped motor may spin the other way. Then a flight, a log. It moved with the motor — the motor; it stayed in place even after that — the ESC, the arm or the mount.

**Abort the flight and land if:** the aircraft drifts or spins and the stick cannot hold it; the hover throttle is above 60 % (a course guideline: a mistake in the mass or the props); you hear rattling or a new sound; after landing you cannot keep a finger on a motor for 5 s; one motor in the hover log is above 80 % of travel (the numbers are course guidelines). After a swap test the first takeoff is a short hop to 1 m: it is easy to get a prop direction wrong during the swap.

Self-check: the lab is complete when:
- **Calculation (the main path):** 876 with `158,2047` = 38.01 %, with `48,2047` = 41.42 %, with `motor_output_limit = 80` = 48.22 % (±0.01).
- **Calculation:** the `--demo` output matched the output above: in log A the indices are +1.03/+3.09/+2.95 %, four exact solutions (the two “weak” ones — motors 1 and 4), in the A–B comparison motor 4 FL is confirmed (a CG change of 0.3 %), motor 1 RR is rejected (12.3 %), and in log C all three indices are −0.07 %.
- **Calculation:** you wrote down in your own words why I_pitch is “normal” in log A with a CG offset of 4 %, and compared it with the reference below.
- **Hardware:** in two logs of level flight with one program all three indices are ≤ 2 % (a course guideline). If not — for every index above 5 % the cause found by the swap test or by inspection is written down, and a log after the fix is saved in which the index is ≤ 2 %.

**Reference for self-check.** The correct explanation of log A: motor 4 needs 6 % more, and that raises the average output of the front pair by 3 %. The heavy rear raises the rear pair by 4 % relative to the front one, and the difference gives about +1 %. The same extra output of motor 4 adds +3 % to roll (it is on the left) and to yaw (it is in the pair 1+4). Typical mistakes. “The CG is fine, since I_pitch is 1 %” — the indices add up, and a cause is never assigned from a single index. “A weak motor 1, since the hypothesis exists” — from one log the “motor 1” and “motor 4” hypotheses are indistinguishable; the swap test decides. The output in percent looks like 40–45 instead of 38: the range `48,2047` was given to the script for a log whose header has 158.

## diagnostics
- **Symptom:** the aircraft slowly yaws in hover, and raising yaw P or I does not help
  - Possible cause: a tilted motor or a bent arm, different props in a pair.
  - What you see in the log: I_yaw consistently above 5 %, I_pitch and I_roll near zero, a constant `axisI[2]`.
  - What to do: check the shaft axis of each motor relative to the frame, straighten or replace the arm, fit props from one batch.
- **Symptom:** one motor is noticeably hotter than the others after a flight
  - Possible cause: it constantly runs at a raised command (a weak motor, a damaged prop, the CG offset toward it).
  - What you see in the log: the median of that `motor[i]` is higher, and the index pattern points to its corner.
  - What to do: swap the props, then swap the motors; with a pitch/roll-only pattern — move the battery.
- **Symptom:** the script prints `no steady segment >= 10 s`
  - Possible cause: the flight had no 10 s without throttle changes, or the aircraft is oscillating (gyro RMS > 20 °/s).
  - What to do: check `blackbox_high_resolution` in the header (with 1 — `--hires`); for a manual hover raise `thr_span_max` to 40–50; a separate flight with 20 s of hover; if it oscillates in hover too — deal with the oscillation first (`bf-pid`, `bf-filters`).
- **Symptom:** the motor percentages in hover are 3–4 points higher than expected
  - Possible cause: a wrong `--motor-range`, for example 48 instead of 158 with dynamic idle off.
  - What to do: take `motorOutput` from the header of that log (`grep -a motorOutput`).
- **Symptom:** the indices jump from flight to flight by more than 2 points
  - Possible cause: wind, different segments (hover and a pass), the battery shifts in flight.
  - What to do: one program, calm air, a strap and a stop for the battery, compare segments of one type.
- **Symptom:** after the swap test the aircraft spins right at takeoff
  - Possible cause: a prop was fitted upside down or on a motor of the other rotation.
  - What to do: disarm, compare the rotation with the Quad X diagram, match the prop to the motor direction.
- **Symptom:** on 2025.12 `get dshot_idle_value` reports that there is no such parameter
  - Possible cause: it was renamed in 2025.12.
  - What to do: `get motor_idle`, the same default, 550.

## checklist
- The order 1 RR, 2 FR, 3 RL, 4 FL and the direction are checked in the Motors tab without props
- `yaw_motors_reversed` matches the props (props-out → ON)
- The motors have no play or grinding, the shafts are straight, the motor axes are parallel, the props are from one batch and balanced
- The CG is at the center: the aircraft with the battery does not tip on the lines 1–3 and 2–4, and the battery position is marked
- The `motorOutput` range is taken from the header of the particular log
- The medians over a 10–20 s segment without throttle transitions, the three indices are computed
- The indices are ≤ 2 % in two logs (a course guideline); everything above 5 % is explained by the swap test or by inspection
- Only after that — the filters and PID

## references
- Betaflight `flight/mixer_init.c`, 4.5-maintenance (mixerQuadX, getMotorOutputLow/High, dynamic idle) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/mixer_init.c | primary | A
- Betaflight `flight/mixer.c`, 4.5-maintenance (yaw_motors_reversed, applyMixToMotors, PID_MIXER_SCALING) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/mixer.c | primary | A
- Betaflight `blackbox/blackbox.c`, 4.5-maintenance (the motor and eRPM fields, the motorOutput and gyro_scale headers) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/blackbox/blackbox.c | primary | A
- Betaflight `drivers/dshot.c`, 4.5-maintenance (dshotInitEndpoints) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/drivers/dshot.c | primary | A
- Betaflight `flight/pid.c`, 4.5-maintenance (iterm_windup, iterm_limit, pidsum_limit) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/pid.c | primary | A
- Betaflight `flight/mixer_init.c`, 2025.12-maintenance (the same Quad X table) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12-maintenance/src/main/flight/mixer_init.c | primary | A
- blackbox-tools `blackbox_decode.c` (the CSV column names, units, the .NN.csv files) | https://raw.githubusercontent.com/betaflight/blackbox-tools/master/src/blackbox_decode.c | primary | A
- Running with Reversed Motors — Betaflight Documentation | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/guides/current/Reversed-motor-direction.md | primary | A
- Motors Tab — Betaflight Documentation (props-in / props-out) | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/app/motors-tab.md | primary | B

## notes
The 2 % and 5 % thresholds, the steady-segment criteria (a throttle span of 20 per 0.5 s, 20 °/s, 10–20 s), the solution filter w > 1 % and the 1 % CG tolerance in the A–B comparison are course guidelines; the firmware has none of them. The relation “thrust index = k × command index” is taken from the 15×5 table (thrust ∝ command^k, k ≈ 1.1–1.8; 2 is the upper bound for RPM proportional to the command). For your own motor and prop it is worth measuring k on a thrust stand. K_M for the 10" is rescaled by diameter from the tabulated 15×5 at the same P/D; it is an estimate. The medians of the real log from the case are not given, and the numbers of the practice were obtained on synthetic data.
