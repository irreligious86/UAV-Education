---
id: bf-rpm-filter
title: "The RPM filter: the case of a “whistling” 10-inch"
level: L2
readingTime: 35 min
firmware: Betaflight 2025.12 (checked against 2025.12.5)
status: published
added: 2026-11-07
tags:
  - RPM filter
  - bidirectional DShot
  - case study
related:
  - bf-filters
  - bf-blackbox
  - f-esc-firmware
  - bf-pid-reg-in-bf
next:
  - bf-cli-automation
source: content/betaflight/bf-rpm-filter.md
source_hash: 8d7a6bb8a28b
---

## summary
An analysis of a real case: a 10-inch quadcopter's motors “whistle” and it flies unevenly. The cause turned out to be not PID but one line of the config: the lower limit of the RPM filter was above the motor rotation frequency, and for most of the flight the filter simply did not work. This module teaches you to check whether the RPM filter covers the real RPM range from Blackbox data, not by eye. The theory follows the Betaflight code: the path eRPM → frequency → notch weight, the role of `motor_poles`, `rpm_filter_*`, the connection with dynamic idle and the dynamic notch, and the diagnostics of telemetry errors; a calculation lab shows which harmonics work at your RPM.

## theory
### How the RPM filter works
With bidirectional DShot every ESC reports the eRPM of its motor to the flight controller. Betaflight converts eRPM to RPM using `motor_poles` and places narrow notch filters exactly on the rotation frequency of each motor and its harmonics. By default that is 12 notch filters per axis (4 motors × 3 harmonics) on roll, pitch and yaw. A notch “follows” the RPM in real time, so it cuts motor noise with almost no extra delay.

### Why the math is different for large props
The fundamental frequency of a motor: `f = RPM / 60`. A five-inch in hover spins at tens of thousands of RPM, and the fundamental lies in the hundreds of hertz. A 10-inch has low-RPM motors (low KV, heavy props), and the fundamental in hover can drop to 50–100 Hz.

The `rpm_filter_min_hz` parameter sets the lower limit: a notch does not go below it and is turned off (weight 0, details below). If the limit is above the real motor frequency, the filter sits “beside” the noise. That is exactly what happened in the case below.

### From eRPM to notch: the chain in the code
Below is the path of one number from the ESC to the gyro filter. The references are to Betaflight 4.5.3. In 2025.12.5 the chain is the same with one difference: the notch update takes the actual scheduler cycle time into account (`schedulerGetCycleTimeMultiplier()` in `rpmFilterUpdate()`).

1. **eRPM.** The ESC answers every DShot frame with an eRPM number in units of 100 (`ERPM_PER_LSB` = 100, `drivers/dshot.c:56`). eRPM is electrical RPM: one mechanical revolution corresponds to `motor_poles`/2 electrical ones.
2. **The motor frequency.** `erpmToHz = 100 / 60 / (motor_poles / 2)` (`dshot.c:160`). In every loop the frequency of each motor passes through a PT1 with a cutoff of `rpm_filter_lpf_hz` (`dshot.c:165, 333`). The minimum over the motors goes to dynamic idle (`getMinMotorFrequencyHz()`). A raw 350 with 14 magnets is 83.3 Hz. If `motor_poles = 12` is set by mistake, the result is 97.2 Hz, that is, all the notches shift by a factor of 14/12 = 1.17.
3. **Initialization** (`flight/rpm_filter.c:71–110`). Without telemetry or with `rpm_filter_harmonics = 0` the filter is off. The upper stop `maxHz = 0.48 · f_loop`: 3840 Hz at 8 kHz, 1920 Hz at 4 kHz. Q = `rpm_filter_q`/100, and the weights are clipped to 0…1. Each axis gets motors × harmonics notches: 4 × 3 = 12, and three axes — 36.
4. **The update** (`rpm_filter.c:112–168`). All the notches are retuned within 1 ms (`RPM_FILTER_DURATION_S`), several per loop: 2 at 8 kHz, 3 at 4 kHz, 4 at 3.2 kHz. For harmonic k the frequency f_k = k · f_motor is constrained to the range [`rpm_filter_min_hz`; maxHz]. Margin = f_k − min_hz. If the margin is less than `rpm_filter_fade_range_hz`, the weight is multiplied by margin/fade, then by `rpm_filter_weights[k]`. The coefficients are computed for roll and copied to pitch and yaw.
5. **Application.** The filter sits right after the downsampling of the samples (with `gyro_lpf2` enabled, that is the downsampling filter, `gyro_filter_impl.c:37–40`), before the static notches, LPF1 and the dynamic notch (`sensors/gyro_filter_impl.c:52–53`); the order is as in `bf-filters`: LPF2 → RPM → static notches → LPF1 → dynamic notch. Every notch mixes its input and output by the weight: output = w · notch(x) + (1 − w) · x (`common/filter.c:227–234`).

