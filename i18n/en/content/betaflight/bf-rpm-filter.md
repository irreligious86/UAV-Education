---
id: bf-rpm-filter
title: "RPM Filter: the Case of the “Whistling” 10-Inch"
level: L2
readingTime: 20 min
firmware: Betaflight 4.5+
status: published
added: 2026-11-07
tags:
  - RPM filter
  - bidirectional DShot
  - case study
related:
  - bf-filters
  - bf-blackbox
next:
  - bf-cli-automation
source: content/betaflight/bf-rpm-filter.md
source_hash: 1c0afa58131a
---

## summary
A breakdown of a real case: a 10-inch quadcopter's motors “whistle” and it flies unevenly. The cause turned out to be not the PID but a single line of config: the lower bound of the RPM filter was above the motors' rotation frequency, and for most of the flight the filter simply wasn't working. This module teaches you to check whether the RPM filter covers the real RPM range using Blackbox data, not by eye.

## theory
### How the RPM filter works
With bidirectional DShot, each ESC reports its motor's eRPM to the flight controller. Betaflight converts eRPM into RPM using `motor_poles` and places narrow notch filters exactly on each motor's rotation frequency and its harmonics. By default that's 12 notch filters per axis (4 motors × 3 harmonics) on roll, pitch and yaw. The notch “tracks” the RPM in real time, so it cuts motor noise with almost no extra delay.

### Why big props have different math
The frequency of a motor's fundamental harmonic: `f = RPM / 60`. A five-inch in hover spins at tens of thousands of RPM, and the fundamental sits in the hundreds of hertz. A 10-inch has low-speed motors (low KV, heavy props), and the fundamental in hover can drop to 50–100 Hz.

The `rpm_filter_min_hz` parameter sets the lower bound: the notch doesn't go below it. If the bound is above the motor's real frequency, the filter sits “off target” from the noise. That's exactly what happened in the case below.

### Hardware requirements
- An ESC with DShot telemetry support: BLHeli_32 from 32.7.0, AM32, Bluejay (BLHeli_S) or JESC.
- `dshot_bidir = ON` and a correct `motor_poles` (the number of magnets in the bell, not the number of stator teeth).
- Telemetry errors in the Motors tab no higher than 1%. If an ESC doesn't report valid telemetry, Betaflight blocks arming with the `DSHOT_TELEM` flag (in the OSD/`status`).

### Case: viking10, iFlight Blitz F722, 10"
The pilot's complaint: the motors whistle, the flight is uneven. A spectrum analysis of the log (Python, `orangebox` + `scipy`) showed:

- motor fundamental: p5 = 48 Hz, median 91 Hz, p95 = 165 Hz;
- the config had `rpm_filter_min_hz = 100` — meaning for more than half the flight the motor spun below the bound and the RPM filter didn't see it;
- in the 80–150 Hz band the filtered gyro was only ~2 dB quieter than raw, D-term +44.5 dB — that's the “whistle”;
- static notches sat at 68 Hz, while the motors in hover ran at 84–96 Hz — the filters were cutting empty air.

The fix: `rpm_filter_min_hz = 50`, static notches removed, gyro LPF returned to default. After the next flight, in the same 80–150 Hz band: filtered gyro −9.5 dB (was +24.4), D-term −1.0 dB (was +44.5), motor command noise dropped from ~450 to ~20 arbitrary units. eRPM errors — 0%.

The takeaway: before touching the PID, check that the filters sit where the noise actually lives.

### Parameters (4.5) and what they mean
| Parameter | Default | Meaning |
|---|---|---|
| `dshot_bidir` | OFF → ON | eRPM telemetry over the same DShot line |
| `motor_poles` | 14 | number of magnets; eRPM/(poles/2) = RPM |
| `rpm_filter_harmonics` | 3 | harmonics 1×, 2×, 3× of the motor frequency |
| `rpm_filter_weights` | 100,100,100 | “weight” (depth) of each harmonic in %; the 2nd and 3rd can often be weakened to 50–80 on clean aircraft → less delay |
| `rpm_filter_q` | 500 | Q factor: notch width ≈ f/(Q/100); 500 → f/5 |
| `rpm_filter_min_hz` | 100 | below it no notch is placed (protects the useful band); for 10" — 50 |
| `rpm_filter_fade_range_hz` | 50 | smooth fade-in of the notch above min_hz |
| `rpm_filter_lpf_hz` | 150 | filter on the eRPM estimate itself (smoothing telemetry jumps) |
The effect can only be measured with the spectrum: before/after attenuation of 20–30 dB in the harmonic band is normal; less than 10 dB — something is wrong (polarity/poles/E%).

### Why the RPM filter lets you raise D
D noise ∝ frequency × gyro noise amplitude. Once the narrow motor peaks are removed, you can raise the D-LPF frequencies (less delay) **and** D (more damping) at the same motor temperature — that's what gave the jump in flight quality in 4.1+, not “new PIDs.”

