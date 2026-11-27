---
id: bf-filters
title: "Filters"
level: L2
readingTime: 50 min
firmware: Betaflight 2025.12 (checked against 2025.12.5)
status: published
tags:
  - filters
  - Blackbox
  - tuning
  - diagnostics
  - PID
references:
  - title: "Betaflight CLI Documentation — Gyro & Filter Variables"
    url: "https://betaflight.com/docs/wiki/guides/current/Cli"
    tier: primary
    stack: betaflight
  - title: "Betaflight — PID Tuning tab: filter settings"
    url: "https://betaflight.com/docs/wiki/app/pid-tuning-tab#filter-settings"
    tier: primary
    stack: betaflight
  - title: "PID Tuning Tab — Filter Settings"
    url: "https://www.betaflight.com/docs/wiki/app/pid-tuning-tab#filter-settings"
    tier: primary
    stack: betaflight
related:
  - bf-blackbox
  - bf-pid
  - bf-rpm-filter
  - bf-cli
  - ctl-signals
  - f-frame-mech
  - bf-tuning-method
next:
  - bf-rpm-filter
source: content/betaflight/bf-filters.md
source_hash: 05f2c29e13a6
---

## summary

Filters sit between the gyro and the PID controller and decide what the controller “sees”: the useful motion of the frame, or motor noise, resonances and vibration as well. Without them the D term turns noise into motor jitter and heat; with too many, every filter adds delay, the aircraft becomes “mushy” and the stability margin melts away. This module goes through the filter chain of Betaflight 2025.12 (it is the same in 4.5) in the order in which the code applies it (LPF2 at downsampling → RPM notches → static notches → LPF1 → dynamic notch for the gyro; notch → LPF1 → LPF2 for the D term), explains every parameter with its default numbers, gives a tuning method based on the Blackbox spectrum with specific “enough” criteria, and shows where filters do **not** help (mechanics, propwash). The interactive part is the frequency response and group delay of the chain.

## theory

### What exactly is filtered and why

The gyro signal = frame motion (0–100 Hz, useful) + noise. The noise sources and where they sit in the spectrum (details are in the modules “Frame and vibration”, “Signals and spectra”):

{{diagram:fc-signal-path|Where the filters sit in the chain: between the gyro and the PID; everything they let through reaches the D term and the motors.}}

| Source | Frequency on a 5" 6S | Appearance on the spectrogram | What deals with it |
|---|---|---|---|
| Motor fundamental (imbalance) | 250–450 Hz in hover, up to 700+ on throttle | a sloped line that tracks the throttle | RPM filter |
| 2nd, 3rd harmonics (blades, aerodynamics) | ×2, ×3 | parallel lines | RPM filter (harmonics) |
| Frame / FC mount resonance | 100–300 Hz | a horizontal line | mechanics, dynamic notch, static notch |
| Broadband noise (play, bad bearings, electrical) | the whole range | a “cushion” | mechanics, LPF |
| Propwash | 20–80 Hz | bursts on sharp maneuvers | not filters: D term, mechanics, props |

