---
id: bf-filters
title: "Filters"
level: L2
readingTime: 50 min
firmware: Betaflight 4.5+
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
next:
  - bf-rpm-filter
source: content/betaflight/bf-filters.md
source_hash: d8da04494915
---

## summary

Filters sit between the gyro and the PID controller and decide what the controller “sees”: the useful movement of the frame, or motor noise, resonances and vibration on top of it. Without them the D-term turns noise into motor jitter and heat; with too much, every filter adds delay, the aircraft becomes “mushy” and the stability margin melts away. This module walks through the Betaflight 4.5 filter chain in the order the code applies it (LPF2 when downsampling → RPM notch → static notches → LPF1 → dynamic notch for the gyro; notch → LPF1 → LPF2 for the D-term), explains each parameter with its default values, gives a method for tuning from the Blackbox spectrum with concrete “good enough” criteria, and shows where filters do **not** help (mechanics, propwash). The interactive part: the chain's frequency response and group delay.

## theory

### What exactly we filter and why

The gyro signal = frame movement (0–100 Hz, useful) + noise. Noise sources and where they sit in the spectrum (more in the “Frame and vibration” and “Signals and spectra” modules):

{{diagram:fc-signal-path|Where the filters sit in the chain: between the gyro and the PID; whatever they let through ends up in the D-term and on the motors.}}

| Source | Frequency on a 5" 6S | Look on the spectrogram | Cure |
|---|---|---|---|
| Motor fundamental (imbalance) | 250–450 Hz at hover, up to 700+ at throttle | a slanted line that follows throttle | RPM filter |
| 2nd, 3rd harmonics (blades, aerodynamics) | ×2, ×3 | parallel lines | RPM filter (harmonics) |
| Frame / FC mount resonance | 100–300 Hz | a horizontal line | mechanics, dynamic notch, static notch |
| Broadband noise (play, bad bearings, electrical) | the whole range | a “cushion” | mechanics, LPF |
| Propwash | 20–80 Hz | bursts during sharp moves | not filters: D-term, mechanics, props |

The main victim of noise is the **D-term**: the derivative amplifies the signal in proportion to frequency (40 times more at 400 Hz than at 10 Hz), so the motors “hum” and heat up, while P and I barely notice the noise. Hence two chains: a gentle one for the gyro (it feeds all three terms) and a harsher one for D.

### Filter types and the price of each

- **PT1** — a first-order filter: −3 dB at the cutoff frequency fc, then −20 dB/decade; group delay at low frequencies ≈ 1/(2π·fc) (PT1 100 Hz → 1.6 ms; 250 Hz → 0.64 ms). The “cheapest” in delay.
- **PT2, PT3** — cascades of PT1: −40/−60 dB/decade, delay ×1.6/×2.2 relative to a PT1 with the same fc. Used when you need to cut noise above the band sharply at moderate delay (the D-term LPF defaults to PT1 in 4.5; the type is changed with `*_lpf1_type`/`*_lpf2_type`: PT1, BIQUAD, PT2, PT3).
- **BIQUAD** (2nd order, Butterworth) — steeper than PT1, delay between PT1 and PT2.
- **Notch** — a dip around the center frequency with a width set by Q (the higher Q, the narrower); outside the band the delay is almost zero. That's why narrowband motor noise is properly cut with notches rather than by lowering the LPF.

The price of filtering is delay; the price of delay is phase margin (the “Control theory” module): with a total gyro+D chain delay of about 1–2 ms, a good 5" tune holds P/D 30–50% higher than with 4–6 ms.

{{widget:filter-response}}

### The gyro chain in Betaflight 4.5 (parameters; the actual order in `filterGyro()`: LPF2 → RPM → static notches → LPF1 → dynamic notch)