Item 4 implies a non-obvious detail. Below `rpm_filter_min_hz` a notch does not disappear; it sits at min_hz with weight 0, that is, it does nothing. With `rpm_filter_fade_range_hz = 0` the condition “the margin is less than fade” is never met. Then the notch of a slow motor stays parked at min_hz at full depth, like a static notch. This is an inference from the code; it was not verified on an aircraft.

### Low RPM, dynamic idle and harmonic coverage
The weight is computed from the frequency, and the frequency from the mechanical RPM, so coverage is conveniently measured in RPM. With the defaults (min 100 Hz, fade 50 Hz):
- the 1st harmonic works at full strength only above 150 Hz = 9000 RPM and is off below 6000 RPM;
- the 2nd works at full strength above 4500 RPM;
- the 3rd — above 3000 RPM.

Hence the main conclusion. At idle, in falls and on a throttle chop (the propwash zone) the fundamental is often not filtered at all, and on a 10″ (hover at 5000–5800 RPM) — not in hover either. On a 7″ (hover at 110–130 Hz, 6600–7800 RPM) the 1st harmonic works only partially in hover: a weight of 0.2–0.6.

Dynamic idle (`bf-pid-reg-in-bf`) keeps the slowest motor no lower than `dyn_idle_min_rpm` × 100 RPM and thereby sets the lower edge of the filter's working range. With `dyn_idle_min_rpm = 30` (3000 RPM) and the defaults only the 3rd harmonic (150 Hz) works fully, and the 2nd sits exactly at min_hz with weight 0. With `rpm_filter_min_hz = 50` at the same 3000 RPM the 2nd and 3rd harmonics work at full strength, and the 1st turns on from 3000 and reaches full strength by 6000 RPM. There is a second effect too: dynamic idle does not let the RPM collapse toward zero, so eRPM at low throttle is more stable and the notch jumps less.

{{lesson:bf-pid-reg-in-bf|How the dynamic idle controller uses the same eRPM to raise the lower motor limit, its P/I/D and the limits on the ground and in the air — with formulas from `mixer.c`.}}

The price of a low min_hz is that a notch of width f/5 at 50–100 Hz (10–20 Hz of bandwidth) lies close to the band where PID works and adds phase delay. A course guideline: lower min_hz to the minimum working frequency from the log, not to 30 “just in case”.

{{diagram:chart-bf-rpm-notch-weight|The RPM notch weight versus RPM at the defaults: the 1st harmonic is off below 6000 RPM and at full strength above 9000, so at dynamic idle 30 (3000 RPM) only the 3rd is filtered; min_hz 50 turns the 1st on already from 3000 RPM.}}

### The RPM filter and the dynamic notch
The dynamic notch (FFT) receives the gyro **after** the RPM filter, the static notches and the LPF (`gyro_filter_impl.c:75`, `dynNotchPush()`). Whatever the RPM filter has already removed, the FFT does not see and does not spend its notches on. What remains is frame resonances and what the RPM filter let through: harmonics below min_hz, the 4th and higher, prop noise.