### Worked example: a 7" with Bluejay
BLHeli_S ESC → flash Bluejay (48 kHz), `dshot_bidir = ON`, `motor_poles = 14` (2806.5), Motors tab: RPM on all four, E = 0%; `rpm_filter_min_hz = 70` (hover ~110–130 Hz on a 7"), `rpm_filter_harmonics = 3`, weights 100/80/60; spectrum: 125 Hz peak −27 dB; `dyn_notch_count` 1 for the frame; after that — `simplified_gyro_filter_multiplier` 120, D-term 110; bounce-back 14 → 9%, motors warm.

{{diagram:rpm-filter-chain|RPM filter: eRPM from the ESC is converted into the motor frequency and its harmonics, a notch is placed on each; rpm_filter_min_hz limits it from below.}}

{{diagram:chart-rpm-harmonics|Why the viking10 case broke: the motor fundamental was 48–165 Hz (median 91 Hz, hover 84–96 Hz, i.e. ~5000–5800 RPM), and the 100 Hz lower bound kept the notch above the noise for more than half the flight. A 50 Hz bound puts the filter back on the harmonic.}}

{{widget:rpm-harmonics}}

## practice
### Step 1. Enable and check telemetry
Connect the battery (without it the Motors tab will show `E: 100%`) and run in the CLI:

```
set dshot_bidir = ON
set motor_poles = 14
save
```

After the reboot, always read the values back. Betaflight can silently correct an incompatible combination (for example, the DShot protocol on a particular board):

```
get dshot_bidir
get motor_pwm_protocol
status
```

The `dshot_telemetry_info` command should show telemetry for all motors with near-zero errors (`status` doesn't print it).

### Step 2. Find the real range of motor frequencies
1. Enable Blackbox with a logging rate of at least 1 kHz and do a normal flight with hovering.
2. In Blackbox Explorer or PID Toolbox look at the `eRPM` field (or the gyro spectrum) and find the minimum frequency in hover and on throttle cuts.
3. The raw `eRPM[n]` field (blackbox_decode/orangebox) is stored in units of 100 eRPM: `Hz = eRPM × 100 / (motor_poles / 2) / 60`; Blackbox Explorer shows rpm and Hz on its own.

### Step 3. Adjust the lower bound
Set `rpm_filter_min_hz` below the motor's minimum operating frequency, with margin:

```
get rpm_filter
set rpm_filter_min_hz = 50
save
```

For a 5" the default is usually enough; for 7–10" check it explicitly — the bound can easily end up above the RPM.

### Step 4. Remove the crutches
Static notches set “from an old log” before the RPM filter was enabled — delete them: after the RPM filter they often cut the wrong thing and add delay.

### Automatic log check
Decode the log with `blackbox_decode` and run the course grader: `python examples/blackbox-grader/check_bf_log.py LOG.01.csv --lab rpm --motor-range <motorOutput from the log header>`. It prints PASS/FAIL for each check (rpm, filters) with the value, the threshold and an explanation; the thresholds are reference points for a 5", you can override them with `--set`, writing down the reason. Before you have your own logs, you can practice on synthetic ones: `make_bf_fixture.py --kind noisy` (or `sluggish`, `oscillating`, `saturated`, `imbalanced`, `no_rpm`).

## diagnostics
- **Symptom:** motors “whistle” or hum in hover, goes away with throttle
  - Possible cause: `rpm_filter_min_hz` is above the motor frequency at low throttle.
  - What to do: calculate the motor frequency from the log and lower the bound.
- **Symptom:** arming blocked, OSD shows `DSHOT_TELEM`
  - Possible cause: one of the ESCs doesn't report DShot telemetry (firmware without bidir, wrong protocol).
  - What to do: check the ESC firmware and the errors in the Motors tab with the battery connected.
- **Symptom:** telemetry errors in Motors above 1%
  - Possible cause: interference on the signal line, DShot too fast for the chosen PID loop.
  - What to do: on a 4k/3.2k loop use DShot300, check the soldering of the signal wires.
- **Symptom:** you enabled bidir, and after the reboot it's OFF again
  - Possible cause: the board doesn't support the chosen timer/DMA arrangement, and Betaflight silently rolled the value back.
  - What to do: read back `get dshot_bidir` and `get dshot_bitbang`, compare with the board documentation.
- **Symptom:** OSD shows `DSHOT_TELEM`, arming impossible
  - Possible cause: no eRPM coming in (ESC without bidir, firmware, wire).
  - What to do: ESC firmware (Bluejay/AM32/BLHeli_32 ≥ 32.7), `dshot_bidir`, DShot300 for testing.
- **Symptom:** E% rises at high throttle
  - Possible cause: long/noisy DShot lines, 600 kbit.
  - What to do: DShot300, shorter wires, ground next to the signal.

## references
- DShot RPM Filtering — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/DSHOT-RPM-Filtering | primary | A
- Betaflight CLI — Documentation | https://betaflight.com/docs/wiki/guides/current/Cli | primary | A
- Orangebox — Blackbox log parser for Python | https://github.com/atomgomba/orangebox | secondary | B
- RPM Filter explained — Oscar Liang | https://oscarliang.com/rpm-filter/ | secondary | B

## checklist
- Before making changes, `diff all` was done and saved to a dated file
- Battery connected, telemetry errors in the Motors tab ≤ 1%
- `motor_poles` matches the motor's number of magnets
- Motor frequency in hover calculated from the log
- `rpm_filter_min_hz` below the minimum operating frequency
- After `save`, all values read back with `get`
- First flight after the changes: 30 s hover, land, check the motor temperature