**Other classes.** The frequencies in the table are for a 5" 6S. The motor fundamental in hover: 7" — 110–200 Hz (`f-frame-mech`, “Numbers”; a 1.4 kg 7" LR in hover — 110–130 Hz, the example in `bf-rpm-filter`), 10" — 80–100 Hz, 15" — 50–70 Hz (`f-frame-mech`). On 7–15" builds motor noise lies where a 5" has only propwash and frame motion, so the boundary “below 100 Hz is not a filter problem” does not apply to them. The order for 7" and larger: first `bf-rpm-filter` — `rpm_filter_min_hz` by class (7" — 70, 10" — 50, the “measure, then set” procedure is there too), then the steps of this module; lower `dyn_notch_min_hz` (default 100, range 20–250, `cli/settings.c`) below 100 only if the frame resonance found by tapping an arm (`f-frame-mech`) lies below 100 Hz. The sliders and LPF frequencies below are reference values for a 5"; on large aircraft they are changed only from the spectrum, one step at a time.

The main victim of noise is the **D term**: a derivative amplifies a signal in proportion to frequency (40 times more at 400 Hz than at 10 Hz), so the motors “buzz” and heat up, while P and I hardly notice the noise. Hence two chains: a gentle one for the gyro (it feeds all three terms) and a stricter one for D.

### Filter types and the cost of each

- **PT1** — a first-order filter: −3 dB at the cutoff frequency fc, then −20 dB/decade; the group delay at low frequencies ≈ 1/(2π·fc) (PT1 100 Hz → 1.6 ms; 250 Hz → 0.64 ms). The “cheapest” in delay.
- **PT2, PT3** — cascades of PT1: −40/−60 dB/decade, a delay of ×1.6/×2.2 relative to a PT1 of the same fc. They are used when noise above the band has to be cut off sharply at a moderate delay (the D term LPF is PT1 by default, and the type is changed with `*_lpf1_type`/`*_lpf2_type`: PT1, BIQUAD, PT2, PT3).
- **BIQUAD** (second-order, Butterworth) — steeper than PT1, with a delay between PT1 and PT2.
- **Notch** — a dip around a center frequency with a width set by Q (the higher the Q, the narrower); outside the band the delay is almost zero. That is why narrowband motor noise is properly cut with notches rather than by lowering the LPF.

The cost of filtering is delay; the cost of delay is phase margin (the module “Control theory”): with a total gyro+D chain delay of about 1–2 ms a good 5" tune holds P/D 30–50% higher than with 4–6 ms.

{{widget:filter-response}}

### The gyro chain in Betaflight 2025.12 (parameters; the real order in `filterGyro()`: LPF2 → RPM → static notches → LPF1 → dynamic notch)

1. **RPM filter** (`rpm_filter_harmonics = 3`, `rpm_filter_q = 500`, `rpm_filter_min_hz = 100`, `rpm_filter_fade_range_hz = 50`, `rpm_filter_lpf_hz = 150`, `rpm_filter_weights = 100,100,100`) — one notch per harmonic of every motor (3 harmonics × 4 motors = 12 notches), with the center taken from eRPM over bidirectional DShot (`dshot_bidir = ON`, `motor_poles = 14` for a 2207/2306 with 14 magnets). Q = 500 means a width of ≈ f/5: narrow and precise. `min_hz` — below this frequency no notch is applied (so as not to cut useful signal at low throttle), `fade_range_hz` — a smooth fade-in above min_hz. A separate module — “RPM filter”.
2. **Dynamic notch** (`dyn_notch_count = 3` (range 0–7; in 4.5 — 0–5), `dyn_notch_q = 300`, `dyn_notch_min_hz = 100`, `dyn_notch_max_hz = 600`): an FFT of the gyro finds the strongest peaks in the min..max range and places notches on them. It catches what the RPM filter does not know about — frame resonances. With the RPM filter, `count = 1–2` and `q = 300–500` are enough; without the RPM filter — `count = 4–5`, `q = 250–300` (wider). Why (a course guideline): with the RPM filter the motors are already notched out, and the dynamic notch is left with one or two frame resonances — extra notches only add delay, and a high Q makes each one narrow; without the RPM filter it also has to catch the motor harmonics, which move with the throttle — more and wider notches are needed. Start at the low end: `count = 1`, `q = 500` with the RPM filter; +1 to count only if a peak remains in the spectrum after the filters.
3. **LPF1** — dynamic by default: the cutoff slides with the throttle from `gyro_lpf1_dyn_min_hz = 250` to `gyro_lpf1_dyn_max_hz = 500` (`gyro_lpf1_dyn_expo` sets the curve); with `gyro_lpf1_static_hz` ≠ 0 and dyn_min = 0 — static. The type is `gyro_lpf1_type = PT1`.
4. **LPF2** — static `gyro_lpf2_static_hz = 500`, PT1: a safety anti-aliasing cutoff.
The static notches `gyro_notch1_hz/cutoff`, `gyro_notch2_hz/cutoff` (0 = off) are for a single known resonance that you do not want to leave to the dynamic notch.

Plus the hardware filter in the gyro chip (`gyro_hardware_lpf = NORMAL`) — on the ICM42688 it is the DLPF, and it already sits in the signal path before all the software filters.

### The D term chain

`dterm_lpf1_*` — dynamic by default (`dterm_lpf1_dyn_min_hz = 75`, `dterm_lpf1_dyn_max_hz = 150`, `dterm_lpf1_type = PT1`), `dterm_notch_hz/cutoff` (0 = off), `dterm_lpf2_static_hz = 150` (PT1). Two to three times lower than the gyro ones, because D amplifies high frequencies. It is the D filters that contribute most of the delay in the chain and are the first to “smear” the response.

### The sliders and when they are enough

`simplified_gyro_filter = ON`, `simplified_gyro_filter_multiplier = 100` and `simplified_dterm_filter_multiplier = 100` scale all the cutoff frequencies at once: 100 = the default values, 150 = 50% higher (less filtering, less delay), 50 = half as high. For a clean 5" with the RPM filter the practice is: gyro 100–150, D term 100–130. The slider is the first tool; the manual parameters are for when the spectrum shows a specific problem.

### Criteria for “filtered enough”

From the spectrum after the filters (the `gyroUnfilt` and `gyroADC` fields in the log give before/after; in 4.5 `debug_mode = GYRO_SCALED` served the same purpose, and the mode was removed in 2025.12): motor peaks ≤ 5–10 dB above the floor; no peaks above 10 dB in the 100–300 Hz band (resonances); the D term (`debug_mode = D_LPF` or `axisD` in the log) without high-amplitude “grass”. From the aircraft: the motors are warm after a flight, not hot (< 50–60 °C is tolerable to the hand); no buzzing in hover. From the response: bounce-back < 10–15%, no “mushiness”. All three criteria must be met together — otherwise the compromise has not been found.

### What filters do not fix

A peak that does not go away after balancing and the RPM filter is mechanical (the module “Frame and vibration”); a “cushion” of broadband noise is bearings, play, electrical interference; propwash is the D term and the props. Lowering the LPF below 150–200 Hz on a 5" to “hide” the mechanics is the road to a mushy aircraft and hot motors at the same time.

{{diagram:chart-filter-response|Frequency response: a biquad cuts twice as steeply as a PT1 at the same cutoff but adds more delay; a notch cuts out a narrow band and hardly touches the rest. The continuous-time formulas are accurate enough below ~1/4 of the loop rate.}}

### Place in the system

- **Receives:** the raw gyro with motor noise and frame resonances (`f-frame-mech`); eRPM for the RPM notches (`bf-rpm-filter`); the spectrum before and after the filters from a log (`bf-blackbox`, `ctl-signals`).
- **Provides:** the filtered gyro — to all three PID terms, and a separate, stricter chain — to the D term (`bf-pid-reg-in-bf`); the total delay, which determines how much P and D the tune can take (`bf-pid`, `ctl-theory`).
- **If you get it wrong here:** too little filtering → the D term amplifies noise, the motors buzz and heat up; in `bf-pid` this looks like “D is too high” although D was not touched. Too much filtering (the LPF lowered to hide the mechanics) → the delay grows, the response is “mushy”, bounce-back increases, and the tune no longer holds its previous P and D (`bf-pid`); the real cause is in `f-frame-mech`.

## practice

### Step 0. Preparation
ESCs with bidirectional DShot (BLHeli_32/Bluejay/AM32), `dshot_bidir = ON`, `motor_poles` per the number of magnets, the Motors tab: RPM from every motor, `E` errors ≤ 1 % (a course guideline, `bf-rpm-filter`). The mechanics per the checklist. Blackbox at 2 kHz or higher, the `gyroUnfilt` field enabled (`blackbox_disable_gyrounfilt = OFF`; in 4.5 `debug_mode = GYRO_SCALED` gave the same, 2025.12 does not have this mode). `diff all` is saved.

What the firmware changes by itself on an F4. The STM32F405, STM32F411 and STM32G47X targets (in 2025.12 also APM32F405/F407) have `USE_PID_DENOM_CHECK` enabled. If bidir DShot is enabled there, `validateAndFixGyroConfig()` in `config/config.c` rewrites `motor_pwm_protocol` DSHOT600 → **DSHOT300** when the configuration is loaded and sets `pid_process_denom` to no less than 2 if the gyro runs faster than 4 kHz (an 8 kHz gyro → a 4 kHz PID). On an F405 this does not happen with `cpu_overclock` from 216 MHz up. In `diff all` this shows up as “corrected” values that you did not enter. For the filters there is one consequence: at 1/4 of the PID rate Blackbox now logs at 1 kHz, not 2, and the spectrum above 500 Hz is not visible — for noise analysis set `blackbox_sample_rate = 1/2`. Look at the load in `status` (the `CPU:…%` line): the `LOAD` arming flag is set when, over one second, more than 1 % of the scheduler's task runs (except serial) started late (`cpu_late_limit_permille` = 10 ‰, `scheduler/scheduler.c`). The `CPU` percentage itself is not an arming threshold.

### Step 1. The baseline
```text
set dshot_bidir = ON
set motor_poles = 14
set simplified_gyro_filter = ON
set simplified_gyro_filter_multiplier = 100
set simplified_dterm_filter = ON
set simplified_dterm_filter_multiplier = 100
set dyn_notch_count = 2
set dyn_notch_q = 300
save
```
The log: 30 s of hover + slow passes + 3–4 sharp stick inputs with a stop + a smooth throttle sweep 20→100%.

### Step 2. Reading the spectrum
Blackbox Explorer → the gyro spectrogram (before and after the filters) for roll/pitch; PID Toolbox or your own Python (`data-python`). Note: the frequency of the fundamental in hover and its attenuation after the RPM filter; the remaining peaks; the D term noise.

### Step 3. Decisions by the table
- Motor peaks remain → check eRPM (`motor_poles`), `rpm_filter_harmonics = 3`, `rpm_filter_q` 500→400 (wider).
- A horizontal peak at 100–300 Hz → `dyn_notch_count` +1 or a static `gyro_notch1_hz` = the frequency, `cutoff` = the frequency × 0.7 (closer to the frequency if a motor line is nearby — covered in `f-frame-mech`); in parallel — the mechanics.
- The spectrum is clean, the motors are cool, the response is mushy → `simplified_gyro_filter_multiplier` 100→125→150, `simplified_dterm_filter_multiplier` 100→120, one step at a time with a log.
- The motors heat up with a clean gyro spectrum → look at D: `dterm_lpf1_dyn_max_hz` 20% lower or `dterm_lpf1_type = PT2`; reduce D.
- Nothing helps below 100 Hz → on a 5" this is not the filters: props, D, mechanics. On 7–15" the motor fundamental itself lies below 100 Hz — first check `rpm_filter_min_hz` by class (`bf-rpm-filter`).

### Step 4. Recording the result
A before/after log; a table “parameter — was — now — why — effect (dB, °C, bounce-back)” in the engineering folder; `diff all` in the config repository.

{{lesson:bf-tuning-method|So that a filter “before/after” does not turn out to be flight-to-flight scatter: a control flight, the ABBA order and a comparison of gyro noise and motor temperature across two logs.}}

### Lab
Before/after spectra with the frequencies and the attenuation in dB labeled; the decision table; the motor temperature before/after.

**Reference for self-check.** Compare your numbers with the module's thresholds: the motor peaks after the RPM filter are attenuated by ≥ 20 dB and stay no higher than 5–10 dB above the floor; there are no peaks above 10 dB in the 100–300 Hz band; the motors are warm after a flight (< 50–60 °C); bounce-back < 10–15 %. All three groups — spectrum, temperature, response — must be met together. The motor peaks were hardly attenuated — the RPM filter is not getting correct eRPM: check `dshot_bidir`, `motor_poles` and `E = 0%` in the Motors tab. The spectrum is clean but bounce-back grew and the response is “mushy” — there is too much filtering: raise the slider multipliers and remove unneeded static notches.

### Automatic log check
Decode the log with `blackbox_decode` and run the course grader: `python examples/blackbox-grader/check_bf_log.py LOG.01.csv --lab filters --motor-range <motorOutput from the log header>`. It prints PASS/FAIL for every check (filters) with the value, the threshold and an explanation; the thresholds are reference values for a 5", and they can be overridden with `--set` if you write down the reason. You can practice on synthetic data before using your own logs: `make_bf_fixture.py --kind noisy` (or `sluggish`, `oscillating`, `saturated`, `imbalanced`, `no_rpm`).

## diagnostics

- **Symptom:** the motors are hot after a short flight
  - Possible cause: the D term is noisy — the RPM filter is not working (no eRPM) or D is too high for a noisy aircraft.
  - What to do: `dshot_bidir`, the errors on the Motors tab, `motor_poles`; the D spectrum; reduce D or the D LPF; the mechanics.
- **Symptom:** the drone “rattles” in hover, a buzz is audible
  - Possible cause: a gyro peak gets through to the PID — a resonance or the RPM filter missing its target.
  - What to do: the spectrogram: sloped → RPM/polarity/poles; horizontal → notch + mechanics.
- **Symptom:** a screech and loss of control authority on a throttle punch
  - Possible cause: a resonance in the working RPM range, broadband noise at high eRPM.
  - What to do: a throttle sweep, find the frequency, a static notch; a higher `dyn_notch_max_hz` (up to 800) for fast props.
- **Symptom:** after tuning it became “mushy”, bounce-back grew
  - Possible cause: excessive filtering — the delay increased.
  - What to do: raise the slider multipliers and the D LPF; check whether there are unneeded static notches.
- **Symptom:** a “fuzzy” gyro on the spectrum, a wide band
  - Possible cause: the RPM telemetry is invalid (E > 0%), or mechanics (bearings, play).
  - What to do: the ESC firmware, `dshot_bidir`, the signal wires; inspect the motors.
- **Symptom:** the spectrum before the filters is clean, after — peaks at new frequencies
  - Possible cause: aliasing/a wrong logging rate, or a wrong `motor_poles` (the notches land off target and create artifacts).
  - What to do: log at the full rate, check the number of magnets, `debug_mode = RPM_FILTER`.

## references

- Betaflight CLI Documentation — Gyro & Filter Variables | https://betaflight.com/docs/wiki/guides/current/Cli | primary | A
- Betaflight — PID Tuning tab: filter settings | https://betaflight.com/docs/wiki/app/pid-tuning-tab#filter-settings | primary | A
- PID Tuning Tab — Filter Settings | https://www.betaflight.com/docs/wiki/app/pid-tuning-tab#filter-settings | primary | A
- Betaflight — Deep Dive (Filtering, Aliasing and Gyro Sync) | https://betaflight.com/docs/wiki/guides/current/Deep-Dive | primary | A
- Betaflight source — cli/settings.c (filter parameter names, ranges) | https://github.com/betaflight/betaflight/blob/master/src/main/cli/settings.c | primary | A

## checklist

- I know the order of the filters in the gyro and D term chains and the cost of each in ms
- The RPM filter works: eRPM is valid, the motor peaks went down by ≥ 20 dB
- The spectrum after the filters: peaks ≤ 5–10 dB, resonances found and dealt with
- The motors are warm, bounce-back < 15%, the response is not mushy — the three criteria together
- The decision table and the before/after logs are in the engineering folder
