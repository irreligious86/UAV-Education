---
id: bf-tuning-method
title: "The A/B method: tuning as an experiment"
level: L2
readingTime: 45 min
firmware: Betaflight 4.5 (checked against the 4.5.3 source); the 2025.12 differences are noted
status: published
added: 2026-11-25
tags:
  - Betaflight
  - tuning
  - Blackbox
  - A/B
  - statistics
related:
  - bf-pid
  - bf-blackbox
  - bf-motor-balance
  - bf-adjustments
  - bf-filters
  - data-python
  - math-prob-est
next:
  - bf-adjustments
source: content/betaflight/bf-tuning-method.md
source_hash: abcc07355f28
---

## summary
“It got softer with the new D” is a hypothesis, not a result. This module turns the comparison of two settings into an experiment: one change, one flight program, the ABBA order within one window of conditions, log metrics with exact definitions and a minimum of statistics — the spread, the ratio of the effect to the standard error, and a permutation test. It covers what Betaflight 4.5 can switch in flight: the rate profile — yes, the PID profile — not by any standard means, a single PID gain — yes, with an absolute `adjrange` slot. The lab is a Python script: the CSV from `blackbox_decode` → maneuvers → five metrics → a verdict with p. On synthetic data with a known effect (−15 % propwash) one pair of flights decides nothing, five pairs in ABBA order find the effect, and the same amount flown in blocks AAAAA BBBBB loses it.

## theory
### Why one flight proves nothing
The propwash metric from two flights with the very same setting differs by 5–15 % (a course guideline; in the lab model CV ≈ 8 %): a different gust, a different pack, the pilot caught the throttle earlier. One flight of A against one flight of B gives no estimate of the spread within an arm, and a difference of 13 % cannot be told from noise. In the lab one pair of flights shows −32 % in overshoot and −33 % in motor headroom, although B does not change them at all.

Impressions are a source of hypotheses, not a decision. A pilot who knows that the “new, better” profile is on flies and judges differently (placebo). In the `bf-pid` case (one flight per profile) the log supported “sharper” for SHARP and showed its price of +45 % motor noise, which cannot be felt by hand; by the standards of this module that is a hypothesis for an A/B test with 4–5 flights per arm.

Confounders change together with the setting and shift the metric by themselves:

| Factor | How it distorts | How to control it |
|---|---|---|
| Battery: charge, sag | on an empty pack delay and propwash grow | one batch, the same charge and landing voltage; ABBA; the same `vbat_sag_compensation` |
| Motor and ESC heating | the metrics drift toward the end of the session | the same pause between flights, ABBA |
| Wind | propwash and tracking error | up to 5 m/s (`bf-pid`), an entry in the log, ABBA |
| Props | a nick or a different batch changes the vibration | one set of props per session; if you changed them — start the session over |
| Pilot | different sharpness of the maneuvers | one program, one pilot, blind selection |
| Aircraft | “identical” drones have different CGs and motors | A and B on one aircraft (`bf-motor-balance`) |

{{lesson:bf-motor-balance|A motor imbalance and an offset CG shift all the metrics more than a slider step does: mechanics first, then A/B.}}

### The design of the experiment
1. **A hypothesis** with a target metric and a threshold — before the flights. An example: “B (`d_roll`/`d_pitch` 40/46 → 46/52 in 4.5) will reduce propwash by at least 10 % without raising the hover noise by more than 10 %”. A threshold written down in advance keeps you from later picking the metric that “worked out”.
2. **One change.** A is the control without edits, and B differs in one parameter or slider.
3. **A flight program** that is the same for all the flights (below); each maneuver feeds its own metric.
4. **The order.** ABA: the average of the two A flights cancels linear drift. ABBA ABBA…: the arms get almost the same drift. ABAB works too, but B always has one flight's worth more drift. The blocks AAAAA BBBBB are the worst option: the whole drift of the session falls on the difference.
5. **An A/A test.** A against A with the same program shows the metric's own noise. If it is comparable with the expected effect, more flights or a larger step are needed.
6. **Blind selection.** A helper sets the profile on the ground, and the pilot does not know what is being flown and writes down a 1–5 rating before the log is analyzed.

{{diagram:bf-ab-order|The number of flights is the same; the order decides: in the blocks AAAAA BBBBB the wind drift added an extra +15 % of propwash to B and ate the −15 % effect, while in ABBA order the drift was split almost evenly (+13.2 % and +13.8 %).}}

The flight program (about 30 s, repeated in every flight; the segmentation thresholds are course guidelines, and the lab script uses them):

| Maneuver | How | Metric | How the script finds the segment |
|---|---|---|---|
| Hover | 5 s at 1.5–2 m, sticks centered | gyro noise | \|setpoint\| < 20 °/s on all axes, throttle 1300–1600, ≥ 2 s |
| Roll snaps | 5 full-stick snaps of 0.25 s, a 0.75 s pause, alternating sign | tracking error, overshoot | \|setpoint[0]\| > 200 °/s for longer than 50 ms |
| Punch-out | 100 % throttle for 1–1.5 s | motor headroom | `rcCommand[3]` > 1900 for longer than 0.3 s |
| Descents | 3 times: throttle to zero for 1–1.5 s, a catch at 70 % | propwash | `rcCommand[3]` < 1150 for longer than 0.5 s |

The first and last 3 s of the log are discarded (takeoff and landing), as in `bf-pid`.

### How to switch between A and B in Betaflight 4.5
The best conditions are A and B in one flight: one pack, one wind. What the firmware can do (verified against the source):

- **There is no standard way to switch the PID profile in flight.** There is no such function in `fc/rc_adjustments.h` and no such mode in `fc/rc_modes.h` (4.5.3 and 2025.12); `MSP_SELECT_SETTING` silently ignores the PID profile while armed (`msp/msp.c`), and the stick commands and entering the OSD menu with the sticks work only while disarmed. On the ground: with the sticks (throttle down + yaw left + roll left / pitch forward / roll right → profiles 1/2/3 in the App numbering, that is, `profile 0`/`1`/`2`, `fc/rc_controls.c`), the OSD menu, Betaflight App or `profile N` (N = 0–3; the fourth profile — only the CLI, the OSD or the App). A comparison of PID profiles means separate flights. The gains themselves can be written over MSP in flight (`MSP_SET_PID`, `MSP_SET_PID_ADVANCED`, `MSP_SET_SIMPLIFIED_TUNING`, for example by a Lua script on the radio): only to RAM, with no Blackbox event — that is not a method for A/B. 4.5.3 also has a hole: the OSD menu opened through CRSF telemetry does not check the arm state and allows the profile to be changed in the air (closed in 2025.12) — this is dangerous and is not a method.
- **The rate profile — from a switch:** function 12 RATE_PROFILE, select mode, 3 positions (6 with `rate_6pos_switch = ON`, but there are 4 rate profiles, and positions 5–6 do nothing): `adjrange 0 0 3 900 2100 12 3 0 0` for a 3-position AUX4. Only for rates, expo and the throttle curve: there is no PID in it.
- **A single PID gain — with an absolute slot.** If a step function has `center` set, the value is taken straight from the channel: `center + (rc − 1500) · scale / 500`, where C division truncates the fraction toward zero (`processContinuosAdjustments`). A two-position switch gives exactly two values:

