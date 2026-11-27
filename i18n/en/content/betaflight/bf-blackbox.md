---
id: bf-blackbox
title: "Blackbox: diagnostics and tuning from flight data"
level: L2
readingTime: 45 min
firmware: Betaflight 2025.12 (checked against 2025.12.5)
status: published
tags:
  - Blackbox
  - logging
  - tuning
  - diagnostics
  - PID
references:
  - title: "Blackbox flight data recorder — Betaflight Documentation"
    url: "https://betaflight.com/docs/wiki/guides/current/Black-Box-logging-and-usage"
    tier: primary
    stack: betaflight
  - title: "Blackbox logging internals"
    url: "https://www.betaflight.com/docs/development/Blackbox-Internals"
    tier: primary
    stack: betaflight
  - title: "How to Use Blackbox in Betaflight — Oscar Liang"
    url: "https://oscarliang.com/blackbox/"
    tier: secondary
    stack: betaflight
  - title: "How to Tune Filters & PID with Blackbox — Oscar Liang"
    url: "https://oscarliang.com/pid-filter-tuning-blackbox/"
    tier: secondary
    stack: betaflight
  - title: "Betaflight Blackbox Explorer"
    url: "https://github.com/betaflight/blackbox-log-viewer"
    tier: primary
    stack: betaflight
related:
  - bf-pid
  - bf-filters
  - bf-cli
  - bf-tuning-method
  - bf-motor-balance
next:
  - bf-custom
source: content/betaflight/bf-blackbox.md
source_hash: 614c270c5287
---

## summary

Blackbox is the flight data recorder in Betaflight; it can capture the state of the flight controller on every control loop iteration (up to 8 kHz). A log contains the gyro, the accelerometer, the stick signals, the PID controller terms, the motor outputs and the filter parameters. This article gives a complete picture of how to set up logging, read the graphs and use the tools (Blackbox Explorer, PIDscope) for diagnostics and tuning. After working through it you will be able to identify the noise structure of a drone, estimate filter delay, and tune PIDs and filters from objective data rather than by trial and error.

{{lesson:bf-motor-balance|The first thing worth extracting from a hover log: the balance of the four motors — center of gravity, a weak motor, a yaw offset, with a ready-made Python script.}}

## theory

### Purpose and architecture of Blackbox

Blackbox records the internal state of the flight controller at the highest possible rate so that control algorithms can be simulated offline, debugged and analyzed on data from real flights. A log is built from frames of several types:

- I frames (intra) — complete frames that can be decoded independently.
- P frames (inter) — delta frames that rely on prediction.
- G/H frames — for GPS data.
- S frames (slow) — state that changes rarely.
- E frames (event) — state transitions.

Predictors and variable-length encoding are used for compression, which makes it possible to store a large amount of data at a moderate data rate.

### What exactly is logged

Blackbox captures:
- time,
- the P/I/D values and the summed output,
- the setpoint (sticks),
- gyro and accelerometer data,
- voltage/current, RSSI,
- the commands to the ESCs,
- GPS frames (if present).

### Log format and storage devices

Logs can be written to:
- onboard flash (usually 2–16 MB),
- an SD card (preferable for long sessions),
- an external logger over a UART.

For an SD card, FAT32 and a card with low write latency are recommended.

### How the settings affect log quality

- 1 kHz — basic PID analysis;
- 2 kHz (or 1.6 kHz for the BMI270) — detailed noise/filter analysis.

If the looptime is short (a high PID rate), you may need to raise the baud rate or lower the logging rate, otherwise frames can be dropped.

### The physical meaning of the noise spectrum

- `<20 Hz` — useful dynamics;
- `20–100 Hz` — vibration/propwash/PID problems;
- `100–250 Hz` — frame resonances/play;
- `>250 Hz` — motor/prop noise and harmonics.

The goal of filtering is to suppress high-frequency noise without adding unnecessary delay in the useful band.