The defaults `dyn_notch_count = 3`, `dyn_notch_q = 300`, `dyn_notch_min_hz = 100`, `dyn_notch_max_hz = 600` (`pg/dyn_notch.c:32–37`), with a count range of 0–5 in 4.5.3 and 0–7 in 2025.12. They do not change automatically for the RPM filter. With a healthy RPM filter the course advises 1–2 notches (`bf-filters`).

The downside: if eRPM stops arriving in flight, the RPM filter does not turn off. The notches freeze at the last received frequencies (`getDshotErpm()` returns the last valid value, `dshot.c:281–283, 341–344`) and stop tracking the motors. This is an inference from the code; it was not verified on an aircraft. One or two dynamic notches will not cover 4 motors × 3 harmonics, and the motors start to heat up.

### Telemetry diagnostics: where to look for eRPM errors
- **`dshot_telemetry_info`** (CLI, `cli/cli.c:6099–6175`, present in 2025.12). With bidir off it prints only “Dshot telemetry not enabled”. Otherwise it first prints `Dshot reads`, `Dshot invalid pkts` — the overall counters — and `Dshot directionChange cycles`. Then comes a table by motor: `Type` (the letters R/T/V/C/S — eRPM, temperature, voltage, current, state; T/V/C/S only with EDT), `eRPM` (already × 100), `RPM`, `Hz`, `Invalid` — the share of bad packets over a sliding second (a 1 s window, 100 ms buckets, `drivers/dshot.h:45–46`). `NO DATA` means that not a single eRPM has come from the motor. Then come the columns TEMP, VCC, CURR, ST/EV, DBG1–3 (EDT). The `Invalid` column exists with `USE_DSHOT_TELEMETRY_STATS`, which is enabled by default (`target/common_pre.h:59`).
- **The Motors tab, E%** — the same number `getDshotTelemetryMotorInvalidPercent()` over MSP (`msp/msp.c:1229`). A motor without eRPM gives exactly 100 % (`dshot.c:417–418`): that is why without a battery the tab shows `E: 100%`.
- **In flight:** `debug_mode = DSHOT_RPM_ERRORS` writes the error share × 100 for motors 1–4 to debug[0…3] (`fc/core.c:1209–1214`). `debug_mode = RPM_FILTER` writes the frequency of each motor in Hz (`rpm_filter.c:118–120`): it can be laid over the spectrum to see where the notches ended up.

### Hardware requirements
- ESCs that support DShot telemetry: BLHeli_32 from 32.7.0, AM32, Bluejay (BLHeli_S) or JESC.
- `dshot_bidir = ON` and a correct `motor_poles` (the number of magnets in the bell, not the number of stator teeth).
- Telemetry errors in the Motors tab no higher than 1 % (a course guideline). If with `dshot_bidir = ON` even one motor has not sent a single eRPM packet, Betaflight blocks arming with the `DSHOT_TELEM` flag (in the OSD and `status`; `fc/core.c:365–370` in 4.5.3). The flag checks only for the presence of eRPM, not the error share: with 5 % of bad packets arming is allowed, and between valid packets the filter holds the last valid RPM value.

`dshot_bidir` is OFF by default (`pg/motor.c:48, 118`). At boot `validateAndFixConfig()` (`config/config.c:542–558`) silently turns it off in two cases: the protocol is not DShot, or `dshot_bitbang = OFF` with `dshot_burst` enabled or a motor on an N channel of a timer. On F405, F411 and G47x (`USE_PID_DENOM_CHECK`; in 2025.12 also APM32F405/F407), with bidir `validateAndFixGyroConfig()` switches DSHOT600 to DSHOT300, and with a gyro faster than 4 kHz makes `pid_process_denom` no less than 2 (`config.c:671–685`; the same in 2025.12, `config.c:585–601`). The only exception is F405: with CPU overclocking (`cpu_overclock` ≥ 2, `USE_PID_DENOM_OVERCLOCK_LEVEL`) this does not happen; F411 and G47x are always switched. So on an F4, re-read the protocol and the loop rate after `save`.