```
# AUX4 (index 3), 2-position switch: down = A, up = B (Betaflight 4.5)
adjrange 0 0 3 900 2100 20 3 43 3      # ROLL_D:  1000 -> 40, 2000 -> 46
adjrange 1 0 3 900 2100 17 3 49 3      # PITCH_D: 1000 -> 46, 2000 -> 52
```

20 and 17 are the CLI numbers of the functions ROLL_D and PITCH_D (the CLI number is the position in `defaultAdjustmentConfigs[]` plus 1, `bf-adjustments`). The combined 8 PITCH_ROLL_D would set both axes to one value, while the defaults differ (40 and 46). Endpoints of 988 and 2012 µs give −3.07 → −3 and +3.07 → +3, that is, 40 and 46; a switch at 1100 µs will give −2.4 → −2 and `d_roll` = 41. The 900–2100 range is “always active”, and the value is set by the switch position already at power-up. After the experiment remove the slots and enter the chosen value with `set`.

Changes are logged as the `INFLIGHT_ADJUSTMENT` event (code 13, `blackbox/blackbox.h`). In absolute mode the event is written on every change of the channel value, even if D did not change: a jittering channel (988 ↔ 989) fills `.event` with repeats, and the A/B boundary is the first event with a new `value`. `blackbox_decode` puts the events into `LOG00001.01.event` as JSON lines: `{"name":"Inflight adjustment", "time":…, "data":{"adjustmentFunction":"ROLL_D","value":46}}`, where the time is the same microsecond counter as `time (us)` in the CSV. That is how the boundaries of the A and B segments are found. The effective D in 4.5 is shown by `debug_mode = D_MIN`: `debug[2]` — roll, `debug[3]` — pitch, both ×10 (`flight/pid.c`). In 2025.12 the mode is called `D_MAX`, and the fields are different: `debug[2]` — the effective D ×10 only on the axis `gyro_filter_debug_axis`, `debug[3]` — the multiplier ×100. There `d_roll` is the base (30) and the top is `d_max_roll` (40), and the slot moves the base: a center of 43 would raise the base to 40/46 ≥ `d_max`, and dynamic D would turn off (it works only while `d_max` > D, `flight/pid_init.c`). For 2025.12 compute the center from the base: `adjrange 0 0 3 900 2100 20 3 33 3` (30/36) and `adjrange 1 0 3 900 2100 17 3 37 3` (34/40); the top `d_max_*` is not changed by a slot (`bf-adjustments`).

The log header has neither the number nor the name of the profile; the profile is recognized by its values: `rollPID:45,80,40`, `d_min:…` (`grep -a rollPID LOG00001.BFL`). Before takeoff check the profile in the OSD (`osd_pid_profile_name_pos`; the name is `profile_name`, up to 8 characters).

### The metrics: exact definitions
The five impression metrics (motor noise, propwash RMS, bounce-back, entry lag, peak tracking) are defined in `bf-pid`. Here are the quantities for A/B, each reduced to one number per flight:

| Metric | Definition | Segment | Better |
|---|---|---|---|
| gyro noise | the RMS of `gyroADC[0]` and `gyroADC[1]` after a 100–250 Hz band-pass filter, °/s | hover | lower |
| tracking error | RMS(`setpoint[0]` − `gyroADC[0]`), °/s | the snap + 150 ms after | lower |
| overshoot | (max gyro / max setpoint − 1) · 100 % in the direction of the snap | the snap + 150 ms | lower (down to zero) |
| propwash | the RMS of the roll and pitch gyro in the 20–70 Hz band, °/s | from 0.3 s after the throttle chop to 0.6 s after the catch | lower |
| motor headroom | 100 % − the 99th percentile of the most loaded motor, % of travel per the `motorOutput` header | punch-out | higher |
| motor temperature | by hand: an IR thermometer or a finger within the first 30 s after landing | after the flight | no higher than A |

The value for a flight is the median over the maneuvers: one bad snap does not spoil the number. The noise band lies above the control band and propwash, so a log at no less than 1 kHz is needed (`blackbox_sample_rate` 1/8 with an 8 kHz PID loop; the default 1/4 gives 2 kHz).