### Recording parameters
`blackbox_device` (SPIFLASH / SDCARD / SERIAL; from 2025.12 also VIRTUAL — for SITL), `blackbox_sample_rate` (1/1, 1/2, 1/4, … of the PID rate: with an 8 kHz PID and 1/4 — a 2 kHz log), `blackbox_mode` (NORMAL — on arming; MOTOR_TEST; ALWAYS — on the ground too: for measuring gyro noise/bias), `blackbox_high_resolution` (finer gyro/setpoint resolution), `blackbox_disable_*` (disable groups of fields: `acc`, `rc`, `gyrounfilt`, `rpm`, `gps`… — saves data rate), `debug_mode` (which 8 debug values to log: `RPM_FILTER`, `D_LPF`, `DSHOT_RPM_TELEMETRY`, `FEEDFORWARD`, `GPS_RESCUE_*`, `AUTOPILOT_ALTITUDE` (before 2025.12 — `GPS_RESCUE_THROTTLE_PID`), `RTH`…; the `GYRO_SCALED` mode — the raw gyro before the filters — does not exist in 2025.12, where the `gyroUnfilt` field replaces it; 4.5 has it). Data rate: 2 kHz with the full set of fields is on the order of 60–100 KB/s → 16 MB of flash lasts 3–4 minutes; an SD card lasts hours. An external logger is the Blackbox logging function on a UART in the Ports tab (`serial <id> 128 …` with the blackbox baud rate); there are no separate `blackbox_uart`/`blackbox_baud` settings in 4.5 or 2025.12.

{{diagram:chart-blackbox-flash-minutes|At 60–100 KB/s (2 kHz, all fields) 16 MB of flash lasts 2.7–4.6 minutes, 8 MB at 80 KB/s — 102 s, 2 MB — 26 s; long sessions need an SD card.}}

Field groups and `blackbox_disable_*` (`cli/settings.c`; in 2025.12 two were added to those listed in the table: `blackbox_disable_attitude` — the `imuQuaternion[0..2]` field, when an accelerometer is present, and `blackbox_disable_servos` — `servo[0..7]`, only with servos in the mixer; the field conditions are in `testBlackboxConditionUncached()` in `blackbox/blackbox.c`). Everything is enabled by default (`fields_disabled_mask = 0`); a group without its sensor is not logged anyway. The number is how many values are in each main frame (for a quadcopter, 4 motors):

| Parameter | What it disables | Values | When to disable |
|---|---|---|---|
| `blackbox_disable_pids` | `axisP`, `axisI`, `axisD`, `axisF` | up to 12 (`axisD` on yaw — only with `d_yaw` ≠ 0) | almost never: without them the tune cannot be analyzed |
| `blackbox_disable_rc` | `rcCommand[0..3]` | 4 | if `setpoint` is there and the sticks are not needed |
| `blackbox_disable_setpoint` | `setpoint[0..3]` | 4 | never for tuning |
| `blackbox_disable_bat` | `vbatLatest`, `amperageLatest` | 2 | rarely: needed for sag |
| `blackbox_disable_mag` | `magADC[0..2]` | 3 (if there is a compass) | there is a compass, but it is not being analyzed |
| `blackbox_disable_alt` | `baroAlt`, `surfaceRaw` | 1–2 (baro/rangefinder) | no altitude-related work |
| `blackbox_disable_rssi` | `rssi` | 1 | — |
| `blackbox_disable_gyro` | `gyroADC[0..2]` (after the filters) | 3 | never |
| `blackbox_disable_gyrounfilt` | `gyroUnfilt[0..2]` (before the filters) | 3 | after the filters are tuned, to save data rate |
| `blackbox_disable_acc` | `accSmooth[0..2]` | 3 | the first candidate when data rate is short on an acro quadcopter |
| `blackbox_disable_debug` | `debug[0..7]` | 8 (only with `debug_mode` ≠ NONE) | `debug_mode = NONE` gives the same result |
| `blackbox_disable_motors` | `motor[0..3]` | 4 | never |
| `blackbox_disable_rpm` | `eRPM[0..3]` | 4 (only with DShot telemetry) | after the RPM filter has been verified |
| `blackbox_disable_gps` | the separate GPS frames (G/H) | — | no GPS analysis |

