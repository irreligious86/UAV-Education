---
id: ap-logs
title: "ArduPilot Logs: Flight Analysis"
level: L3
readingTime: 30 min
firmware: ArduPilot 4.5+
status: published
added: 2026-11-07
tags:
  - DataFlash
  - logs
  - troubleshooting
related:
  - ap-ekf
  - bf-blackbox
next:
  - ap-lua
source: content/ardupilot/ap-logs.md
source_hash: 6184cf012fb2
---

## summary
ArduPilot writes a binary DataFlash log (`.bin`) to the SD card with hundreds of message types: attitude, altitude, motors, battery, EKF, errors. It's the black box that answers “why” after any weird flight. This module gives you an analysis order — from vibration to errors — with concrete message and field names, thresholds from the documentation, and a Python script for your own plots.

## theory
### Two kinds of logs
- **DataFlash** (`.bin`) — onboard, high rate, everything. Your main tool.
- **Telemetry log** (`.tlog`) — what the GCS saw over the radio link. Lower rate and with gaps, but it exists even if the SD card burned up along with the aircraft.

The `LOG_BITMASK` parameter sets what gets logged; `LOG_DISARMED` enables logging before arming (useful for analyzing pre-arm problems).

### Messages to start with
- `VIBE` — vibration: `VibeX`, `VibeY`, `VibeZ` (m/s²) and `Clip` — the accelerometer saturation counter. Below 30 is normal; above 60 almost certainly means altitude and position problems. Clipping should be zero.
- `ATT` — `DesRoll` vs. `Roll`, `DesPitch` vs. `Pitch`: how well the aircraft keeps up with the desired attitude. A sharp divergence means a mechanical problem or a lack of thrust.
- `CTUN` — altitude control: `ThO` (throttle output), `ThH` (hover throttle estimate), `DAlt`/`Alt` (desired and actual altitude), `BAlt` (baro).
- `BAT` — `Volt`, `Curr`, `CurrTot`, `Res` (internal resistance estimate). Voltage sag under load and real consumption.
- `RCIN` — radio channels `C1…C14`: what the pilot was doing.
- `MODE` — mode changes and the reason `Rsn`.
- `ERR` — errors: `Subsys` and `ECode`. For example, subsystem 2 (radio) with code 2 — no receiver frames for two seconds; 11 — GPS glitch; 16 — bad EKF variance; 17 — EKF failsafe; 29 — vibration compensation.
- `MSG` — text messages, including pre-arm ones.
- `GPS` — `NSats`, `HDop`: HDOP below 1.5 is good, above 2.0 is suspicious; fewer than 12 satellites is bad.
- `XKF1…XKF4` — EKF3 internals per core: estimates and variances (`XKF4`: `SV`, `SP`, `SH`, `SM` — velocity, position, height, compass).
- `POWR` — board `VCC`: fluctuations above 0.1–0.15 V hint at power problems.

### Analysis order
1. **Does the log cut off?** A log that ends in the air means power loss or a reboot.
2. **Vibration** (`VIBE`). Everything else is meaningless while it's high.
3. **Errors** (`ERR`, `MSG`): what triggered and when.
4. **Modes** (`MODE`): who changed the mode — the pilot or a failsafe.
5. **Control** (`ATT`, `CTUN`): did the aircraft keep up with commands.
6. **Power** (`BAT`, `POWR`): sags and whether they coincide with events.
7. **Navigation** (`GPS`, `XKF4`): position quality and variances at the moment of the problem.

### Tools
Mission Planner (Review a Log), MAVExplorer from the MAVProxy package (plots by field name, e.g. `graph ATT.Roll ATT.DesRoll`), UAV Log Viewer in the browser. For automation — `pymavlink.DFReader`: reads `.bin` directly in Python.

