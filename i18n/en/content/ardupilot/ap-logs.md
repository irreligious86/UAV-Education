---
id: ap-logs
title: "ArduPilot logs: analyzing a flight"
level: L3
readingTime: 30 min
firmware: ArduPilot 4.7 (checked against 4.7.3)
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
source_hash: 221a6f84498a
---

## summary
ArduPilot writes a binary DataFlash log (`.bin`) to the SD card with hundreds of message types: attitude, altitude, motors, battery, EKF, errors. It is the black box that answers "why" after any strange flight. This module gives you an order of analysis, from vibration to errors, with the exact message and field names, the limits from the documentation, and a Python script for your own plots.

## theory
### Two kinds of logs
- **DataFlash** (`.bin`): on board, high rate, everything. This is the main tool.
- **Telemetry log** (`.tlog`): what the GCS saw over the radio. Lower rate and with gaps, but it exists even if the SD card burned together with the vehicle.

The `LOG_BITMASK` parameter sets what is logged; `LOG_DISARMED` enables logging before arming (useful for analyzing pre-arm problems).

### Messages to start with
- `VIBE`: vibration, with `VibeX`, `VibeY`, `VibeZ` (m/s²) and `Clip`, the accelerometer clipping counter. The general limits in the ArduPilot documentation: below 30 is normal, above 60 almost certainly means altitude and position problems; on large props the goal is stricter, below 15 (see ap-heavy). Clipping should be zero.
- `ATT`: `DesRoll` against `Roll`, `DesPitch` against `Pitch`, that is, how well the vehicle keeps up with the desired attitude. A sharp divergence means a mechanical problem or a lack of thrust.
- `CTUN`: altitude control, with `ThO` (throttle output), `ThH` (hover throttle estimate), `DAlt`/`Alt` (desired and actual altitude), `BAlt` (baro).
- `BAT`: `Volt`, `Curr`, `CurrTot`, `Res` (the estimated internal resistance). Sag under load and actual consumption.
- `RCIN`: the transmitter channels `C1…C14`, that is, what the pilot did.
- `MODE`: mode changes and the reason, `Rsn`.
- `ERR`: errors, with `Subsys` and `ECode`. For example, subsystem 2 (radio) with code 2 means no receiver frames for longer than `RC_FS_TIMEOUT` (1 s by default); 11 is a GPS glitch; 16 is a bad EKF variance; 17 is the EKF failsafe; 29 is vibration compensation.
- `MSG`: text messages, including pre-arm ones.
- `GPS`: `NSats`, `HDop`. An HDOP below 1.5 is good, above 2.0 is suspicious; fewer than 12 satellites is poor.
- `XKF1…XKF4`: the internals of EKF3 per core, estimates and variances (`XKF4`: `SV`, `SP`, `SH`, `SM` for velocity, position, height, compass).
- `POWR`: the board `Vcc`. Fluctuations of more than 0.1–0.15 V hint at power problems.

### Order of analysis
1. **Does the log end abruptly?** A log that ends in the air means a power loss or a reboot.
2. **Vibration** (`VIBE`). Nothing else means anything while it is high.
3. **Errors** (`ERR`, `MSG`): what triggered and when.
4. **Modes** (`MODE`): who changed the mode, the pilot or a failsafe.
5. **Control** (`ATT`, `CTUN`): whether the vehicle kept up with the commands.
6. **Power** (`BAT`, `POWR`): sags and whether they coincide with events.
7. **Navigation** (`GPS`, `XKF4`): position quality and variances at the moment of the problem.

### Tools
Mission Planner (Review a Log), MAVExplorer from the MAVProxy package (plots by field name, for example `graph ATT.Roll ATT.DesRoll`), UAV Log Viewer in the browser. For automation use `pymavlink.DFReader`, which reads a `.bin` directly in Python. ArduPilot WebTools (firmware.ardupilot.org/Tools/WebTools, the "ArduPilot WebTools" wiki page) is a set of browser tools, and the log is not uploaded anywhere: Hardware Report (which sensors and firmware were on board, health, sensor offsets, from a log or a `.param` file), Filter Review (the gyro spectrum from batch sampling or raw IMU logging, with trial application of filters), Filter Tool (Bode plots of the filters from a `.param` file), PID Review (step response from a log), MAGFit (compass calibration from a log, see `ap-sensors`). How to choose: "what was on board" is Hardware Report; "what to filter with" is Filter Review; "how the rate loop is tuned" is PID Review.