{{lesson:f-esc-firmware|Which ESC firmware answers over bidirectional DShot and EDT, how to reflash BLHeli_S to Bluejay or BLHeli_32 to AM32, and which ESC settings change in the process.}}

### The case: viking10, iFlight Blitz F722, 10"
The pilot's complaint: the motors whistle and the flight is uneven. A spectral analysis of the log (Python, `orangebox` + `scipy`) showed:

- the motor fundamental: p5 = 48 Hz, median 91 Hz, p95 = 165 Hz;
- the config had `rpm_filter_min_hz = 100` — that is, for more than half of the flight the motor was spinning below the limit and the RPM filter did not see it;
- in the 80–150 Hz band the filtered gyro was only ~2 dB quieter than the raw one, and the D term was +44.5 dB — that is the “whistle”;
- the static notches sat at 68 Hz, while the motors in hover ran at 84–96 Hz — the filters were cutting empty space.

The fix: `rpm_filter_min_hz = 50`, the static notches removed, the gyro LPF returned to the default. After the next flight, in the same 80–150 Hz band: the filtered gyro −9.5 dB (it was +24.4), the D term −1.0 dB (it was +44.5), and the noise of the motor command fell from ~450 to ~20 arbitrary units. eRPM errors — 0%.

The conclusion: before touching PID, check that the filters sit where the noise actually lives.

### The parameters and what they mean (the defaults are the same in 4.5 and 2025.12)
| Parameter | Default | Range | Meaning (per the 4.5.3 code) |
|---|---|---|---|
| `dshot_bidir` | OFF (we set ON) | OFF, ON | eRPM telemetry over the same DShot line; without it at boot the RPM filter and dynamic idle are off |
| `motor_poles` | 14 | 4–255 | the number of magnets; RPM = eRPM/(poles/2), Hz = eRPM·100/60/(poles/2) |
| `rpm_filter_harmonics` | 3 | 0–3 | harmonics 1×, 2×, 3×; 0 turns the filter off |
| `rpm_filter_weights` | 100,100,100 | 0–100 per harmonic (more than 100 = 100) | the notch “weight”: output = w·notch + (1 − w)·input, the depth at the center 20·log₁₀(1 − w): 80 → −14 dB, 50 → −6 dB; 0 — the harmonic is skipped |
| `rpm_filter_q` | 500 | 250–3000 | the quality factor Q/100: notch width ≈ f/(Q/100); 500 → f/5 |
| `rpm_filter_min_hz` | 100 | 30–200, Hz | the lower stop: a lower frequency is constrained to min_hz, and the weight there is 0 — the notch is effectively off |
| `rpm_filter_fade_range_hz` | 50 | 0–1000, Hz | the weight rises linearly from 0 at min_hz to 1 at min_hz + fade |
| `rpm_filter_lpf_hz` | 150 | 100–500, Hz | a PT1 on the frequency of each motor from eRPM; the same frequency goes to dynamic idle |

Sources: `cli/settings.c:856, 868, 1737–1742` and `pg/rpm_filter.c:32–39` (4.5.3; in 2025.12.5 — `settings.c:968, 980, 1954–1959`, the same defaults). The number of harmonics: `rpm_filter_harmonics` = N filters 1…N and drops only from the top; an individual harmonic is turned off with a weight of 0 in `rpm_filter_weights`. The course rule (in detail — `f-micro-whoop`): do not remove or weaken the harmonic whose number equals the number of blades (the blade-pass frequency: the 2nd for a two-blade prop, the 3rd for a three-blade one); for a four-blade prop it is the 4th and outside the RPM filter — the dynamic notch takes it; with the `LOAD` flag on an F411, first zero the weight of a harmonic that has no line in the spectrum. Notches per axis — motors × N (a quadcopter — 12, an X8 — 24). Weakening the other harmonics (not the blade-pass frequency) to 50–80 on clean aircraft is a course guideline, not a rule: the delay is lower, but the notch depth is limited (−6…−14 dB). “Clean” here means an aircraft whose line of that harmonic in the pre-filter spectrum (`gyroUnfilt`) rises above the background by no more than ~10 dB (a course guideline). The effect is measured only with a spectrum: after the weakening the line of the harmonic in the post-filter spectrum must not rise above the background — the same “before/after” measurement as below. Before/after in the band of the harmonics, an attenuation of 20–30 dB is normal, and less than 10 dB means something is wrong: polarity, `motor_poles`, E% (a course guideline).

