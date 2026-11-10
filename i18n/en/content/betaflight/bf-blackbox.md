---
id: bf-blackbox
title: "Blackbox: troubleshooting and tuning from flight data"
level: L2
readingTime: 45 min
firmware: Betaflight 4.5+
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
next:
  - bf-custom
source: content/betaflight/bf-blackbox.md
source_hash: ac8c59ec5c3a
---

## summary

Blackbox is the flight data recording system in Betaflight that captures the controller state on every control loop cycle (up to 8 kHz). The log contains the gyro, accelerometer, stick signals, PID controller activity, motor outputs and filter parameters. This article gives you a complete understanding of how to set up logging, interpret the graphs and use the tools (Blackbox Explorer, PIDscope) for troubleshooting and tuning. After studying it, you'll be able to identify your drone's noise structure, estimate filter latency, and tune PIDs and filters based on objective data rather than random trial and error.

## theory

### Purpose and architecture of Blackbox

Blackbox records the internal state of the flight controller at the highest possible rate, to enable offline simulation, debugging and analysis of control algorithms using real flight data. The log is built from frames of several types:

- I-frames (intra) — full frames, independently decodable.
- P-frames (inter) — delta frames, using prediction.
- G/H frames — for GPS data.
- S frames (slow) — rarely changing states.
- E frames (event) — state transitions.

Compression uses predictors and variable-length encoding, which lets you store a large amount of data at a moderate data rate.

### What exactly is logged

Blackbox records:
- time,
- P/I/D values and the summed output,
- setpoint (sticks),
- gyro and accelerometer data,
- voltage/current, RSSI,
- ESC commands,
- GPS frames (if present).

### Log format and storage devices

Logging can go to:
- onboard flash (usually 2–16 MB),
- an SD card (preferred for long sessions),
- an external logger over UART.

For an SD card, FAT32 and a card with low write latency are recommended.

### How settings affect log quality

- 1 kHz — basic PID analysis;
- 2 kHz (or 1.6 kHz for BMI270) — detailed noise/filter analysis.

If the looptime is small (high PID rate), you may need to raise the baud rate or lower the logging rate, otherwise you can get dropped frames.

### Physical meaning of the noise spectrum

- `<20 Hz` — useful dynamics;
- `20–100 Hz` — vibration/propwash/PID problems;
- `100–250 Hz` — frame resonances/play;
- `>250 Hz` — motor/prop noise and harmonics.

The goal of filtering is to suppress high-frequency noise without adding extra latency in the useful range.

### Logging parameters
`blackbox_device` (SPIFLASH / SDCARD / SERIAL), `blackbox_sample_rate` (1/1, 1/2, 1/4, … of the PID rate: with 8 kHz PID and 1/4 — a 2 kHz log), `blackbox_mode` (NORMAL — on arm; MOTOR_TEST; ALWAYS — on the ground too: for measuring gyro noise/bias), `blackbox_high_resolution` (more precise gyro/setpoint), `blackbox_disable_*` (disable field groups: `acc`, `rc`, `gyrounfilt`, `rpm`, `gps`… — saves bandwidth), `debug_mode` (which 8 debug values to log: `GYRO_SCALED` — raw gyro before the filters (4.5 only; removed in 2025.12, use the `gyroUnfilt` field), `RPM_FILTER`, `D_LPF`, `DSHOT_RPM_TELEMETRY`, `FEEDFORWARD`, `GPS_RESCUE_*`, `RTH`…). Data rate: 2 kHz with the full set of fields is around 60–100 KB/s → 16 MB of flash is enough for 3–4 minutes; SD — hours. An external logger is the Blackbox function on a UART in the Ports tab (`serial <id> 128 …` with the blackbox baud); there are no separate `blackbox_uart`/`blackbox_baud` settings in 4.5 and 2025.12.

### The fields you need most often
`gyroADC[0..2]` (after the filters), `gyroUnfilt[0..2]` (before, if the field is enabled), `setpoint[0..3]`, `rcCommand[0..3]`, `axisP/I/D/F[0..2]`, `motor[0..3]`, `eRPM[0..3]`, `vbatLatest`, `amperageLatest`, `rssi`, `debug[0..7]`, `flightModeFlags`, `stateFlags`, `failsafePhase`; events (E-frames): arm/disarm, mode change, failsafe. The log header contains about 190 key parameters (PIDs, rates, filters, motors), but not the whole `diff`: there's no `aux`, `serial`, OSD, failsafe — a full backup only via `diff all`.

### Reading a log in 5 minutes
1. Blackbox Explorer: overview — any gaps (dropped frames), `vbat` under load, `rssi/LQ`.
2. Gyro spectrogram (before/after) — motors, resonances (the “Signals and spectra” module).
3. Overlay `setpoint` on `gyro` for roll — overshoot/bounce-back by eye; `axisD` — noise.
4. `motor[0..3]` — symmetry (one higher than the others = imbalance/mechanical issue), saturation at 100%.
5. Numbers — via Python (`data-python`), into a decision table.

### Worked example: “one motor runs hotter”
In the log, `motor[2]` at hover is 8% higher than the others and `eRPM[2]` is lower — the motor is producing less thrust: a damaged prop, a bearing or a twisted frame; the noise in `gyroUnfilt` at 2×RPM of that motor is higher. The fix is mechanical, not PID. Without a log this would have looked like “need to bump up D”.