### Worked example: analyzing “a 3 m altitude drop in Loiter”
1. `VIBE.VibeZ` 12 m/s², `Clip` 0 → not vibration.
2. `ERR`/`MSG`: none.
3. `CTUN`: `DAlt` constant at 20 m, `Alt` drops to 17 m, `BAlt` at the same time → a real drop, not an estimation issue.
4. `CTUN.ThO` at that moment — 0.78 (before — 0.42), `BAT.Volt` 21.1 → 18.9 V, `BAT.Curr` 60 → 95 A: throttle hit the ceiling on a sagging battery.
5. `RCIN.C3` — the pilot didn't touch the throttle; `MODE` has no changes.
Conclusion: lack of thrust due to voltage sag on an old battery (`BAT.Res` 0.09 Ω — high): replace the battery, use `MOT_BAT_VOLT_MIN/MAX` for compensation, raise the `BATT_LOW_VOLT` threshold. The method matters more than the conclusion: every step is a specific field.

### Python for your own metrics (pymavlink)
```python
from pymavlink import mavutil
import pandas as pd
def df_of(log, msg):
    m = mavutil.mavlink_connection(log); rows = []
    while (x := m.recv_match(type=msg, blocking=False)) is not None: rows.append(x.to_dict())
    return pd.DataFrame(rows)
att = df_of("flight.bin", "ATT")
err = (att.DesRoll - att.Roll).abs()
print("roll tracking RMS deg:", err.pow(2).mean() ** 0.5, "p99:", err.quantile(0.99))
vibe = df_of("flight.bin", "VIBE"); print("VibeZ p95:", vibe.VibeZ.quantile(0.95), "clips:", vibe.Clip.max())
```
`mavlogdump.py --types ATT,VIBE --format csv flight.bin` — a quick CSV export with no code; `MAVExplorer`: `graph ATT.Roll ATT.DesRoll`, `fft` for batch-sampling spectra (`ISBH/ISBD`), `map` for the trajectory. Step-response metrics and spectra are covered in the “Python for Data” module.

### What to put in LOG_BITMASK
The default is enough for flight analysis; for tuning, add `PID` (messages `PIDR/PIDP/PIDY` with P/I/D/FF per axis) and `IMU_RAW`/batch sampling (`INS_LOG_BAT_MASK`) while you set up filters — the log grows several times over, so turn them off afterward. `LOG_FILE_DSRMROT` — a new file on every disarm; `LOG_DISARMED = 1` — for ground measurements (noise, GPS), then turn it off, otherwise the SD card fills up.

{{diagram:log-triage|Where to start analyzing a log: the symptom determines the first message — VIBE, BAT/POWR, XKF4/GPS, RATE/ATT or MODE/ERR/EV.}}

## practice
### Script: vibration and clipping from a log
```python
import sys
from pymavlink import DFReader

log = DFReader.DFReader_binary(sys.argv[1])
vibe = {"VibeX": [], "VibeY": [], "VibeZ": []}
clip_max = 0
errors = []
while True:
    m = log.recv_msg()
    if m is None:
        break
    t = m.get_type()
    if t == "VIBE" and m.IMU == 0:
        for k in vibe:
            vibe[k].append(getattr(m, k))
        clip_max = max(clip_max, m.Clip)
    elif t == "ERR":
        errors.append((m.TimeUS / 1e6, m.Subsys, m.ECode))

for k, v in vibe.items():
    v = sorted(v)
    print(f"{k}: median {v[len(v)//2]:.1f}  p95 {v[int(len(v)*0.95)]:.1f} m/s/s")
print("accel clipping events:", clip_max)
for t, sub, code in errors:
    print(f"ERR at {t:7.1f}s  subsys={sub} ecode={code}")
```

Run it: `python vibe_report.py 00000012.BIN`. A median above 30 or nonzero clipping — fix the mechanics first, then everything else.

### Lab
1. Fly a mission in SITL with a motor failure triggered by a switch.
2. Download the log (in SITL — the `logs/` folder).
3. Find the failure moment in `RCIN` (the switch) and look at how `DesRoll`/`Roll` diverged and the motor outputs rose (`RCOU`).
4. Write a five-line report: what happened, when, how the aircraft coped, which parameters are worth changing.