### Worked example: analyzing "a 3 m altitude drop in Loiter"
1. `VIBE.VibeZ` is 12 m/s², `Clip` is 0 → not vibration.
2. `ERR`/`MSG`: nothing.
3. `CTUN`: `DAlt` is a constant 20 m, `Alt` drops to 17 m, and `BAlt` drops with it → a real drop, not an estimation artifact.
4. `CTUN.ThO` at that moment is 0.78 (0.42 before), `BAT.Volt` goes 21.1 → 18.9 V, `BAT.Curr` 60 → 95 A: the throttle hit the ceiling on a sagging battery.
5. `RCIN.C3`: the pilot did not touch the throttle; `MODE` has no changes.
Conclusion: a lack of thrust with voltage sag on an old battery (`BAT.Res` of 0.09 Ω is high): replace the battery, set `MOT_BAT_VOLT_MIN/MAX` for compensation, raise the `BATT_LOW_VOLT` threshold. The method matters more than the conclusion: every step is a specific field.

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
`mavlogdump.py --types ATT,VIBE --format csv flight.bin` is a quick export to CSV with no code; in `MAVExplorer`: `graph ATT.Roll ATT.DesRoll`, `fft` for batch sampling spectra (`ISBH/ISBD`), `map` for the track. Step-response metrics and spectra are in the "Python for data" module.

### What to log in LOG_BITMASK
The default (Copter: `LOG_BITMASK = 180222`) is enough for analyzing a flight, and `PID` (bit 12, the `PIDR/PIDP/PIDY` messages with P/I/D/FF per axis) is already in it, but at 10 Hz. For tuning add bit 0, Fast Attitude (+1: `ANG`, `RATE`, and `PIDx` at the loop rate), and `IMU_RAW` or batch sampling (`INS_LOG_BAT_MASK`) while you set up the filters; the log grows several times over, so turn them off afterwards. `LOG_FILE_DSRMROT` starts a new file on every disarm; `LOG_DISARMED = 1` is for ground measurements (noise, GPS); turn it off afterwards or the SD card fills up.

The `LOG_BITMASK` bits in ArduCopter 4.7.2 (`ArduCopter/defines.h`; the default is `DEFAULT_LOG_BITMASK` in `ArduCopter/config.h`):

| Bit | Value | Name in the GCS | In 180222 | What it gives you |
|---|---|---|---|---|
| 0 | 1 | Fast Attitude | no | `ANG`, `RATE`, `PIDx` at the loop rate instead of 10 Hz |
| 1 | 2 | Medium Attitude | yes | `ANG` and `RATE` at 10 Hz |
| 2 | 4 | GPS | yes | `GPS`, `GPA` |
| 3 | 8 | System Performance | yes | `PM`: load and loop rate |
| 4 | 16 | Control Tuning | yes | `CTUN`: throttle, altitudes, `ThH` |
| 5 | 32 | Navigation Tuning | yes | `PSCN/PSCE/PSCD`: the position controller |
| 6 | 64 | RC input | yes | `RCIN`, `RSSI` |
| 7 | 128 | IMU | yes | `IMU` at 25 Hz, `VIBE`, `BARO` |
| 8 | 256 | Mission Commands | yes | `CMD` |
| 9 | 512 | Battery Monitor | yes | `BAT`, `POWR` |
| 10 | 1024 | RC output | yes | `RCOU` |
| 11 | 2048 | Optical Flow | yes | `OF` |
| 12 | 4096 | PID | yes | `PIDR/PIDP/PIDY/PIDA` (10 Hz; at the loop rate with bit 0) |
| 13 | 8192 | Compass | yes | `MAG` |
| 15 | 32768 | Camera | yes | `CAM`, `TRIG` |
| 17 | 131072 | Motors | yes | `MOTB`: voltage compensation and motor limits |
| 18 | 262144 | Fast IMU | no | `IMU` at the loop rate |
| 19 | 524288 | Raw IMU | no | `GYR`, `ACC`: every sensor sample (pre-filter by default; post-filter with `INS_RAW_LOG_OPT`) |
| 20 | 1048576 | Video Stabilization | no | data for video stabilization |
| 21 | 2097152 | Fast harmonic notch logging | no | notch frequencies at the loop rate |

Breaking down the default: 180222 = 131072 + 32768 + 8192 + 4096 + 2048 + 1024 + 512 + 256 + 128 + 64 + 32 + 16 + 8 + 4 + 2, which is bits 1–13, 15, and 17 (bit 14 is obsolete and unused). For tuning: 180222 + 1 = 180223 (Fast Attitude); for choosing filters also set `INS_LOG_BAT_MASK = 1` (batch sampling) or bit 19. To check yourself, subtract powers of two from the value starting with the largest: every power you subtract is an enabled bit.