### Why the RPM filter allows a higher D
D noise ∝ frequency × the amplitude of the gyro noise. With the narrow motor peaks removed, the D LPF frequencies can be raised (less delay) **and** so can D (more damping) at the same motor temperature — that, not “new PIDs”, is what gave the jump in flight quality in 4.1+.

### A worked example: a 7" with Bluejay
A teaching example (an illustration, not a real log). BLHeli_S ESCs → flash Bluejay (48 kHz), `dshot_bidir = ON`, `motor_poles = 14` (2806.5), the Motors tab: RPM on all four, E = 0%; `rpm_filter_min_hz = 70` (hover at ~110–130 Hz on a 7", that is, 6600–7800 RPM; the weight of the 1st harmonic at the lower edge is (110 − 70)/50 = 0.8 — deliberately; for a weight of 1.0 by the method of step 5, min_hz ≤ 60 is needed), `rpm_filter_harmonics = 3`, weights 100/80/60; the spectrum: the 125 Hz peak is −27 dB; `dyn_notch_count` 1 for the frame; after that — `simplified_gyro_filter_multiplier` 120, D term 110; bounce-back 14 → 9%, the motors are warm.

{{diagram:rpm-filter-chain|The RPM filter: the eRPM from the ESC is converted to the motor frequency and its harmonics, and a notch is placed on each; rpm_filter_min_hz limits it from below.}}

{{diagram:chart-rpm-harmonics|Why the viking10 case broke: the motor fundamental was 48–165 Hz (median 91 Hz, hover 84–96 Hz, that is, ~5000–5800 RPM), while the 100 Hz lower limit kept the notch above the noise for more than half of the flight. A limit of 50 Hz puts the filter back on the harmonic.}}

{{widget:rpm-harmonics}}

### Place in the system

- **Receives:** the eRPM of each motor over bidirectional DShot from ESCs with suitable firmware (`f-esc-firmware`); `motor_poles` — the number of motor magnets (`f-motors-esc`); the spectrum of a log to check the real RPM range (`bf-blackbox`).
- **Provides:** notches on the motor harmonics in the gyro chain (`bf-filters`); the headroom that allows D and the D LPF frequencies to be raised (`bf-pid`); the RPM for dynamic idle (`bf-features-tour`, `bf-pid-reg-in-bf`); a gyro without motor harmonics — to the dynamic notch, which is left with the frame resonances.
- **If you get it wrong here:** `rpm_filter_min_hz` is above the real motor frequency (large props) → the notch sits beside the noise, the D term amplifies it, and the motors “whistle”; it looks like bad PID and is found from the spectrum (`bf-blackbox`, `bf-pid`). An ESC does not send telemetry with `dshot_bidir = ON` → the `DSHOT_TELEM` flag, arming is blocked (`bf-arming-safety`).

## practice
### Step 1. Enable and check telemetry
Connect the battery (without it the Motors tab will show `E: 100%`) and run in the CLI:

```
set dshot_bidir = ON
set motor_poles = 14
save
```

After the reboot — be sure to re-read the values. Betaflight may silently correct an incompatible combination (for example, the DShot protocol on a particular board):

```
get dshot_bidir
get motor_pwm_protocol
status
```

The `dshot_telemetry_info` command should show telemetry for all the motors with almost zero errors (`status` does not print it).

### Step 2. Find the real range of motor frequencies
1. Enable Blackbox with a logging rate of at least 1 kHz and make an ordinary flight with a hover.
2. In Blackbox Explorer or PID Toolbox look at the `eRPM` field (or the gyro spectrum) and find the minimum frequency in hover and on a throttle chop.
3. The raw field `eRPM[n]` (blackbox_decode/orangebox) is stored in units of 100 eRPM: `Hz = eRPM × 100 / (motor_poles / 2) / 60`; Blackbox Explorer shows rpm and Hz by itself.

### Step 3. Adjust the lower limit
Set `rpm_filter_min_hz` below the minimum working frequency of the motor, with a margin:

```
get rpm_filter
set rpm_filter_min_hz = 50
save
```

For a 5" the default is usually enough; for 7–10" check explicitly — the limit easily ends up above the RPM.

### Step 4. Remove the crutches
Delete the static notches that were set “from an old log” before the RPM filter was enabled: after the RPM filter they often cut the wrong thing and add delay.

### Step 5. Check the harmonic coverage by calculation
No hardware is needed. The script repeats `rpmFilterUpdate()` and the eRPM conversion from `drivers/dshot.c` (4.5.3) and shows which harmonics work at a given RPM:

```python
# Betaflight 4.5.3 RPM filter: drivers/dshot.c (eRPM -> Hz), flight/rpm_filter.c (notch weight), common/filter.c
import math

def motor_hz(erpm_raw, poles=14):                 # erpmToHz = 100 / 60 / (poles / 2)
    return erpm_raw * 100 / 60 / (poles / 2)

def weight(rpm, k, min_hz=100, fade=50, w=1.0):   # rpmFilterUpdate()
    f = max(k * rpm / 60, min_hz)                 # constrainf(f, minHz, maxHz)
    margin = f - min_hz
    return (margin / fade if margin < fade else 1.0) * w

print("eRPM raw 350, 14 magnets ->", round(motor_hz(350), 1), "Hz; with motor_poles 12 ->", round(motor_hz(350, 12), 1), "Hz")
for loop in (8000, 4000, 3200):
    upd = math.ceil(4 * 3 / (0.001 * loop))
    print(f"loop {loop} Hz: maxHz {0.48 * loop:.0f} Hz, notch updates per loop {upd}")
for min_hz in (100, 50):
    for rpm in (3000, 4500, 6000, 9000):
        ws = [round(weight(rpm, k, min_hz), 2) for k in (1, 2, 3)]
        print(f"min_hz {min_hz}, {rpm} RPM ({rpm/60:.0f} Hz): weights 1st/2nd/3rd = {ws}")
for w in (1.0, 0.8, 0.5):
    depth = "unlimited" if w == 1 else f"{20 * math.log10(1 - w):.1f} dB"
    print(f"rpm_filter_weights {int(w*100)}: depth at the notch center {depth}")
```

The output (Python 3, an actual run):

```text
eRPM raw 350, 14 magnets -> 83.3 Hz; with motor_poles 12 -> 97.2 Hz
loop 8000 Hz: maxHz 3840 Hz, notch updates per loop 2
loop 4000 Hz: maxHz 1920 Hz, notch updates per loop 3
loop 3200 Hz: maxHz 1536 Hz, notch updates per loop 4
min_hz 100, 3000 RPM (50 Hz): weights 1st/2nd/3rd = [0.0, 0.0, 1.0]
min_hz 100, 4500 RPM (75 Hz): weights 1st/2nd/3rd = [0.0, 1.0, 1.0]
min_hz 100, 6000 RPM (100 Hz): weights 1st/2nd/3rd = [0.0, 1.0, 1.0]
min_hz 100, 9000 RPM (150 Hz): weights 1st/2nd/3rd = [1.0, 1.0, 1.0]
min_hz 50, 3000 RPM (50 Hz): weights 1st/2nd/3rd = [0.0, 1.0, 1.0]
min_hz 50, 4500 RPM (75 Hz): weights 1st/2nd/3rd = [0.5, 1.0, 1.0]
min_hz 50, 6000 RPM (100 Hz): weights 1st/2nd/3rd = [1.0, 1.0, 1.0]
min_hz 50, 9000 RPM (150 Hz): weights 1st/2nd/3rd = [1.0, 1.0, 1.0]
rpm_filter_weights 100: depth at the notch center unlimited
rpm_filter_weights 80: depth at the notch center -14.0 dB
rpm_filter_weights 50: depth at the notch center -6.0 dB
```

Substitute the RPM of your own hover and the minimum RPM from the log (step 2), as well as your `dyn_idle_min_rpm` × 100. Find the lowest `rpm_filter_min_hz` (in steps of 5 Hz) at which the 1st harmonic in hover has a weight of 1.0. For the case in the theory (hover at 84–96 Hz, that is, 5040–5760 RPM) the answer is 30 Hz. That is the lower end of the parameter's range: min_hz + fade = 80 Hz ≤ 84 Hz. At 50 Hz, as in the case, the weight at 84 Hz is 0.68. So with such an aircraft you either live with partial depth at the lower edge of the hover or reduce `rpm_filter_fade_range_hz`: with 50/30 the weight at 84 Hz is already 1.0.

### Automatic log check
Decode the log with `blackbox_decode` and run the course grader: `python examples/blackbox-grader/check_bf_log.py LOG.01.csv --lab rpm --motor-range <motorOutput from the log header>`. It gives PASS/FAIL for every check (rpm, filters) with the value, the threshold and an explanation; the thresholds are guidelines for a 5" and can be overridden with `--set`, with the reason written down. You can practice on synthetic data before your own logs: `make_bf_fixture.py --kind noisy` (or `sluggish`, `oscillating`, `saturated`, `imbalanced`, `no_rpm`).

Self-check: the lab is complete when:
- by calculation (step 5, without hardware) the script output matched the one given. For your own hover RPM and minimum RPM you found the weights of the three harmonics and the lowest `rpm_filter_min_hz` at which the 1st harmonic in hover has a weight of 1.0. For the case in the theory: 30 Hz with fade 50 or 50 Hz with fade 30;
- on hardware: `dshot_telemetry_info` shows `R` in the `Type` column and `Invalid` ≤ 1 % for all the motors, and `get dshot_bidir` after a reboot = ON. In a log with `debug_mode = DSHOT_RPM_ERRORS` all four channels are ≤ 100 (1 %) for the whole flight. In the gyro spectrum the motor peaks in hover are attenuated by at least 20 dB against the log before the changes (a course guideline).

**Reference for self-check.** For a 5″ the fundamental in hover is 250–450 Hz (`bf-filters`), that is, 15,000–27,000 RPM. The defaults 100/50 give all three harmonics a weight of 1.0 there with a large margin, and nothing needs to be changed. For the 10″ from the case — 30/50 or 50/30, as above.

Typical wrong answers:
- “min_hz 80 is enough, since the hover is at 84 Hz”. The fade was forgotten: with 80/50 the weight at 84 Hz is only 0.08.
- The frequency was computed from the raw eRPM without multiplying by 100: the result is 0.83 Hz instead of 83.3 Hz.
- `motor_poles` = 9 was taken from the number of stator teeth of a 9N12P: the frequencies are too high by a factor of 12/9 = 1.33, and the notches end up above the noise (`f-micro-whoop`).

## diagnostics
- **Symptom:** the motors “whistle” or hum in hover, and it goes away with throttle
  - Possible cause: `rpm_filter_min_hz` is above the motor frequency at low throttle.
  - What to do: compute the motor frequency from the log and lower the limit.
- **Symptom:** arming is blocked, the OSD shows `DSHOT_TELEM`
  - Possible cause: one of the ESCs does not send DShot telemetry (firmware without bidir, a wrong protocol).
  - What to do: check the ESC firmware and the errors in the Motors tab with the battery connected.
- **Symptom:** telemetry errors in Motors are above 1%
  - Possible cause: interference on the signal line, a DShot rate too high for the chosen PID loop.
  - What to do: use DShot300 on a 4k/3.2k loop, check the solder joints of the signal wires.
- **Symptom:** you enabled bidir, and after a reboot it is OFF again
  - Possible cause: the board does not support the chosen timer/DMA scheme, and Betaflight silently reverted the value.
  - What to do: re-read `get dshot_bidir` and `get dshot_bitbang`, check against the board documentation.
- **Symptom:** the OSD shows `DSHOT_TELEM`, and in `dshot_telemetry_info` one motor has `NO DATA`
  - Possible cause: eRPM does not arrive from this particular ESC: firmware without bidir, a broken or badly soldered signal wire.
  - What to do: the ESC firmware (Bluejay/AM32/BLHeli_32 ≥ 32.7), the signal solder joint; DShot300 as a test.
- **Symptom:** E% is 0 on the bench, but the motors heat up in flight and the peaks in the spectrum “wander”
  - Possible cause: telemetry errors appear only under load (interference from the power wires). The `DSHOT_TELEM` flag does not catch them; it checks only for the presence of eRPM.
  - What you see in the log: `debug_mode = DSHOT_RPM_ERRORS`, debug[0…3] above 100 (1 %) in a punch-out.
  - What to do: DShot300, the signal wire next to ground and away from the power wires, a ferrite ring if needed (a course guideline).
- **Symptom:** the motor peaks in the spectrum are not where the frequencies from `debug_mode = RPM_FILTER` are
  - Possible cause: a wrong `motor_poles`: the notches are shifted by a factor of poles_true/poles_set (14 against 12 — by 17 %).
  - What to do: count the magnets on the bell again, `set motor_poles = <number of magnets>`.
- **Symptom:** after `rpm_filter_min_hz = 30` the noise went away, but the aircraft became “mushy” at low throttle, and propwash did not decrease
  - Possible cause: a notch of width f/5 at 30–60 Hz adds phase delay in the band where PID works.
  - What to do: raise min_hz to the minimum working frequency from the log; enable dynamic idle (`bf-pid-reg-in-bf`) so that the RPM does not drop below it.
- **Symptom:** after telemetry was lost in flight the motors are suddenly hot
  - Possible cause: without fresh eRPM the RPM notches froze at the old frequencies (an inference from the code), and 1–2 dynamic notches do not cover 12 harmonics.
  - What to do: restore telemetry; if you fly without it, temporarily `dyn_notch_count` 4–5 (`bf-filters`).
- **Symptom:** E% grows at high throttle
  - Possible cause: long/noisy DShot lines, 600 kbit.
  - What to do: DShot300, shorter wires, ground next to the signal.

## references
- DShot RPM Filtering — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/DSHOT-RPM-Filtering | primary | A
- Betaflight CLI — Documentation | https://betaflight.com/docs/wiki/guides/current/Cli | primary | A
- Betaflight 4.5 rpm_filter.c (the weight, fade, the notch update) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/rpm_filter.c | primary | A
- Betaflight 4.5 drivers/dshot.c (eRPM → Hz, PT1, the error share) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/drivers/dshot.c | primary | A
- Betaflight 4.5 cli.c (`dshot_telemetry_info`) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/cli/cli.c | primary | A
- Orangebox — Blackbox log parser for Python | https://github.com/atomgomba/orangebox | secondary | B
- RPM Filter explained — Oscar Liang | https://oscarliang.com/rpm-filter/ | secondary | B

## checklist
- Before the changes `diff all` was made and saved to a file with the date
- The battery is connected, telemetry errors in the Motors tab are ≤ 1%
- `motor_poles` matches the number of motor magnets
- The motor frequency in hover is computed from the log
- `rpm_filter_min_hz` is below the minimum working frequency
- After `save` all the values are re-read with `get`
- The first flight after the changes: 30 s of hover, land, check the motor temperature