{{diagram:blackbox-chain|Where in the flight controller loop the main Blackbox fields come from and how the log gets into the analysis tools.}}

## practice

### Preparing hardware and software

Hardware:
- an FC with flash or an SD slot,
- ESCs with Bidirectional DShot (BLHeli_32/Bluejay),
- a high-quality, mechanically stiff build.

Setup:
- enable `BLACKBOX`,
- set the `logging rate` (usually 2 kHz),
- for noise analysis use `debug_mode = GYRO_SCALED`,
- enable the RPM filter.

### Recording a log and maneuvers

Blackbox usually starts on arm and stops on disarm. For a good analysis, fly:
- hover and straight-and-level flight,
- throttle sweep `20% -> 100%`,
- sharp rolls/flips,
- throttle pumps,
- sharp turns (propwash check).

### Working with Blackbox Explorer

1. Download the `.bbl` (Mass Storage Mode).
2. Open the log in Blackbox Explorer.
3. Check the header (`i`) — it has all the firmware parameters.
4. For analysis, select `Gyro`, `Setpoint`, `P/I/D`, `Motor`, `Debug`.
5. Use `I/O` to select sections of equal length.

### PIDscope (formerly PIDtoolbox)

Since 2024 PIDtoolbox has been distributed as a paid subscription product; its open continuation is **PIDscope** (GPL-3.0, runs in the free GNU Octave, supports Betaflight 4.x and 2025.12 logs). It's useful for:
- estimating filter latency,
- comparing spectra in dB,
- step response analysis.

### Step-by-step filter tuning

1. Record a log with `GYRO_SCALED` and a `throttle sweep`.
2. Assess the spectrum:
   - `<100 Hz` is usually solved with mechanics/PID,
   - `100–250 Hz` — the dynamic notch zone,
   - `>250 Hz` — the RPM filter zone.
3. Make sure bidirectional DShot works (`E = 0%` in Motors).
4. Set the lowpass according to the spectrum.
5. Make changes iteratively: one parameter -> new log -> comparison.

### Automatic log check
Decode the log with `blackbox_decode` and run the course grader: `python examples/blackbox-grader/check_bf_log.py LOG.01.csv --lab all --motor-range <motorOutput from the log header>`. It prints PASS/FAIL for each check (tracking, motors) with the value, the threshold and an explanation; the thresholds are guidelines for a 5", you can override them with `--set`, writing down the reason. You can practice on synthetic data before you have your own logs: `make_bf_fixture.py --kind noisy` (or `sluggish`, `oscillating`, `saturated`, `imbalanced`, `no_rpm`).

## diagnostics

- Symptom: a strong peak at `100–250 Hz` in the gyro log.
  - Possible cause: frame resonance/play.
  - What to do (check/fix): check the mechanics and make sure the dynamic notch is active.

- Symptom: noise above `250 Hz` isn't suppressed.
  - Possible cause: the RPM filter is off or bidirectional DShot is misconfigured.
  - What to do (check/fix): check `E = 0%` in Motors, enable the RPM filter (in 4.5 it exists only on the gyro; there's no separate D-term RPM filter).

- Symptom: spikes in `20–100 Hz`.
  - Possible cause: insufficient P/D or excessive filtering (latency).
  - What to do (check/fix): check the latency in PIDscope (or PIDtoolbox), adjust the filters and PIDs.

- Symptom: the drone feels “mushy” after filtering.
  - Possible cause: cutoff frequencies too low.
  - What to do (check/fix): raise the gyro lowpass cutoff, check the D-term lowpass and the latency.

- Symptom: log with gaps/artifacts.
  - Possible cause: write speed/buffer.
  - What to do (check/fix): use a good SD card, lower the logging rate if needed.

- Symptom: nothing is recorded to onboard flash with Blackbox enabled.
  - Possible cause: the memory is full.
  - What to do (check/fix): `Erase Flash`, download logs regularly.

- Symptom: wrong frequencies in the spectrum.
  - Possible cause: sections of different length are being compared.
  - What to do (check/fix): select equal intervals with `I/O`.
- **Symptom:** the log cuts off / “Log ends abruptly”
  - Possible cause: the flash is full or can't keep up (DMA/speed), a weak SD card.
  - What to do: erase the flash, lower `blackbox_sample_rate`, disable unneeded fields, use an A1/U3 class card.
- **Symptom:** the log has no pre-filter gyro
  - Possible cause: `blackbox_disable_gyrounfilt` or an old version without the field.
  - What to do: enable the field or `debug_mode = GYRO_SCALED`.

## references

- Blackbox flight data recorder — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/Black-Box-logging-and-usage | primary | A
- Blackbox logging internals | https://www.betaflight.com/docs/development/Blackbox-Internals | primary | A
- Betaflight Blackbox Explorer | https://github.com/betaflight/blackbox-log-viewer | primary | A
- PIDscope — open-source GNU Octave continuation of PIDtoolbox | https://github.com/dzikus/PIDscope | secondary | B
- How to Use Blackbox in Betaflight — Oscar Liang | https://oscarliang.com/blackbox/ | secondary | B
- How to Tune FPV Drone Filters & PID with Blackbox — Oscar Liang | https://oscarliang.com/pid-filter-tuning-blackbox/ | secondary | B