`LOG_DISARMED` (default 0): 1 logs at all times, including on the ground; 2 logs while disarmed, but not when a USB connection is detected (connecting to download logs or change parameters does not generate extra files); 3 logs while disarmed, and a log in which the vehicle never armed is discarded on the next boot (for the filesystem backend). For analyzing startup and pre-arm problems use 3: the log of the flight you need stays, and "sat on the bench" logs do not pile up. Bits 0 and 19 grow the log several times over; go back to 180222 after tuning.

{{diagram:log-triage|Where to start analyzing a log: the symptom determines the first message, which is VIBE, BAT/POWR, XKF4/GPS, RATE/ATT, or MODE/ERR/EV.}}

### AI log analyzers: where they help and where they get it wrong
By November 2026 discuss.ardupilot.org had a list of automated `.bin` analyzers; the first post listed 16 of them as of November 22, 2026 (the "List of automated ArduPilot flight log analysis software" topic, May to October 2026). They fall into three types by design:

| Type | Examples from the list | What it does well | Where it gets it wrong |
|---|---|---|---|
| Rules (deterministic checks) | Flight Log Analyzer AYNA, with 44 checks across 7 systems and no LLM; Skybrush Log Analyzer, for shows | one log → always the same answer, and you can read the thresholds | it sees only what was built in; the thresholds may come from a different version |
| Rules + an LLM for the explanation | the analyzer in ArduPilot Methodic Configurator (GSoC 2026): the engine makes the diagnosis and the LLM only restates it | readable text on top of verifiable facts | the restatement can distort the engine's fact |
| An LLM or agent reads the log itself | chatbots, MCP servers (ardupilot-mcp), "AI" tabs in web tools | drafting a checklist, finding the right field, writing a pymavlink script | it confuses parameter versions, invents fields and thresholds, and skips the order of analysis |

Experienced members of the ArduPilot forum judge the third type harshly in that same topic: one writes that he has not yet seen a single reliable log analysis from an AI tool. The accuracy of specific tools has not been measured independently; it is **not verified**.

**Procedure for checking AI output.** Every conclusion goes through five checks; if it fails even one, the conclusion is discarded.

1. **A reference to a fact.** The conclusion names the message and field, the time, and the value (`VIBE.VibeZ = 45 m/s² at 312 s`). "Looks like vibration" with no field is not a conclusion.
2. **Recalculation.** You get the same value yourself: `graph VIBE.VibeZ` in MAVExplorer or the `df_of` function from the Python section. If they differ, the conclusion is discarded.
3. **Parameter names.** You look up every suggested parameter in the `PARM` messages of the same log: they hold the names and values of the firmware the vehicle flew on. If the name is not in `PARM`, it comes from a different version (for example `ARMING_CHECK` instead of `ARMING_SKIPCHK` in 4.7, see `ap-intro`).
4. **Thresholds.** You check the numbers against the documentation: vibration 30/60 m/s², HDOP 1.5/2.0, as in the "Messages to start with" section.
5. **Order.** A conclusion about the EKF or PID with high `VIBE` or `Clip` > 0 is not accepted: mechanics first.

Apply suggested changes one at a time, with a log before and after. Never load an AI-generated parameter list wholesale. One more thing: the log contains your home coordinates and route, so before you hand a `.bin` to a cloud service, decide whether you are willing to share them.

### Place in the system

- **Receives:** messages from every subsystem: `XKF1…XKF4` from the EKF (`ap-ekf`), `BAT` from the battery monitor calibrated in `ap-setup-scratch`, `RATE` and `PIDx` from the control loops (`ap-tuning`); `LOG_BITMASK` sets what is logged and how often.
- **Provides:** facts for the analysis: who changed the mode, whether the throttle saturated, whether the power sagged; data for your own metrics and spectra (`data-python`); the "before/after" criterion for tuning (`ap-tuning`) and for the test log (`ap-safety-fs`).
- **If you get it wrong here:** you started the analysis with navigation and skipped `VIBE` → you are fixing GPS and the EKF when the cause is mechanical (`f-frame-mech`). You did not enable batch sampling and Fast Attitude before tuning → `PIDx` at 10 Hz and no spectrum → the notch and D are set blind (`ap-tuning`).

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

Run it: `python vibe_report.py 00000012.BIN`. A median above 30 or nonzero clipping means mechanics first, then everything else.

### Lab
1. Fly a mission in SITL with a motor failure on a switch.
2. Download the log (in SITL, the `logs/` folder).
3. Find the moment of the failure from `RCIN` (the switch) and see how `DesRoll`/`Roll` diverged and the motor outputs (`RCOU`) rose.
4. Write yourself a five-line analysis: what happened, when, how the vehicle coped, which parameters are worth changing.

### A real log
Repeat the same with a log of a real hover: vibration, hover throttle (`CTUN.ThH`), battery sag. Save the log and the analysis in the drone's folder with the date.