### Real log
Repeat the same with a log of a real hover: vibration, hover throttle (`CTUN.ThH`), battery sag. Save the log and the report in the drone's folder with the date.

### How to set up a motor failure in SITL
The failure is set with simulator parameters: `SIM_ENGINE_FAIL` — a motor mask (bit 0 — output 1), `SIM_ENGINE_MUL` — their thrust multiplier. On a quadcopter a full failure (`SIM_ENGINE_MUL = 0`) means a crash, so for a training analysis use a partial failure (0.5–0.6) or a hexa/octa frame, where a full failure of one motor is survivable. The failure moment shows up in the log as a `PARM` record with the new parameter value, or as a switch in `RCIN` if the failure is mapped to a radio channel.

### What you should get and what to write down
- **Script.** In SITL vibration is small (single-digit m/s²) and there is no clipping — there are no mechanics. On a real aircraft: median below 30 m/s² and zero clipping — only then analyze the rest. Write down the median and p95 for all three axes.
- **ERR.** Decode every record with the subsystem table from the theory: time, subsystem, code, what it means.
- **Failure.** A fraction of a second after it, `ATT.DesRoll` and `ATT.Roll` diverge, and the motor outputs in `RCOU` spread apart: the remaining motors work with margin, the failed one goes to maximum trying to produce thrust. Write down the time to stabilize and the maximum roll deviation.
- **Five-line report, example:** “12.3 s — motor 1 failure (×0.6). Roll deviated up to 14°, stabilized in 1.2 s. The outputs of the remaining motors rose to 75 %, there is thrust margin. Vibration is normal (median 4 m/s²), no clipping. Recommendation: for this weight the margin is sufficient, no changes needed.”
- **Real log.** Compare the hover throttle `CTUN.ThH` with `MOT_THST_HOVER`; battery sag under throttle shows in `BAT`.

The lab counts as done when the DFReader script prints the VIBE median and clipping, every ERR is decoded, the failure moment is found via `PARM`/`RCIN` with the response in `ATT` and `RCOU`, and the five-line report is saved next to the log.

## diagnostics
- **Symptom:** the log cuts off in the air
  - Possible cause: loss of board power.
  - What to do: `POWR.VCC` before the cutoff, soldering of the power connectors, BEC.
- **Symptom:** `VIBE` is high, `Clip` keeps growing
  - Possible cause: prop/motor imbalance, rigid FC mounting.
  - What to do: balancing, dampers, frame inspection — before any filters.
- **Symptom:** `DesRoll` and `Roll` diverge, one motor at maximum in `RCOU`
  - Possible cause: a failed or weak motor/ESC, overload.
  - What to do: check the motor, propeller, ESC; compare motor outputs in hover.
- **Symptom:** `ERR` 16/17 before a crash
  - Possible cause: bad EKF variances — compass, GPS or vibration.
  - What to do: `XKF4` at that moment, the cause per the previous module.

## references
- Diagnosing problems using Logs — ArduPilot Copter | https://ardupilot.org/copter/docs/common-diagnosing-problems-using-logs.html | primary | A
- Downloading and Analyzing Data Logs — ArduPilot | https://ardupilot.org/copter/docs/common-downloading-and-analyzing-data-logs-in-mission-planner.html | primary | A
- Log message reference (LogStructure.h, GitHub) | https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_Logger/LogStructure.h | primary | A
- MAVExplorer — MAVProxy | https://ardupilot.org/dev/docs/using-mavexplorer-for-log-analysis.html | primary | A

## checklist
- I know the difference between DataFlash and tlog
- I start analysis with log cutoffs and vibration
- I can find `ERR` and decode the subsystem
- The DFReader script reads my log
- Logs and reports live in the drone's folder with the date