1. **RPM filter** (`rpm_filter_harmonics = 3`, `rpm_filter_q = 500`, `rpm_filter_min_hz = 100`, `rpm_filter_fade_range_hz = 50`, `rpm_filter_lpf_hz = 150`, `rpm_filter_weights = 100,100,100`) — one notch per harmonic per motor (3 harmonics × 4 motors = 12 notches), with the center taken from eRPM via bidirectional DShot (`dshot_bidir = ON`, `motor_poles = 14` for a 2207/2306 with 14 magnets). Q = 500 means a width of ≈ f/5: narrow and precise. `min_hz` — below this frequency no notch is placed (so the useful signal isn't cut at low throttle), `fade_range_hz` — a smooth fade-in above min_hz. There's a separate module, “RPM filter”.
2. **Dynamic notch** (`dyn_notch_count = 3`, `dyn_notch_q = 300`, `dyn_notch_min_hz = 100`, `dyn_notch_max_hz = 600`): an FFT on the gyro finds the strongest peaks in the min..max range and puts notches on them. It catches what the RPM filter doesn't know about — frame resonances. With the RPM filter, `count = 1–2` and `q = 300–500` is enough; without the RPM filter — `count = 4–5`, `q = 250–300` (wider).
3. **LPF1** — dynamic by default: the cutoff slides with throttle from `gyro_lpf1_dyn_min_hz = 250` to `gyro_lpf1_dyn_max_hz = 500` (`gyro_lpf1_dyn_expo` sets the curve); with `gyro_lpf1_static_hz` ≠ 0 and dyn_min = 0 — static. Type `gyro_lpf1_type = PT1`.
4. **LPF2** — static `gyro_lpf2_static_hz = 500`, PT1: a safety anti-aliasing cutoff.
Static notches `gyro_notch1_hz/cutoff`, `gyro_notch2_hz/cutoff` (0 = off) — for one known resonance you don't want to hand to the dynamic notch.

Plus the gyro's hardware filter in the chip (`gyro_hardware_lpf = NORMAL`) — on an ICM42688 this is the DLPF, and it already sits in the signal path before all the software filters.

### The D-term chain

`dterm_lpf1_*` — dynamic by default (`dterm_lpf1_dyn_min_hz = 75`, `dterm_lpf1_dyn_max_hz = 150`, `dterm_lpf1_type = PT1`), `dterm_notch_hz/cutoff` (0 = off), `dterm_lpf2_static_hz = 150` (PT1). Two to three times lower than the gyro ones, because D amplifies high frequencies. It's the D filters that contribute most of the chain's delay and are the first to “blur” the response.

### Sliders and when they're enough

`simplified_gyro_filter = ON`, `simplified_gyro_filter_multiplier = 100` and `simplified_dterm_filter_multiplier = 100` scale all the cutoff frequencies at once: 100 = defaults, 150 = 50% higher (less filtering, less delay), 50 = half. For a clean 5" with the RPM filter, the practice is: gyro 100–150, D-term 100–130. The slider is the first tool; manual parameters are for when the spectrum shows a specific problem.

### “Filtered enough” criteria

From the post-filter spectrum (a log with `debug_mode = GYRO_SCALED` gives before/after): motor peaks ≤ 5–10 dB above the floor; no peaks above 10 dB in the 100–300 Hz band (resonances); D-term (`debug_mode = D_LPF` or `axisD` in the log) without high-amplitude “grass”. From the aircraft: motors warm, not hot, after a flight (< 50–60 °C, bearable to the touch); no humming at hover. From the response: bounce-back < 10–15%, no “mush”. All three criteria must hold together — otherwise you haven't found the compromise.

### What filters don't cure

A peak that doesn't go away after balancing and the RPM filter is mechanical (the “Frame and vibration” module); a broadband noise “cushion” is bearings, play, electrical interference; propwash is the D-term and props. Lowering the LPF below 150–200 Hz on a 5" to “hide” mechanics is the road to a mushy aircraft and hot motors at the same time.

{{diagram:chart-filter-response|Frequency response: a biquad cuts twice as steeply as PT1 at the same cutoff, but adds more delay; a notch cuts out a narrow band and barely touches the rest. Continuous-time formulas — accurate enough below ~1/4 of the loop rate.}}

## practice

### Step 0. Preparation
ESCs with bidirectional DShot (BLHeli_32/Bluejay/AM32), `dshot_bidir = ON`, `motor_poles` per the magnet count, Motors tab: RPM from every motor, errors `E = 0%`. Mechanics per the checklist. Blackbox at 2 kHz or higher, `debug_mode = GYRO_SCALED` (4.5 only; in 2025.12 the mode was removed — the unfiltered gyro is logged in the `gyroUnfilt` field). `diff all` saved.

### Step 1. Baseline
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
Log: 30 s of hover + slow passes + 3–4 sharp stick inputs with a stop + a smooth throttle sweep 20→100%.

### Step 2. Reading the spectrum
Blackbox Explorer → gyro spectrogram (before and after filters) on roll/pitch; PID Toolbox or your own Python (`data-python`). Note: the fundamental's frequency at hover and how much it's attenuated after RPM; residual peaks; D-term noise.

### Step 3. Decisions from the table
- Motor peaks remain → check eRPM (`motor_poles`), `rpm_filter_harmonics = 3`, `rpm_filter_q` 500→400 (wider).
- A horizontal peak at 100–300 Hz → `dyn_notch_count` +1 or a static `gyro_notch1_hz` = the frequency, `cutoff` = frequency × 0.7; in parallel — mechanics.
- Clean spectrum, cold motors, mushy response → `simplified_gyro_filter_multiplier` 100→125→150, `simplified_dterm_filter_multiplier` 100→120, one step at a time with a log.
- Motors heat up with a clean gyro spectrum → look at D: `dterm_lpf1_dyn_max_hz` 20% lower or `dterm_lpf1_type = PT2`; lower D.
- Nothing helps below 100 Hz → it's not the filters: props, D, mechanics.

### Step 4. Locking it in
Before/after logs; a “parameter — was — now — why — effect (dB, °C, bounce-back)” table in the engineering folder; `diff all` into the config repo.

### Lab
Before/after spectra with labeled frequencies and attenuation in dB; a decision table; motor temperature before/after.

### Automatic log check
Decode the log with `blackbox_decode` and run the course grader: `python examples/blackbox-grader/check_bf_log.py LOG.01.csv --lab filters --motor-range <motorOutput from the log header>`. It reports PASS/FAIL for each check (filters) with the value, the threshold and an explanation; the thresholds are guidelines for a 5", and you can override them with `--set`, recording the reason. Before you have your own logs, you can practice on synthetic ones: `make_bf_fixture.py --kind noisy` (or `sluggish`, `oscillating`, `saturated`, `imbalanced`, `no_rpm`).

## diagnostics

- **Symptom:** motors are hot after a short flight
  - Possible cause: the D-term is noisy — the RPM filter isn't working (no eRPM) or D is too high for a noisy aircraft.
  - What to do: `dshot_bidir`, errors on the Motors tab, `motor_poles`; the D spectrum; lower D or the D-LPF; mechanics.
- **Symptom:** the drone “rattles” at hover, you can hear a hum
  - Possible cause: a gyro peak gets through to the PID — a resonance or the RPM filter missing.
  - What to do: spectrogram: slanted → RPM/polarity/poles; horizontal → notch + mechanics.
- **Symptom:** a squeal on sharp throttle, control sags
  - Possible cause: a resonance within the operating RPM range, broadband noise at high eRPM.
  - What to do: throttle sweep, find the frequency, static notch; raise `dyn_notch_max_hz` (up to 800) for fast props.
- **Symptom:** after tuning it got “mushy”, bounce-back grew
  - Possible cause: excessive filtering — the delay went up.
  - What to do: raise the slider multipliers, the D-LPF; check for unneeded static notches.
- **Symptom:** a “fuzzy” gyro on the spectrum, a wide band
  - Possible cause: RPM telemetry is invalid (E > 0%), or mechanics (bearings, play).
  - What to do: ESC firmware, `dshot_bidir`, signal wires; inspect the motors.
- **Symptom:** the spectrum before the filters is clean, after — peaks at new frequencies
  - Possible cause: aliasing/wrong log rate, or a wrong `motor_poles` (the notches land off target and create artifacts).
  - What to do: log at the full rate, check the magnet count, `debug_mode = RPM_FILTER`.

## references

- Betaflight CLI Documentation — Gyro & Filter Variables | https://betaflight.com/docs/wiki/guides/current/Cli | primary | A
- Betaflight — PID Tuning tab: filter settings | https://betaflight.com/docs/wiki/app/pid-tuning-tab#filter-settings | primary | A
- PID Tuning Tab — Filter Settings | https://www.betaflight.com/docs/wiki/app/pid-tuning-tab#filter-settings | primary | A
- Betaflight — Deep Dive (Filtering, Aliasing and Gyro Sync) | https://betaflight.com/docs/wiki/guides/current/Deep-Dive | primary | A
- Betaflight source — cli/settings.c (filter parameter names, ranges) | https://github.com/betaflight/betaflight/blob/master/src/main/cli/settings.c | primary | A

## checklist

- I know the filter order in the gyro and D-term chains and the price of each in ms
- The RPM filter works: eRPM is valid, motor peaks dropped by ≥ 20 dB
- Post-filter spectrum: peaks ≤ 5–10 dB, resonances found and dealt with
- Motors warm, bounce-back < 15%, response not mushy — all three criteria together
- Decision table and before/after logs in the engineering folder