### How to set up a motor failure in SITL
The failure is set with simulator parameters: `SIM_ENGINE_FAIL` is the motor mask (bit 0 is output 1), `SIM_ENGINE_MUL` is the multiplier applied to their thrust. On a quadcopter a complete failure (`SIM_ENGINE_MUL = 0`) means a crash, so for a training analysis use a partial failure (0.5–0.6) or a hexa or octa frame, which survives the complete failure of one motor. You can see the moment of the failure in the log from the `PARM` record with the new parameter value, or from the switch in `RCIN` if the failure is tied to a transmitter channel.

### What you should get and what to record
- **Script.** In SITL the vibration is low (a few m/s²) and there is no clipping, because there are no mechanics. On a real vehicle you need a median below 30 m/s² and zero clipping: only then do you analyze the rest. Record the median and p95 for the three axes.
- **ERR.** Decode every record with the subsystem list from the theory: time, subsystem, code, what it means.
- **Failure.** A fraction of a second after it, `ATT.DesRoll` and `ATT.Roll` diverge, and the motor outputs in `RCOU` spread apart: the remaining motors run with margin, and the failed one goes to maximum trying to produce thrust. Record the time to stabilization and the maximum roll deviation.
- **A five-line analysis, example:** "12.3 s: failure of motor 1 (×0.6). Roll deviated to 14° and stabilized in 1.2 s. The outputs of the remaining motors rose to 75%, so there is thrust margin. Vibration is normal (median 4 m/s²), no clipping. Recommendation: the margin is sufficient for this mass, no change needed."
- **A real log.** Compare the hover throttle `CTUN.ThH` with `MOT_THST_HOVER`; the battery sag under throttle is visible in `BAT`.

Self-check: the lab is done when the DFReader script prints the `VIBE` median and p95 for the three axes and the clipping (in SITL, a few m/s² and 0 events), every `ERR` record is decoded with the subsystem list from the theory (time, subsystem, code, what it means), the moment of the failure is found from `PARM`/`RCIN` with the divergence of `ATT.DesRoll`/`ATT.Roll` and the spread of `RCOU` visible right after it, and the five-line analysis has the same five items as the example above (time and kind of failure; maximum roll and time to stabilization; outputs of the remaining motors; vibration and clipping; recommendation) and is saved next to the log.

**Reference for the self-check.** A correct result: every statement in the analysis is backed by a number from the log, as in the example. Typical wrong results: (1) in SITL the vibration median is tens of m/s² or the clipping is nonzero: there are no mechanics in the simulator, so the script is reading the wrong field or the wrong IMU; (2) after the failure the quadcopter crashed and there is nothing to analyze, because a complete failure was set (`SIM_ENGINE_MUL = 0`): use 0.5–0.6 or a hexa or octa frame.

## diagnostics
- **Symptom:** the log ends in the air
  - Possible cause: loss of board power.
  - What to do: `POWR.Vcc` before the end of the log, the soldering of the power connectors, the BEC.
- **Symptom:** `VIBE` is high and `Clip` is increasing
  - Possible cause: unbalanced props or motors, a hard-mounted FC.
  - What to do: balancing, dampers, a frame check, before any filters.
- **Symptom:** `DesRoll` and `Roll` diverge, one motor is at maximum in `RCOU`
  - Possible cause: a failed or weak motor or ESC, overloading.
  - What to do: check the motor, the propeller, the ESC; compare the motor outputs in hover.
- **Symptom:** `ERR` 16/17 before a crash
  - Possible cause: bad EKF variances from the compass, GPS, or vibration.
  - What to do: `XKF4` at that moment, then find the cause as in the previous module.

## references
- Diagnosing problems using Logs — ArduPilot Copter | https://ardupilot.org/copter/docs/common-diagnosing-problems-using-logs.html | primary | A
- Downloading and Analyzing Data Logs — ArduPilot | https://ardupilot.org/copter/docs/common-downloading-and-analyzing-data-logs-in-mission-planner.html | primary | A
- Log message reference (LogStructure.h, GitHub) | https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_Logger/LogStructure.h | primary | A
- MAVExplorer — MAVProxy | https://ardupilot.org/dev/docs/using-mavexplorer-for-log-analysis.html | primary | A
- List of automated ArduPilot flight log analysis software — ArduPilot Discourse (May–October 2026; accessed 2026-11-22) | https://discuss.ardupilot.org/t/list-of-automated-ardupilot-flight-log-analysis-software/143635 | secondary | B

## checklist
- I know the difference between DataFlash and tlog
- I start the analysis with an abrupt log end and vibration
- I can find an `ERR` and decode the subsystem
- My DFReader script reads my log
- Logs and analyses are in the drone's folder with the date