Storage maintenance from the CLI: `flash_info` — the size and usage of the onboard flash; `flash_erase` — erase it (prints dots until done; the same as the Erase flash button in the Blackbox tab or the BLACKBOX ERASE mode, id 31); `sd_info` — the SD card state (`Not configured`, `None inserted`, `Startup failed`, or the card's manufacturer, capacity and manufacture date); `msc` — reboot the FC into USB mass storage mode, where logs are copied as files from both flash and SD (if the storage is not ready — `Storage not present or failed to initialize!`).

Events in the log (E frames) include in-flight adjustments: a value change made through Adjustments is logged as an `INFLIGHT_ADJUSTMENT` event (the function number and the new value; in step and absolute mode — for all functions, of the select functions — only the rate profile and HORIZON_STRENGTH, `fc/rc_adjustments.c`), so Blackbox Explorer shows at which moment of the flight D became 42. Slots and functions — bf-adjustments.

### The fields needed most often
`gyroADC[0..2]` (after the filters), `gyroUnfilt[0..2]` (before, when the field is enabled), `setpoint[0..3]`, `rcCommand[0..3]`, `axisP/I/D/F[0..2]`, `motor[0..3]`, `eRPM[0..3]`, `vbatLatest`, `amperageLatest`, `rssi`, `debug[0..7]`, `flightModeFlags`, `stateFlags`, `failsafePhase`; events (E frames): arm/disarm, flight mode change, failsafe. The log header contains about 190 key parameters (PIDs, rates, filters, motors), but not the whole `diff`: there is no `aux`, `serial`, OSD or failsafe — a full backup is only `diff all`.

### A method for reading a log in 5 minutes
1. Blackbox Explorer: an overview — any gaps (dropped frames), `vbat` under load, `rssi/LQ`.
2. The gyro spectrogram (before/after) — motors, resonances (the module “Signals and spectra”).
3. Overlay `setpoint` on `gyro` for roll — overshoot/bounce-back by eye; `axisD` — noise.
4. `motor[0..3]` — symmetry (one above the others = imbalance/mechanics), saturation at 100%.
5. Numbers — through Python (`data-python`), into the decision table.

{{lesson:bf-tuning-method|One log shows a state, two show the effect of a change: how to compare logs A and B by noise, tracking error and motor temperature, with a script.}}

### A worked example: “one motor runs hotter”
In the log `motor[2]` is 8% above the others in hover and `eRPM[2]` is lower — the motor produces less thrust: a damaged prop, a bearing or a twisted frame; the noise in `gyroUnfilt` at 2×RPM of this motor is higher. The fix is mechanical, not PID. Without the log this would have looked like “D needs tweaking”.

{{diagram:blackbox-chain|Where in the flight controller loop the main Blackbox fields are taken from and how the log gets into the analysis tools.}}

### Place in the system

- **Receives:** the gyro before and after the filters (`bf-filters`), the setpoint from the stick chain (`bf-rates-rc`), the P, I, D, F terms and the motor commands (`bf-pid-reg-in-bf`), eRPM from DShot telemetry (`bf-rpm-filter`).
- **Provides:** the “before/after” spectrum — to filter tuning (`bf-filters`); the setpoint/gyro overlay and metric values — to tuning (`bf-pid`, `data-python`); adjustment events — to checking what was changed in flight (`bf-adjustments`).
- **If you get it wrong here:** the `gyroUnfilt` or `eRPM` field is disabled → there is nothing to compare the filtered gyro against and no way to check whether the RPM filter covers the real RPM; the filter decision is made blind (`bf-filters`, `bf-rpm-filter`). The log is recorded at 1 kHz instead of 2 kHz → it is enough for basic PID analysis but not for a detailed look at noise and filters (`bf-filters`).

## practice

### Preparing the hardware and software

Hardware:
- an FC with flash or an SD slot,
- ESCs with Bidirectional DShot (BLHeli_32/Bluejay),
- a well-made, mechanically stiff build.

Setup:
- enable `BLACKBOX`,
- set the `logging rate` (usually 2 kHz),
- for noise analysis leave the `gyroUnfilt` field enabled (in 4.5 — either that or `debug_mode = GYRO_SCALED`; 2025.12 does not have this mode),
- enable the RPM filter.

### Recording a log and the maneuvers

Blackbox normally starts on arming and stops on disarming. For a good analysis, fly:
- a hover and straight-and-level flight,
- a throttle sweep `20% -> 100%`,
- sharp rolls/flips,
- throttle pumps,
- sharp turns (a propwash check).

### Working with Blackbox Explorer

1. Download the `.bbl` (Mass Storage Mode).
2. Open the log in Blackbox Explorer.
3. Check the header (`i`) — it holds all the firmware parameters.
4. For analysis select `Gyro`, `Setpoint`, `P/I/D`, `Motor`, `Debug`.
5. Use `I/O` to mark sections of equal length.

### PIDscope (formerly PIDtoolbox)

Since 2024 PIDtoolbox has been distributed as a paid subscription product; the open-source continuation is **PIDscope** (GPL-3.0, runs in the free GNU Octave, supports Betaflight 4.x and 2025.12 logs). It is useful for:
- estimating filter delay,
- comparing spectra in dB,
- step response analysis.

### Step-by-step filter tuning

1. Record a log with the `gyroUnfilt` field (in 4.5 — `debug_mode = GYRO_SCALED` also works) and a `throttle sweep`.
2. Assess the spectrum:
   - `<100 Hz` is more often solved by mechanics/PID,
   - `100–250 Hz` — the dynamic notch zone,
   - `>250 Hz` — the RPM filter zone.
3. Make sure bidirectional DShot works (`E = 0%` in Motors).
4. Set the lowpass from the result of the spectrum.
5. Make changes iteratively: one parameter -> a new log -> a comparison.

### Automatic log check
Decode the log with `blackbox_decode` and run the course grader: `python examples/blackbox-grader/check_bf_log.py LOG.01.csv --lab all --motor-range <motorOutput from the log header>`. It prints PASS/FAIL for every check (tracking, motors) with the value, the threshold and an explanation; the thresholds are reference values for a 5", and they can be overridden with `--set` if you write down the reason. You can practice on synthetic data before using your own logs: `python examples/blackbox-grader/make_bf_fixture.py noisy.csv --kind noisy` (or `sluggish`, `oscillating`, `saturated`, `imbalanced`, `no_rpm`).

### An exercise without hardware: rate, flash and a grader run
You do not need a log of your own for this: the first part is arithmetic from the section “Recording parameters”, the second is running the course grader on synthetic logs with a defect known in advance.

**Part 1. Calculation.**
1. Log rate = PID rate × `blackbox_sample_rate`. In the theory: 8 kHz and 1/4 give 2 kHz. Calculate it for 8 kHz and 1/8, for 4 kHz and 1/2, for 3.2 kHz and 1/2.
2. Time until the flash is full = capacity / data rate. Calculate it for 16 MB at 60, 80 and 100 KB/s and for 8 MB and 2 MB of flash at 80 KB/s (1 MB = 1024 KB).
3. Using the field group table, count how many values the main frame has for a quadcopter under these conditions: `d_yaw` = 0, there is a barometer, no rangefinder and no compass, `debug_mode = NONE`, DShot telemetry works, all `blackbox_disable_*` = OFF. Then — how many remain after `blackbox_disable_acc = ON` and `blackbox_disable_rc = ON`.
4. The gyro spectrum has four peaks: 15, 60, 180 and 320 Hz. Assign each to a band from the section “The physical meaning of the noise spectrum” and write down how it is dealt with according to the section “Step-by-step filter tuning”.
5. From the list “PIDs, rates, filters, `aux`, `serial`, failsafe, OSD” write out what can be recovered from the log header.

**Part 2. The grader on synthetic data.** You need Python 3 and `numpy`. Before running, write down a prediction: which of the checks (`filters`, `tracking`, `motors`, `rpm`) should fail on an `imbalanced` log — the hint is in the worked example “one motor runs hotter”. Then, from the repository root, run `python examples/blackbox-grader/make_bf_fixture.py imbalanced.csv --kind imbalanced` and `python examples/blackbox-grader/check_bf_log.py imbalanced.csv --lab all`; repeat for `good`, `noisy`, `saturated` and `no_rpm`. The generator is deterministic: the numbers in the output must match the table (the output was captured with the grader from this repository).

| `--kind` | Result | `[FAIL]` lines and values |
|---|---|---|
| `good` | `RESULT: PASS (2000.0 Hz)` | none |
| `noisy` | `RESULT: FAIL` | `filters`: noise after the filters 12.94 °/s on roll and 12.95 on pitch (limit ≤ 4.0), attenuation 4.40 dB (limit ≥ 6.0); `tracking`: residual rate with the sticks centered 11.15 and 11.17 °/s (limit ≤ 6.0) |
| `imbalanced` | `RESULT: FAIL` | `motors` only: motor imbalance 0.1764 (limit ≤ 0.12) |
| `saturated` | `RESULT: FAIL` | `motors` only: saturation fraction 0.2001 (limit ≤ 0.02) |
| `no_rpm` | `RESULT: FAIL` | `rpm` only: `eRPM telemetry logged: None` |

Self-check: the lab is complete when:
- the log rates came out as 1000, 2000 and 1600 Hz;
- flash time: 16 MB — 273, 205 and 164 s (4.6, 3.4 and 2.7 min) at 60, 80 and 100 KB/s; 8 MB at 80 KB/s — 102 s; 2 MB — 26 s; a difference of up to 3 % is acceptable if you used 1 MB = 1000 KB;
- the main frame has 40 values, and 33 after disabling `acc` and `rc` (17.5 % fewer);
- the peaks are assigned like this: 15 Hz — useful dynamics, not filtered; 60 Hz — vibration, propwash or PID: mechanics and PID; 180 Hz — a frame resonance or play: the dynamic notch zone; 320 Hz — motors and props: the RPM filter zone;
- PIDs, rates and filters are recovered from the header; `aux`, `serial`, failsafe and OSD — only from `diff all`;
- the prediction for `imbalanced` was written down before the run, and the grader output on the five logs matched the table: one PASS, four FAIL, the values in the `[FAIL]` lines — to the second decimal place;
- on hardware (if you have it): your own log gives `RESULT: PASS`, or every `[FAIL]` line has its value, limit and cause written down.

**Reference for self-check.** The count of values in the frame: PID 11 (P, I and F on three axes, D only on roll and pitch because `d_yaw` = 0), `rcCommand` 4, `setpoint` 4, battery 2, compass 0, altitude 1, `rssi` 1, `gyroADC` 3, `gyroUnfilt` 3, `accSmooth` 3, `debug` 0, `motor` 4, `eRPM` 4 — 40 in total. The correct prediction for `imbalanced` is that a single check, `motors`, fails: one motor works harder than the others while noise and tracking are normal; this is the same case as in the worked example, and the fix is mechanical. Common wrong results: 41 or 48 values — `axisD` on yaw was counted with `d_yaw` = 0, or the 8 `debug` fields with `debug_mode = NONE`; the flash time came out 60 times longer — seconds were written as minutes (16 MB at 80 KB/s is 3.4 minutes, the “3–4 minutes” from the theory); on `noisy` you expected only `filters`, and `tracking` failed too — noise that got through the filters also shows up as residual rate with the sticks centered, there is no separate fault here; the grader exited with an import error — `numpy` is not installed.

## diagnostics

- Symptom: a strong peak at `100–250 Hz` in the gyro log.
  - Possible cause: a frame resonance/play.
  - What to check/do: check the mechanics and make sure the dynamic notch is active.

- Symptom: noise above `250 Hz` is not suppressed.
  - Possible cause: the RPM filter is disabled or bidirectional DShot is set up incorrectly.
  - What to check/do: check `E = 0%` in Motors, enable the RPM filter (it exists only on the gyro — in both 4.5 and 2025.12; there is no separate D-term RPM filter).

- Symptom: spikes in `20–100 Hz`.
  - Possible cause: insufficient P/D or excessive filtering (delay).
  - What to check/do: check the delay in PIDscope (or PIDtoolbox), adjust the filters and PIDs.

- Symptom: the drone became “mushy” after filtering.
  - Possible cause: the cutoff frequencies are too low.
  - What to check/do: raise the gyro lowpass cutoff, check the D-term lowpass and the delay.

- Symptom: a log with gaps/artifacts.
  - Possible cause: write speed/buffer.
  - What to check/do: use a good SD card, lower the logging rate if necessary.

- Symptom: nothing is recorded to onboard flash with Blackbox enabled.
  - Possible cause: the memory is full.
  - What to check/do: `Erase Flash`, download the logs regularly.

- Symptom: incorrect frequencies in the spectrum.
  - Possible cause: sections of different length are being compared.
  - What to check/do: mark equal intervals with `I/O`.
- **Symptom:** the log is cut short / “Log ends abruptly”
  - Possible cause: the flash is full or cannot keep up (DMA/speed), a weak SD card.
  - What to do: erase the flash, a lower `blackbox_sample_rate`, disable unneeded fields, an A1/U3 class card.
- **Symptom:** the log has no gyro before the filters
  - Possible cause: `blackbox_disable_gyrounfilt`, or an old version without the field.
  - What to do: enable the field (`set blackbox_disable_gyrounfilt = OFF`); on 4.5 `debug_mode = GYRO_SCALED` also works.

## references

- Blackbox flight data recorder — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/Black-Box-logging-and-usage | primary | A
- Blackbox logging internals | https://www.betaflight.com/docs/development/Blackbox-Internals | primary | A
- Betaflight Blackbox Explorer | https://github.com/betaflight/blackbox-log-viewer | primary | A
- PIDscope — open-source GNU Octave continuation of PIDtoolbox | https://github.com/dzikus/PIDscope | secondary | B
- How to Use Blackbox in Betaflight — Oscar Liang | https://oscarliang.com/blackbox/ | secondary | B
- How to Tune FPV Drone Filters & PID with Blackbox — Oscar Liang | https://oscarliang.com/pid-filter-tuning-blackbox/ | secondary | B