{{lesson:bf-pid|The five impression metrics, the “good/tolerable/problem” guidelines for a 5" and the case with four profiles are there.}}

### A minimum of statistics
The unit of replication is a flight (or a segment when switching from a switch), not a maneuver: the maneuvers of one flight share the battery and the wind.

- **The effect** Δ = x̄_B − x̄_A, in percent of x̄_A.
- **The pooled spread** s_p = √[((n_A − 1)s_A² + (n_B − 1)s_B²) / (n_A + n_B − 2)], where s is the standard deviation of an arm. With one flight per arm s is undefined.
- **The standard error of the difference** SE = s_p · √(1/n_A + 1/n_B). **A course guideline:** the effect is real if |Δ|/SE > 2 and the permutation test gave p < 0.05. At n = 5 the “2 SE” rule by itself corresponds to a level of about 0.08, so the deciding criterion is usually p < 0.05.
- **The permutation test.** If B changes nothing, the labels “A” and “B” are random. Enumerate all the splits of the n_A + n_B numbers into two groups: p is the share of splits where |the difference of the means| is no less than the observed one. Normality is not required, but there is a limit: the minimum p = 2 / C(2n, n) with n flights per arm.

| n per arm | splits C(2n, n) | minimum p |
|---|---|---|
| 1 | 2 | 1.000 |
| 2 | 6 | 0.333 |
| 3 | 20 | 0.100 |
| 4 | 70 | 0.029 |
| 5 | 252 | 0.0079 |
| 6 | 924 | 0.0022 |

With three flights per arm p < 0.05 is unattainable even with perfect separation, and with four all the B flights must turn out better than all the A flights.

- **The plan:** n ≈ 16 · (CV/Δ)², where CV is the flight-to-flight spread and Δ the expected effect, both as fractions of the mean. That is about an 80 % chance of catching the effect with the “2 SE” rule (16 ≈ 2 · (2 + 0.84)²), but no fewer than 4. CV 8 %, Δ 15 % → 4.6 → 5 flights. CV 12 %, Δ 10 % → 23.04 → 24: such an effect cannot be caught in a session; take a larger step.

{{diagram:chart-bf-ab-power|With a spread of 8 % the −15 % effect is found in 67 % of series with 4 flights per arm and in 92 % with 5; with 1–3 flights — never, and a comparison of A with A gives a false alarm in about 5 % of series.}}

“Not proven” does not mean “there is no effect”: the +6 % of noise in the lab is not visible in five pairs, and by the formula it needs about 30 flights per arm (16 · (0.08/0.06)² = 28.4). Such side effects are covered by a threshold: the motors are no hotter than with A.

### Reference table (Betaflight 4.5)

| Command / parameter | Default | Range | Role in A/B |
|---|---|---|---|
| `profile N` | 0 | 0–3 | select the PID profile, on the ground only |
| `rateprofile N` | 0 | 0–3 | select the rate profile |
| `diff all` | — | — | a backup of all the profiles; `diff` — only the current PID profile and rate profile |
| `adjrange i 0 ch start end fn adjch center scale` | empty | i 0–29 | 12 RATE_PROFILE, 17 PITCH_D, 20 ROLL_D, 8 PITCH_ROLL_D |
| `profile_name`, `osd_pid_profile_name_pos` | empty, hidden | up to 8 characters | see in the OSD what is being flown |
| `d_roll` / `d_pitch` | 40 / 46 | 0–250 (an adjustment slot — 0–200) | in 4.5 the top of D (2025.12: the base 30/34, the top is `d_max_*`) |
| `d_min_roll` / `d_min_pitch` | 30 / 34 | 0–250 | the base D in 4.5 |
| `blackbox_sample_rate` | 1/4 | 1/1 … 1/16 | ≥ 1 kHz |
| `blackbox_high_resolution` | OFF | OFF, ON | ON → gyro, setpoint, rcCommand ×10 |
| `debug_mode` | NONE | a table | D_MIN (2025.12: D_MAX) — the effective D |
| `vbat_sag_compensation` | 0 | 0–150 % | the same in A and B; only with an ADC voltage meter |
| `auto_profile_cell_count` | 0 | −1…8 | ≠ 0 changes the PID profile by itself: 0 for the duration of A/B |

A profile is copied to another profile by Betaflight App (`MSP_COPY_PROFILE`, 183) and the OSD menu (COPY PROF); there is no CLI command in either 4.5 or 2025.12. The backup is `diff all`, not `diff`: the latter saves only the current PID profile and rate profile.

### A case: two identical 7" quads with different profiles
Two 7-inch quadcopters of the same build, profile A on the first and B on the second, and by the logs B has 12 % less propwash. The conclusion “B is better” does not follow: the aircraft and the profile change together. The `bf-pid` case showed the scale: the single profile SHARP gave a bounce-back of 2.9 % and 8.5 % on two such drones — per the `bf-pid` analysis, because of different piloting sharpness; the “drone/session” difference turned out larger than the difference between profiles (6.0 and 8.5 % on one drone).

The correct design is a crossover: each aircraft flies both profiles in its own ABBA session, and the effect is computed within the aircraft (Δ₁, Δ₂). If they agree in sign and pass |Δ|/SE > 2 — the effect transfers. If Δ₁ ≈ −15 % and Δ₂ ≈ 0 — look for the cause in the second aircraft (motor balance, CG, props) before copying the profile. “A on one, B on the other” is good only for finding hypotheses.

### Place in the system
- **Receives:** a log with `setpoint`, `gyroADC`, `motor`, `rcCommand` and the adjustment events (`bf-blackbox`); trued mechanics (`bf-motor-balance`); a clean spectrum (`bf-filters`); candidates for a change and the impression metrics (`bf-pid`); adjustment slots for switching in flight (`bf-adjustments`).
- **Provides:** the decision “accept B / keep A / fly more” with the effect, the spread and p — to the tuning log and `diff all` in the repository (`eng-ci-configs`); an estimate of the metric noise (the A/A test) — for planning the next changes (`bf-pid`).
- **If you get it wrong here:** a profile “won” on one pair of flights, although the difference was noise. A week later it “stopped working”, and the pilot keeps turning PID (`bf-pid`), taking the wind for an effect every time. Or the profile was copied to a second aircraft, which has a different CG, and there B is worse than A (`bf-motor-balance`).

## practice
The main path needs no hardware. The script cuts the CSV from `blackbox_decode` into maneuvers by the rules from the program table, computes the metrics and prints a verdict. Without logs of your own it generates synthetic flights with a known truth: B reduces the propwash amplitude by 15 % and raises the gyro noise by 6 %. The spread: the propwash of a flight ×e^N(0, 0.05), of each descent ×e^N(0, 0.08), the noise ×e^N(0, 0.08); in the sessions the wind adds +3 % of propwash for every subsequent flight. Python 3.8+ is needed (`math.comb`), the standard library only.

### Step 1. The limit of the test and the plan
Work it out by hand before the flights. The minimum p = 2 / C(2n, n): n = 4 → 2/70 = 0.0286, n = 3 → 2/20 = 0.100. The plan n ≈ 16 · (CV/Δ)²: CV 8 %, Δ 15 % → 4.55 → 5 flights; CV 10 %, Δ 20 % → 4.0 → 4. Fewer than 4 flights per arm make no sense with this test for any effect.

### Step 2. The script
Save it as `ab_compare.py`. `make_flight` writes a CSV with the `blackbox_decode` columns (`time (us)`, `rcCommand[3]`, `setpoint[0..3]`, `gyroADC[0..2]`, `motor[0..3]`), 1 kHz. The gyro response is a second-order system (16 Hz, a damping ratio of 0.55), and propwash is a 30–45 Hz sine that builds up after the throttle chop and decays with a 0.2 s time constant, starting 0.3 s after the catch. The band-pass filter is a biquad run forward and backward, with no phase shift.

```python
#!/usr/bin/env python3
"""A/B comparison of Betaflight tunes from blackbox_decode CSVs (one value per flight, then statistics).

  python3 ab_compare.py --a A1.csv A2.csv ... --b B1.csv B2.csv ... [--target propwash] [--motor-range 158,2047]
  python3 ab_compare.py --a LOG.01.csv@40-95 --b LOG.01.csv@95-150     # windows (s from log start), in-flight A/B
  python3 ab_compare.py --demo                                         # synthetic flights with a known effect
Standard library only. Metrics per flight (medians over manoeuvres of the scripted program):
  noise     gyro roll+pitch RMS in 100-250 Hz on hover (|setpoint| < 20 deg/s, throttle 1300-1600, >= 2 s)
  track     RMS(setpoint - gyro) roll on each roll manoeuvre (|setpoint| > 200 deg/s for > 50 ms) + 150 ms after
  overshoot (max gyro / max setpoint - 1) * 100 % on the same windows, same sign as the setpoint
  propwash  gyro roll+pitch RMS in 20-70 Hz from 0.3 s into a dive (throttle < 1150 for >= 0.5 s) to 0.6 s after it
  headroom  100 % - 99th percentile of the highest motor output on a punch-out (throttle > 1900 for >= 0.3 s)
The first and last 3 s of every log are ignored (take-off, landing). Thresholds are course guidelines, not firmware values.
"""
import argparse, csv, itertools, math, os, random, re, statistics, sys, tempfile

LOWER_IS_BETTER = {"noise": True, "track": True, "overshoot": True, "propwash": True, "headroom": False}
UNIT = {"noise": "deg/s", "track": "deg/s", "overshoot": "%", "propwash": "deg/s", "headroom": "%"}
TRIM_S = 3.0


# ---------------------------------------------------------------- reading and segmenting
def read_csv(spec, scale=1.0):
    path, _, win = spec.partition("@")
    with open(path, newline="") as f:
        rd = csv.reader(f)
        head = [re.sub(r"\s*\(.*\)$", "", h.strip()) for h in next(rd)]
        need = ["time", "rcCommand[3]", "setpoint[0]", "setpoint[1]", "setpoint[2]", "gyroADC[0]", "gyroADC[1]"]
        need += [f"motor[{i}]" for i in range(4)]
        miss = [n for n in need if n not in head]
        if miss:
            sys.exit(f"{path}: no columns {miss}")
        pos = [head.index(n) for n in need]
        rows = [[float(r[p]) for p in pos] for r in rd if len(r) >= len(head)]
    c = {n: [r[k] for r in rows] for k, n in enumerate(need)}
    for n in need[1:7]:                                   # rcCommand, setpoint, gyro x10 with high resolution
        c[n] = [v / scale for v in c[n]]
    t0 = c["time"][0]
    c["t"] = [(v - t0) / 1e6 for v in c["time"]]
    lo, hi = (0.0, 1e9)
    if win:
        lo, hi = (float(x) for x in win.split("-"))
    keep = [i for i, t in enumerate(c["t"]) if max(lo, TRIM_S) <= t <= min(hi, c["t"][-1] - TRIM_S)]
    c["keep"] = set(keep)
    c["fs"] = (len(c["t"]) - 1) / (c["t"][-1] - c["t"][0])
    return c


def runs(c, cond, min_s):
    """Index ranges [i0, i1) where cond(i) holds for at least min_s seconds, inside the kept part."""
    out, start = [], None
    for i in range(len(c["t"]) + 1):
        ok = i < len(c["t"]) and i in c["keep"] and cond(i)
        if ok and start is None:
            start = i
        elif not ok and start is not None:
            if c["t"][i - 1] - c["t"][start] >= min_s:
                out.append((start, i))
            start = None
    return out


def bandpass(x, fs, f1, f2):
    """RBJ band-pass biquad (0 dB at the centre sqrt(f1*f2)), run forward and backward: no phase shift."""
    f0 = math.sqrt(f1 * f2)
    q = f0 / (f2 - f1)
    w = 2 * math.pi * f0 / fs
    al = math.sin(w) / (2 * q)
    b0, b2, a0, a1, a2 = al, -al, 1 + al, -2 * math.cos(w), 1 - al

    def run(s):
        y, x1, x2, y1, y2 = [], 0.0, 0.0, 0.0, 0.0
        for v in s:
            o = (b0 * v + b2 * x2 - a1 * y1 - a2 * y2) / a0
            x2, x1, y2, y1 = x1, v, y1, o
            y.append(o)
        return y
    return run(run(x)[::-1])[::-1]


def rms(xs):
    return math.sqrt(sum(v * v for v in xs) / len(xs)) if xs else float("nan")


def flight_metrics(c, lo, hi):
    fs, n = c["fs"], len(c["t"])
    thr, sp, g = c["rcCommand[3]"], c["setpoint[0]"], c["gyroADC[0]"]
    m = {}
    hover = runs(c, lambda i: max(abs(c[f"setpoint[{a}]"][i]) for a in range(3)) < 20 and 1300 <= thr[i] <= 1600, 2.0)
    hp = [bandpass(c[f"gyroADC[{a}]"], fs, 100, 250) for a in (0, 1)]
    m["noise"] = statistics.median([rms(hp[0][a:b] + hp[1][a:b]) for a, b in hover]) if hover else float("nan")
    man = runs(c, lambda i: abs(sp[i]) > 200, 0.05)
    tr, ov = [], []
    for a, b in man:
        b2 = min(n, b + int(0.15 * fs))
        tr.append(rms([sp[i] - g[i] for i in range(a, b2)]))
        s = 1 if sp[a] > 0 else -1
        ov.append((max(s * g[i] for i in range(a, b2)) / max(s * sp[i] for i in range(a, b)) - 1) * 100)
    m["track"] = statistics.median(tr) if tr else float("nan")
    m["overshoot"] = statistics.median(ov) if ov else float("nan")
    dives = runs(c, lambda i: thr[i] < 1150, 0.5)
    bp = [bandpass(c[f"gyroADC[{a}]"], fs, 20, 70) for a in (0, 1)]
    pw = []
    for a, b in dives:
        a2, b2 = a + int(0.3 * fs), min(n, b + int(0.6 * fs))
        pw.append(rms(bp[0][a2:b2] + bp[1][a2:b2]))
    m["propwash"] = statistics.median(pw) if pw else float("nan")
    punch = runs(c, lambda i: thr[i] > 1900, 0.3)
    hr = []
    for a, b in punch:
        top = sorted(max((c[f"motor[{k}]"][i] - lo) / (hi - lo) * 100 for k in range(4)) for i in range(a, b))
        hr.append(100 - top[int(0.99 * (len(top) - 1))])
    m["headroom"] = statistics.median(hr) if hr else float("nan")
    m["_count"] = (len(hover), len(man), len(dives), len(punch))
    return m


# ---------------------------------------------------------------- statistics
def perm_p(a, b, limit=20000, seed=7):
    """Two-sided permutation test on the difference of means: share of relabellings at least as extreme."""
    pool, na = a + b, len(a)
    obs = abs(statistics.fmean(b) - statistics.fmean(a))
    if math.comb(len(pool), na) <= limit:
        splits = itertools.combinations(range(len(pool)), na)
    else:
        rnd = random.Random(seed)
        splits = (rnd.sample(range(len(pool)), na) for _ in range(limit))
    hit = tot = 0
    for idx in splits:
        s = set(idx)
        xa = [pool[i] for i in s]
        xb = [pool[i] for i in range(len(pool)) if i not in s]
        hit += abs(statistics.fmean(xb) - statistics.fmean(xa)) >= obs - 1e-12
        tot += 1
    return hit / tot


def compare(a, b):
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    d = mb - ma
    if len(a) < 2 or len(b) < 2:
        return dict(ma=ma, mb=mb, d=d, rel=d / ma * 100, sp=float("nan"), se=float("nan"), z=float("nan"), p=perm_p(a, b))
    sp = math.sqrt(((len(a) - 1) * statistics.variance(a) + (len(b) - 1) * statistics.variance(b)) / (len(a) + len(b) - 2))
    se = sp * math.sqrt(1 / len(a) + 1 / len(b))
    return dict(ma=ma, mb=mb, d=d, rel=d / ma * 100, sp=sp, se=se, z=abs(d) / se if se else float("inf"), p=perm_p(a, b))


def verdict(r, lower_better):
    if math.isnan(r["se"]):
        return "no spread estimate (1 flight per arm)"
    if r["z"] <= 2 or r["p"] >= 0.05:
        return "within noise"
    better = (r["d"] < 0) == lower_better
    return "B better" if better else "B WORSE"


def report(title, A, B, target):
    print(f"== {title}: {len(A)} flight(s) A, {len(B)} flight(s) B, target metric '{target}'")
    print(f"  {'metric':9s} {'A mean':>8s} {'B mean':>8s} {'B-A':>7s} {'s_p':>6s} {'|d|/SE':>6s} {'p':>6s}  verdict")
    res = {}
    for k in LOWER_IS_BETTER:
        a, b = [f[k] for f in A], [f[k] for f in B]
        r = compare(a, b)
        res[k] = (r, verdict(r, LOWER_IS_BETTER[k]))
        print(f"  {k:9s} {r['ma']:8.2f} {r['mb']:8.2f} {r['rel']:+6.1f}% {r['sp']:6.2f} {r['z']:6.2f} {r['p']:6.3f}  {res[k][1]}")
    worse = [k for k, (r, v) in res.items() if v == "B WORSE"]
    if res[target][1] == "B better" and not worse:
        print(f"  DECISION: accept B ({target} {res[target][0]['rel']:+.1f} %, no side metric worse beyond noise)")
    elif res[target][1] == "B better":
        print(f"  DECISION: trade-off, B improves {target} but worsens {', '.join(worse)}: decide by the task")
    else:
        print(f"  DECISION: keep A, effect on {target} not shown; fly more pairs or drop the change")
    return res


# ---------------------------------------------------------------- synthetic flights
def lognorm(rnd, cv):
    return math.exp(rnd.gauss(0, cv))


def make_flight(path, arm, seed, slot=0, drift=0.0, fs=1000, dur=26.0, lo=158, hi=2047):
    """Scripted program: take-off, hover 2-6 s, five roll steps +-500 deg/s at 6.5-10.5 s, punch-out 12.3-13.5 s,
    three zero-throttle dives at 14, 17, 20 s (1.2 s cut, 0.8 s recovery at 1700), hover, landing.
    Arm B: propwash amplitude x0.85, gyro noise x1.06. drift: +share of propwash per flight slot (wind rising)."""
    rnd = random.Random(seed)
    pw_amp = 40.0 * (0.85 if arm == "B" else 1.0) * lognorm(rnd, 0.05) * (1 + drift * slot)
    noise = 3.0 * (1.06 if arm == "B" else 1.0) * lognorm(rnd, 0.08)
    zeta, wn = 0.55 * lognorm(rnd, 0.05), 2 * math.pi * 16 * lognorm(rnd, 0.04)
    dive_amp = [lognorm(rnd, 0.08) for _ in range(3)]
    dive_f = [rnd.uniform(30, 45) for _ in range(3)]
    punch_top = 93.0 * lognorm(rnd, 0.01)
    x = v = 0.0
    with open(path, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["loopIteration", "time (us)", "rcCommand[3]"] + [f"setpoint[{a}]" for a in range(4)]
                    + [f"gyroADC[{a}]" for a in range(3)] + [f"motor[{i}]" for i in range(4)])
        for n in range(int(dur * fs)):
            t = n / fs
            thr, sp, env, fpw, kd = 1450.0, 0.0, 0.0, 35.0, 0
            if t < 2:
                thr = 1000 + 225 * t
            elif 6.5 <= t < 11.5 and (t - 6.5) % 1.0 < 0.25:
                sp = 500.0 if int(t - 6.5) % 2 == 0 else -500.0
            elif 12.3 <= t < 13.5:
                thr = 2000.0
            elif 14 <= t < 22:
                kd = int((t - 14) // 3)
                u = (t - 14) - 3 * kd
                thr = 1000.0 if u < 1.2 else (1700.0 if u < 2.0 else 1450.0)
                env = 0 if u < 0.4 else (min(1, (u - 0.4) / 0.8) if u < 1.5 else math.exp(-(u - 1.5) / 0.2))
                fpw = dive_f[kd]
            elif t >= 24.5:
                thr = 1450 - 300 * (t - 24.5)
            acc = wn * wn * (sp - x) - 2 * zeta * wn * v              # second-order rate response
            v += acc / fs
            x += v / fs
            burst = pw_amp * dive_amp[kd] * env
            g0 = x + burst * math.sin(2 * math.pi * fpw * t) + rnd.gauss(0, noise)
            g1 = burst * math.sin(2 * math.pi * fpw * 1.07 * t + 1.3) + rnd.gauss(0, noise)
            base = punch_top if thr > 1900 else 8 + 0.085 * (thr - 1000)
            mot = []
            for s in (-1, -1, 1, 1):                                # roll signs of mixerQuadX
                p = base + s * 0.015 * (sp - g0) + rnd.gauss(0, 1.0)
                mot.append(int(round(lo + max(0.0, min(100.0, p)) / 100 * (hi - lo))))
            wr.writerow([n, int(t * 1e6), int(thr), round(sp), 0, 0, int(thr)] + [round(g0), round(g1), 0] + mot)


def demo():
    d = tempfile.mkdtemp(prefix="bfab_")
    gen = lambda name, arm, seed, slot=0, drift=0.0: (make_flight(os.path.join(d, name), arm, seed, slot, drift),
                                                     os.path.join(d, name))[1]
    met = lambda p: flight_metrics(read_csv(p), 158, 2047)
    print("Synthetic truth: B = propwash x0.85 (-15 %), gyro noise x1.06; flight-to-flight scatter as in real sessions")
    order = "ABBAABBAAB"
    sess = [(arm, met(gen(f"S1_{k:02d}{arm}.csv", arm, 100 + k, k, 0.03))) for k, arm in enumerate(order)]
    c = sess[0][1]["_count"]
    print(f"segments found in flight 1: hover {c[0]}, roll manoeuvres {c[1]}, dives {c[2]}, punch-outs {c[3]}")
    print("session 1, order " + order + ", wind rising +3 % propwash per flight:")
    print("  propwash per flight: " + "  ".join(f"{a}{k + 1} {m['propwash']:.2f}" for k, (a, m) in enumerate(sess)))
    report("1 flight per arm (A1, B2)", [sess[0][1]], [sess[1][1]], "propwash")
    report("5 flights per arm, ABBA order", [m for a, m in sess if a == "A"], [m for a, m in sess if a == "B"], "propwash")
    blk = [(arm, met(gen(f"S2_{k:02d}{arm}.csv", arm, 200 + k, k, 0.03))) for k, arm in enumerate("AAAAABBBBB")]
    report("5 flights per arm, blocked AAAAA BBBBB, same wind drift", [m for a, m in blk if a == "A"],
           [m for a, m in blk if a == "B"], "propwash")
    print("== power: draws from pools of 30 flights per arm (no drift), 400 draws with replacement per n, target propwash")
    pools = {arm: [met(gen(f"P_{arm}{k:02d}.csv", arm[0], 1000 * (i + 1) + k))["propwash"] for k in range(30)]
             for i, arm in enumerate(("A", "B", "A2"))}
    cv = statistics.stdev(pools["A"]) / statistics.fmean(pools["A"]) * 100
    print(f"  flight-to-flight CV of propwash in pool A: {cv:.1f} %")
    rnd = random.Random(42)
    print("  n/arm  B vs A: detected  median effect  5..95 % of estimates   A vs A2 (no effect): false alarm")
    for n in range(1, 9):
        det = fa = 0
        est = []
        for _ in range(400):
            a, b, a2 = (rnd.choices(pools[k], k=n) for k in ("A", "B", "A2"))
            r = compare(a, b)
            est.append(r["rel"])
            det += verdict(r, True) == "B better"
            fa += verdict(compare(a, a2), True) != "within noise" and n > 1
        est.sort()
        print(f"  {n:5d}  {det / 4:16.1f} % {statistics.median(est):+12.1f} % {est[20]:+9.1f} .. {est[379]:+6.1f} %"
              f" {fa / 4:27.1f} %")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a", nargs="*", default=[])
    ap.add_argument("--b", nargs="*", default=[])
    ap.add_argument("--target", default="propwash", choices=list(LOWER_IS_BETTER))
    ap.add_argument("--motor-range", default="158,2047", help="log header line motorOutput: low,high")
    ap.add_argument("--hires", action="store_true", help="blackbox_high_resolution = ON: rcCommand, setpoint, gyro x10")
    ap.add_argument("--demo", action="store_true")
    o = ap.parse_args()
    if o.demo or not (o.a and o.b):
        demo()
        sys.exit()
    lo, hi = (float(v) for v in o.motor_range.split(","))
    sc = 10.0 if o.hires else 1.0
    A = [flight_metrics(read_csv(p, sc), lo, hi) for p in o.a]
    B = [flight_metrics(read_csv(p, sc), lo, hi) for p in o.b]
    for name, S, files in (("A", A, o.a), ("B", B, o.b)):
        for m, p in zip(S, files):
            print(f"{name} {os.path.basename(p)}: " + "  ".join(f"{k} {m[k]:.2f}" for k in LOWER_IS_BETTER)
                  + f"  segments h/m/d/p {m['_count']}")
    report("own logs", A, B, o.target)
```

### Step 3. A run on synthetic data
`python3 ab_compare.py --demo`. The generator is deterministic (`random.Random(seed)`), the run takes about a minute, and the output must match to the hundredths:

```text
Synthetic truth: B = propwash x0.85 (-15 %), gyro noise x1.06; flight-to-flight scatter as in real sessions
segments found in flight 1: hover 1, roll manoeuvres 5, dives 3, punch-outs 1
session 1, order ABBAABBAAB, wind rising +3 % propwash per flight:
  propwash per flight: A1 18.20  B2 15.80  B3 16.04  A4 20.66  A5 22.48  B6 17.99  B7 18.25  A8 22.58  A9 24.50  B10 18.10
== 1 flight per arm (A1, B2): 1 flight(s) A, 1 flight(s) B, target metric 'propwash'
  metric      A mean   B mean     B-A    s_p |d|/SE      p  verdict
  noise         1.42     1.35   -5.4%    nan    nan  1.000  no spread estimate (1 flight per arm)
  track       108.43   106.74   -1.6%    nan    nan  1.000  no spread estimate (1 flight per arm)
  overshoot    12.00     8.20  -31.7%    nan    nan  1.000  no spread estimate (1 flight per arm)
  propwash     18.20    15.80  -13.2%    nan    nan  1.000  no spread estimate (1 flight per arm)
  headroom      5.29     3.55  -33.0%    nan    nan  1.000  no spread estimate (1 flight per arm)
  DECISION: keep A, effect on propwash not shown; fly more pairs or drop the change
== 5 flights per arm, ABBA order: 5 flight(s) A, 5 flight(s) B, target metric 'propwash'
  metric      A mean   B mean     B-A    s_p |d|/SE      p  verdict
  noise         1.37     1.35   -1.6%   0.12   0.29  0.778  within noise
  track       107.13   105.81   -1.2%   2.48   0.84  0.460  within noise
  overshoot    11.56    10.24  -11.4%   1.87   1.11  0.294  within noise
  propwash     21.68    17.23  -20.5%   1.88   3.73  0.016  B better
  headroom      3.90     4.54  +16.6%   1.17   0.88  0.460  within noise
  DECISION: accept B (propwash -20.5 %, no side metric worse beyond noise)
== 5 flights per arm, blocked AAAAA BBBBB, same wind drift: 5 flight(s) A, 5 flight(s) B, target metric 'propwash'
  metric      A mean   B mean     B-A    s_p |d|/SE      p  verdict
  noise         1.30     1.42   +8.8%   0.09   1.98  0.079  within noise
  track       105.03   105.91   +0.8%   1.54   0.90  0.444  within noise
  overshoot    12.68    11.84   -6.6%   1.49   0.89  0.413  within noise
  propwash     19.04    18.45   -3.1%   1.66   0.56  0.595  within noise
  headroom      4.30     3.78  -12.1%   0.80   1.03  0.333  within noise
  DECISION: keep A, effect on propwash not shown; fly more pairs or drop the change
== power: draws from pools of 30 flights per arm (no drift), 400 draws with replacement per n, target propwash
  flight-to-flight CV of propwash in pool A: 7.9 %
  n/arm  B vs A: detected  median effect  5..95 % of estimates   A vs A2 (no effect): false alarm
      1               0.0 %        -16.7 %     -29.4 ..   -3.4 %                         0.0 %
      2               0.0 %        -16.3 %     -26.5 ..   -7.1 %                         0.0 %
      3               0.0 %        -16.2 %     -24.3 ..   -7.9 %                         0.0 %
      4              67.2 %        -16.2 %     -23.0 ..   -8.9 %                         3.2 %
      5              92.5 %        -16.2 %     -22.3 ..  -10.1 %                         5.0 %
      6              98.8 %        -17.1 %     -22.8 ..  -11.2 %                         5.2 %
      7              99.8 %        -16.6 %     -22.6 ..  -11.4 %                         8.5 %
      8             100.0 %        -16.7 %     -21.0 ..  -11.6 %                         7.8 %
```

The analysis. **One pair**: propwash −13.2 %, which looks like the truth, but next to it are overshoot −31.7 % and headroom −33.0 %, which B does not change. Without the spread within an arm these numbers cannot be told apart, p = 1.000. **ABBA, 5 + 5**: propwash −20.5 %, |Δ|/SE = 3.73, p = 0.016, B is accepted. The +6 % of noise built into B stayed “within noise”, and it is covered by the rule about motor temperature. −20.5 % against a truth of −15 % is the ordinary spread of a series: at n = 5, 90 % of the estimates lie between −22.3 and −10.1 %. **Blocks** with the same wind: −3.1 %, p = 0.595, the effect is lost — the drift is +6 % for A and +21 % for B. **Power**: at n ≤ 3 there are 0 % detections (the limit of the test), at n = 4 — 67 %, at n = 5 — 92.5 %. The false alarm rate of A against A2 is about 5 % (3–8.5 %) — the price of the p < 0.05 threshold. Even pools of 30 flights give a median of −16…−17 %, not exactly −15 %.

### Step 4. Your own logs
{{lesson:bf-blackbox|Recording a log, the rate, the `blackbox_disable_*` fields and decoding to CSV are covered there: without the `setpoint` and `motor` fields the script has nothing to compute.}}

`blackbox_decode LOG00001.BFL` gives `LOG00001.01.csv` and `LOG00001.01.event`. If `grep -a blackbox_high_resolution LOG00001.BFL` = 1, run with `--hires`; the motor range — `grep -a motorOutput LOG00001.BFL` → `--motor-range`. Separate flights: `python3 ab_compare.py --a A1.csv A4.csv A5.csv A8.csv A9.csv --b B2.csv B3.csv B6.csv B7.csv B10.csv`. A switch in one flight: the event time from `.event` minus the first `time (us)` of the CSV, divided by 10⁶, is seconds from the start of the log, and you pass them as windows: `--a LOG.01.csv@40-75 LOG.01.csv@110-145 --b LOG.01.csv@75-110 …`; every window holds the whole program. A `segments h/m/d/p` line with a zero means that a maneuver was not recognized and its metric will be `nan`.

### Moving to real hardware
**At home, props off.** `diff all` to a file with the date; the mechanics (`bf-motor-balance`) and the spectrum (`bf-filters`) are in order; the hypothesis, the metric, the threshold and the plan n are written in the log. Separate flights: B in the neighboring PID profile, `profile_name` “A” and “B”, the profile name in the OSD. A switch: the two `adjrange` slots from the theory, endpoints of 1000/2000 in the Receiver tab, `get d_roll` in both positions (40 and 46), `debug_mode = D_MIN`. A log at no less than 1 kHz, the flash erased.

**The field.** Wind up to 5 m/s, one batch of batteries, one set of props. The order ABBA ABBA AB, 5 flights per arm, the same pause (5 min), landing at the same voltage (for example, 3.6 V per cell under load, a course guideline). Before takeoff — the profile in the OSD (if a helper sets it, the pilot does not look). After every flight — a line in the log:

| No. | Time | Arm | Profile / value | Battery no. and resting V after | Wind, m/s | Motor T, °C | Pilot rating 1–5 | Log | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 10:05 | A | profile 0 “A” | 3, 3.78 | 2–3 | 41 | 3 | LOG00001 | — |
| 2 | 10:12 | B | profile 1 “B” | 4, 3.77 | 3 | 44 | 4 | LOG00002 | a gust on the 2nd descent |

**Abort the flight and land if:** oscillations or “ringing” appeared that A did not have; the OSD shows the wrong profile or the wrong value; after landing you cannot keep a finger on the motors for 5 s (`bf-pid`) — then B is rejected without statistics; you hit something or changed a prop — start the session over with A. After the session: the `adjrange` slots are removed, the accepted value is entered with `set`, and the “after” `diff all` and the script's verdict are in the log.

Self-check: the lab is complete when:
- **Calculation (the main path):** the minimum p for n = 3, 4, 5 is 0.100, 0.0286, 0.0079 (±0.0001); the plan for CV 8 %, Δ 15 % is 5 flights.
- **Calculation:** the `--demo` output matched the output above: one pair — p = 1.000 for all the metrics; ABBA — propwash −20.5 %, |Δ|/SE = 3.73, p = 0.016, `accept B`; blocks — −3.1 %, p = 0.595, `keep A`; the power at n = 4 and 5 — 67.2 % and 92.5 %.
- **Calculation:** you wrote down in your own words why the blocks lost the effect and ABBA did not, and compared it with the reference below.
- **Hardware:** a session of 5 + 5 flights in ABBA order with the log filled in. The script found all the segments in every flight of your logs (h/m/d/p ≥ 1/1/1/1), the verdict is written down together with |Δ|/SE and p, and the motor temperature in B is no higher than in A.

**Reference for self-check.** In the blocks, arm B flew later and got 15 % more propwash from the wind than A (+21 % against +6 %) — almost exactly as much as the effect (1.21/1.06 = +14.2 %, 0.85 · 1.142 = 0.97). In ABBA the drift of the arms is +13.2 % and +13.8 %, and the effect remains. Typical mistakes. “−13 % on one pair, so it works” — without the spread this cannot be told from the −33 % in motor headroom, which B does not change. “Three flights, p = 0.10, almost significant” — at n = 3 there is nothing below 0.10; that is the limit of the test. “The noise did not grow, since it is within noise” — +6 % is built into B, and five pairs simply do not see it.

## diagnostics
- **Symptom:** yesterday's “best” profile is no better today
  - Possible cause: the decision was made on one pair of flights, and the difference was noise or wind.
  - What to do: an A/A test to estimate the metric noise, then 4–5 flights per arm in ABBA order.
- **Symptom:** the script prints `nan` for one metric
  - Possible cause: a maneuver did not fit the rule: a descent shorter than 0.5 s, snaps weaker than 200 °/s, a punch-out below 1900, a hover shorter than 2 s; or the window `@t0-t1` cut it off.
  - What you see in the log: a zero in place of the maneuver in the `segments h/m/d/p` line.
  - What to do: fly the program with a margin in duration, check the windows; with `blackbox_high_resolution = 1` run with `--hires`.
- **Symptom:** the switch gives a `d_roll` of 41 instead of 40 (position A) or 45 instead of 46 (position B)
  - Possible cause: the channel endpoints do not reach 1000/2000 µs, and C division drops the fractional part.
  - What to do: endpoints in the radio out to 988–1000 and 2000–2012 µs, a check with `get d_roll` in both positions.
- **Symptom:** the PID profile cannot be switched from a switch in flight
  - Possible cause: 4.5 and 2025.12 have no such function; in select mode `adjrange` can do only the rate, OSD and LED profiles, HORIZON_STRENGTH and PID_AUDIO (in 2025.12 also LED_DIMMER).
  - What to do: separate flights with the profile chosen on the ground, or an absolute slot for one gain.
- **Symptom:** the profile changes by itself after the battery is changed
  - Possible cause: `auto_profile_cell_count` ≠ 0 in one of the profiles.
  - What to do: 0 in all the profiles for the duration of the experiment, a check of the profile name in the OSD before takeoff.
- **Symptom:** the effect is there on one aircraft and absent on a second identical one
  - Possible cause: the aircraft differ in mechanics or props more than the profiles do.
  - What to do: a crossover design, the effect within each aircraft; motor balance from the log (`bf-motor-balance`).

## checklist
- The mechanics and the filters are in order before the experiment
- The hypothesis, the target metric, the threshold and the plan n are written down before the flights
- B differs from A in one parameter; `diff all` before and after
- One flight program, one set of props, one batch of batteries, wind up to 5 m/s
- The order ABA or ABBA, not blocks; no fewer than 4 flights per arm
- The profile or the value is checked in the OSD before every takeoff
- The verdict: |Δ|/SE > 2 and p < 0.05 on the target metric, the side metrics are no worse, the motors are no hotter
- The `adjrange` slots are removed after the experiment, and the accepted value is entered with `set`

## references
- Betaflight `fc/rc_adjustments.c`, 4.5.3 (defaultAdjustmentConfigs, the RATE_PROFILE select mode, the absolute mode, the adjustment event) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/fc/rc_adjustments.c | primary | A
- Betaflight `fc/rc_adjustments.h`, 4.5.3 (the function list, no PID-profile function, 30 slots) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/fc/rc_adjustments.h | primary | A
- Betaflight `cli/cli.c`, 4.5.3 (adjrange, diff, dump, profile, rateprofile) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/cli/cli.c | primary | A
- Betaflight `cli/settings.c`, 4.5.3 (blackbox_*, debug_mode, vbat_sag_compensation, d_roll, d_min_roll, the profile names) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/cli/settings.c | primary | A
- Betaflight `blackbox/blackbox.c`, 4.5.3 (the setpoint, gyroADC, motor fields; the rollPID, d_min headers) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/blackbox/blackbox.c | primary | A
- Betaflight `fc/rc_controls.c`, 4.5.3 (PID profile selection with the sticks on the ground) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/fc/rc_controls.c | primary | A
- Betaflight `fc/rc_modes.h`, 4.5.3 (the mode list: there is no PID-profile mode) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/fc/rc_modes.h | primary | A
- Betaflight `msp/msp.c`, 4.5.3 (MSP_SELECT_SETTING ignores the PID profile while armed; MSP_SET_PID without an arm check; MSP_COPY_PROFILE) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/msp/msp.c | primary | A
- Betaflight `fc/rc_adjustments.c`, 2025.12-maintenance (the same numbers 12, 17, 20; still no PID profile) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12-maintenance/src/main/fc/rc_adjustments.c | primary | A
- blackbox-tools `blackbox_decode.c` (the .event file, the JSON of the Inflight adjustment event) | https://raw.githubusercontent.com/betaflight/blackbox-tools/master/src/blackbox_decode.c | primary | A
- PID Tuning Guide — Betaflight Documentation | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/guides/current/PID-Tuning-Guide.md | primary | B
- SciPy `stats/_resampling.py`, permutation_test (exact enumeration of the splits, two-sided p) | https://raw.githubusercontent.com/scipy/scipy/main/scipy/stats/_resampling.py | secondary | B

## notes
The thresholds |Δ|/SE > 2, p < 0.05, 80 %, the maneuver segmentation rules, the 100–250 and 20–70 Hz bands, the 3 s trim, the landing voltage and the pause are course guidelines; the firmware has none of them. n ≈ 16 · (CV/Δ)² is a normal approximation. The numbers of the practice were obtained on synthetic data, and a propwash CV of about 8 % is an assumption of the model; your own spread is measured with an A/A test. The log lines are an example of how to fill it in, not session data.
