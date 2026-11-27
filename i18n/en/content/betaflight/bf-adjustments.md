---
id: bf-adjustments
title: "In-flight adjustments: the Adjustments tab, `adjrange` and the VTX on a switch"
level: L2
readingTime: 45 min
firmware: Betaflight 2025.12 (checked against 2025.12.5); the lab was captured on the 4.5.x source (branch 4.5-maintenance, 7dcc851; version.h 4.5.6, the latest release is 4.5.5)
status: published
added: 2026-11-14
tags:
  - Betaflight
  - adjustments
  - adjrange
  - VTX
  - profiles
  - CLI
related:
  - bf-modes-osd
  - bf-pid
  - bf-blackbox
  - bf-cli
  - link-vtx
  - bf-setup-scratch
  - bf-tuning-method
  - bf-rates-rc
next:
  - bf-blackbox
source: content/betaflight/bf-adjustments.md
source_hash: 8080b48198ee
---

## summary
The Adjustments tab and the CLI command `adjrange` let you change PIDs, rates and profiles from the radio — without a laptop, right in the air. This is convenient and dangerous at the same time: a change applies immediately, it is not written to EEPROM by itself, and the function number in the CLI does not match the number in the source. This module goes through `fc/rc_adjustments.c` from Betaflight 2025.12 (the file differs from 4.5 only by the added function 31 LED_DIMMER): 30 slots, two channels per slot, three modes (step, absolute, select), the full function table with CLI numbers, the 500 ms timing and the ±200 µs thresholds, saving with the sticks, the OSD and Blackbox. Separately — the `vtx` command for the power, band and channel of the video transmitter on a switch, `vtxtable` and `vtx_low_power_disarm`. The lab: a Python model that repeats the firmware logic (the run and its output are in the text), then the bench without props and a short hover session with a D adjustment and a save.

## theory
### Why this is needed and what it cannot do
Typical jobs: tweak P/D/FF in the field when there is no laptop; switch rate profiles for different pilots; an OSD profile “race / long range / empty”; the LED strip color; VTX power “low on the bench, working in the air”. The last one is served by a separate command, `vtx`, not by `adjrange`.

What Adjustments **cannot do** (neither in 4.5 nor in 2025.12): switch the PID profile (there is no such function, and no such mode in Modes either), change D max (`d_max_*`; in 4.5 it was `d_min_*` that was unavailable), filters, the `simplified_*` sliders, anti-gravity, the VTX band/channel/power. The PID profile changes only while disarmed: with the sticks (throttle down + yaw left + roll left / pitch up / roll right → profile 1/2/3, `fc/rc_controls.c`), from the OSD menu, with the CLI command `profile` or through `auto_profile_cell_count`. In flight — not at all. The profiles that are switched in the air: rates (function 12), OSD (29), LED (30); from 2025.12 the strip brightness changes the same way (31, LED_DIMMER).

### The two-channel model: slot, range, function
There are **30** slots (`MAX_ADJUSTMENT_RANGE_COUNT 30`, indices 0…29; the official In-flight Adjustments page says “12” — that is outdated). Each slot stores:
- **the range channel** (`auxChannelIndex`, AUX1 = 0) and the range `start..end` (900–2100, step 25, as for `aux`). The slot is active if `start ≤ channel < end` (the end is not included, `isRangeActive()` in `fc/rc_modes.c`);
- **the function** — a number from the table below;
- **the adjustment channel** (`auxSwitchChannelIndex`, AUX1 = 0) — the switch or pot that changes the value. It may be the same as the range channel;
- `center` and `scale` — for absolute mode.

All active slots are processed at the same time: you can turn four parameters with four channels. An inactive slot changes nothing, so the simplest way to have a “safe position” of the selector is to leave it without a slot. Adjustments are processed in the RC receive task (`fc/core.c`), **both armed and disarmed**, but not in CLI mode and not with PARALYZE active while disarmed.

### Three modes
- **Step (STEP)** — `center = 0`, the function is not from the select group. The adjustment channel above `mid_rc + 200` (1700 µs with `mid_rc` 1500) → +1, below `mid_rc − 200` (1300) → −1. The step equals 1 for all functions. While held, the value repeats **every 500 ms** (`RESET_FREQUENCY_2HZ`); a return to center “re-arms” the slot immediately, so quick taps are faster than holding. The beeper: 2 short — up, 1 equally short — down (`beeperConfirmationBeeps(2)` / `(1)`).
- **Absolute (ABSOLUTE)** — `center ≠ 0`, a step function. The value = `center + (rc − 1500) × scale / 500` (C integer division, truncates toward zero), applied on every change of the channel. A pot at 1000 gives `center − scale`, at 2000 — `center + scale`. While the slot is inactive, the “last channel value” is reset to 0 — at the moment the slot turns on, the value **jumps** to the pot position.
- **Select (SELECT)** — functions 12, 24, 25, 29, 30 (in 2025.12 also 31). The 900–2099 range is divided into N equal parts: `position = (rc − 900) / (1200 / N)`. RATE_PROFILE: N = 3, or 6 with `rate_6pos_switch = ON` (but there are 4 rate profiles — positions 5–6 have nothing to switch to). OSD_PROFILE: N = 3, position + 1 is written (`osd_profile` 1…3). LED_PROFILE: N = 3 (RACE / BEACON / STATUS). PID_AUDIO: N = 7. HORIZON_STRENGTH: N = 255.

Limits: P/I/D 0–200 (although `set p_roll` accepts up to 250), F 0–2000 (`set f_roll` — up to 1000), RC rate 1–255, expo 0–100, super rate 0–255, `thr_expo` 0–100, `feedforward_transition` 1–100.

### The 2025.12 function table: CLI number ≠ enum number
The CLI number is the position in the `defaultAdjustmentConfigs[]` array plus 1, not the value of `adjustmentFunction_e`. In the enum, positions 25–28 hold ROLL/PITCH RC RATE/EXPO, which are not in the array, so from number 25 on everything is shifted by 4. The table below was printed by the lab script from the 4.5.x source (branch `4.5-maintenance`, commit `7dcc851`: `version.h` says 4.5.6, but there is no such release; the latest release is 4.5.5, and the `src/` code matches it except for the version number in `version.h`) and checked against 2025.12.5: rows 1–30 match, and row 31 was added in 2025.12.

| CLI | Function | Mode | What it changes | Code in Blackbox |
|---|---|---|---|---|
| 0 | none | — | — | — |
| 1 | RC_RATE | step/abs. | `roll_rc_rate` and `pitch_rc_rate` | 25, 26 |
| 2 | RC_EXPO | step/abs. | `roll_expo` and `pitch_expo` | 27, 28 |
| 3 | THROTTLE_EXPO | step/abs. | `thr_expo` | 3 |
| 4 | PITCH_ROLL_RATE | step/abs. | `pitch_srate` and `roll_srate` | 13, 14 |
| 5 | YAW_RATE | step/abs. | `yaw_srate` | 5 |
| 6 | PITCH_ROLL_P | step/abs. | `p_pitch` and `p_roll` | 15, 18 |
| 7 | PITCH_ROLL_I | step/abs. | `i_pitch` and `i_roll` | 16, 19 |
| 8 | PITCH_ROLL_D | step/abs. | `d_pitch` and `d_roll` (in 2025.12 this is the base D, in 4.5 — the peak) | 17, 20 |
| 9 | YAW_P | step/abs. | `p_yaw` | 9 |
| 10 | YAW_I | step/abs. | `i_yaw` | 10 |
| 11 | YAW_D | step/abs. | `d_yaw` | 11 |
| 12 | RATE_PROFILE | select 3/6 | rate profile | 12 |
| 13 | PITCH_RATE | step/abs. | `pitch_srate` | 13 |
| 14 | ROLL_RATE | step/abs. | `roll_srate` | 14 |
| 15 | PITCH_P | step/abs. | `p_pitch` | 15 |
| 16 | PITCH_I | step/abs. | `i_pitch` | 16 |
| 17 | PITCH_D | step/abs. | `d_pitch` | 17 |
| 18 | ROLL_P | step/abs. | `p_roll` | 18 |
| 19 | ROLL_I | step/abs. | `i_roll` | 19 |
| 20 | ROLL_D | step/abs. | `d_roll` | 20 |
| 21 | RC_RATE_YAW | step/abs. | `yaw_rc_rate` | 21 |
| 22 | PITCH_ROLL_F | step/abs. | `f_pitch` and `f_roll` | 30, 31 |
| 23 | FEEDFORWARD_TRANSITION | step/abs. | `feedforward_transition` | 23 |
| 24 | HORIZON_STRENGTH | select 255 | `horizon_limit_sticks` (the level D) | 24 |
| 25 | PID_AUDIO | select 7 | PID audio mode (if built in) | — |
| 26 | PITCH_F | step/abs. | `f_pitch` | 30 |
| 27 | ROLL_F | step/abs. | `f_roll` | 31 |
| 28 | YAW_F | step/abs. | `f_yaw` | 32 |
| 29 | OSD_PROFILE | select 3 | `osd_profile` 1…3 | — |
| 30 | LED_PROFILE | select 3 | `ledstrip_profile` | — |
| 31 | LED_DIMMER (from 2025.12) | select 100 | LED strip brightness, position = percent | — |
| 32–35 | empty (in 4.5 — 31–34) | — | the CLI accepts it, it does nothing | — |

The combined functions (1, 2, 4, 6, 7, 8, 22) change **two axes** at once and write two events. HORIZON_STRENGTH historically (in both 4.5 and 2025.12) writes to `pid[PID_LEVEL].D`, that is to `horizon_limit_sticks`, not to `horizon_level_strength`. In 2025.12 `d_roll` is the base D (30 by default), and the top of dynamic D is `d_max_roll` (40). A D step moves only the base; `d_max_*` stays in place, and when the base reaches it, the dynamic D boost disappears (`pid_init.c`: the boost exists only while `d_max` > `d`). In 4.5 the meaning was reversed: `d_roll` was the top (40), the base was `d_min_roll` (30), and a D step raised only the top. Function 31 LED_DIMMER (select, 100 positions) appeared in 2025.12. The SIMPLIFIED_MASTER_MULTIPLIER function described on betaflight.com under number 31 exists only in `master`, and there it is number 32 (31 is LED_DIMMER).

### The OSD profile on a switch (function 29)
The select function 29 OSD_PROFILE is the same for 4.5 and 2025.12; the CLI number is the index in `defaultAdjustmentConfigs[]` plus 1 (element [28]), in the enum it is `ADJUSTMENT_OSD_PROFILE` = 33, and CLI number 33 leads to a zeroed array entry (function NONE) and does nothing. The channel is divided into 3 positions of 400 µs, `applySelectAdjustment()` calls `changeOsdProfileIndex(position + 1)`, that is, it writes `osd_profile` 1…3 to RAM and immediately rebuilds the list of visible elements. A typical line for the `bf-modes-osd` layout (a three-position, non-momentary switch on AUX4, index 3), slot 3: `adjrange 3 0 3 900 2100 29 3 0 0` — 988 / 1500 / 2012 µs give profiles 1 / 2 / 3. In step 7 below the same slot 3 sits on AUX6 together with the rate profile, because AUX4 there is momentary (it would bring back profile 2) — take one variant. The course reference is a slot range of 900–2100: for such a “permanent” slot `setConfigDirtyIfNotPermanent()` does not set the unsaved-changes flag, while with a narrow range the flag is set on any change of the adjustment channel value while the slot is active (and at the moment of entering the range), even if the profile did not change (and then the `stats_total_*` counters are not saved). There are no beeps, no Blackbox event and no line in `osd_adjustment_range_pos`; the confirmation is the `osd_profile_name_pos` element in all three profiles: it will show the profile name or `OSD_1`…`OSD_3`. What exactly changes when the profile changes — profile bits 11–13 in every `osd_*_pos` — is covered in the module on modes and the OSD.

{{lesson:bf-modes-osd|How the `osd_*_pos` bits are arranged, which elements are visible in which OSD profile and how to build three profiles “full / race / recording”.}}

### Nothing is saved by itself
An adjustment changes the value in RAM and marks the config “dirty” (`setConfigDirty()`). Power off — the change is gone. Ways to save:
1. **Sticks while disarmed**: throttle down + yaw left + pitch down + roll right (`THR_LO + YAW_LO + PIT_LO + ROL_HI`, `fc/rc_controls.c`) → `saveConfigAndNotify()`: EEPROM write, re-read, one beep. No reboot. “Down” is ≤ `min_check` (1050), “up” is ≥ `max_check` (1900); a pitch stick at 1060 turns the gesture into “PID profile 3”.
2. **CLI**: `get d_roll` will show the new value (the CLI reads RAM), then `save`.
3. **Betaflight App**: first refresh the tab (Refresh), then Save — otherwise Save will write the old values loaded before the adjustment.

### Feedback: OSD and Blackbox
The OSD element `osd_adjustment_range_pos` (hidden by default) shows “NAME: value” for 2 s after a change (`VALUE_DISPLAY_LATENCY_MS 2000`), for example `PITCH/ROLL D:  41`. For a combined function the value of the second axis (roll) is shown. A change of rate profile or OSD profile is not shown by this element (the rate profile has an element of its own). LED_PROFILE and LED_DIMMER have the labels “LED PROFILE” and “LED DIMMER” from 2025.12 on; in 4.5 `adjustmentLabels[]` ends at “OSD PROFILE” — there, do not rely on the element for LED_PROFILE. Without this element the pilot adjusts blind — count the beeps.

In Blackbox every change is written as a `FLIGHT_LOG_EVENT_INFLIGHT_ADJUSTMENT` event: the function code (the **enum** value, not the CLI number — see the last column of the table) and the new value. It is convenient for matching “what I turned” against the response in the log.

{{lesson:bf-tuning-method|How to turn an adjustment slot into a fair A/B: segment boundaries from the `INFLIGHT_ADJUSTMENT` events, the ABBA order and comparing two logs with a script.}}

### The VTX on a switch: the `vtx` command
`vtx <index> <aux> <band> <channel> <power> <start> <end>` — 10 slots (`MAX_CHANNEL_ACTIVATION_CONDITION_COUNT`), AUX1 = 0, 0 in band/channel/power means “do not touch”. `power` is the index of a VTX table row (1 = the minimum), not mW. The logic of `vtxUpdateActivatedChannel()` (`io/vtx_control.c`):
- the slots are checked in order, the **first** matching one is applied, and the loop breaks. But the slot applied last time (`lastIndex`) is skipped, and the function is called on every RC frame: if two slots are active, they **alternate** frame by frame and both take effect (two power slots with different values will “yank” the power back and forth);
- the band and channel change only **before the first arm**: after arming a `locked` latch is set until reboot (so as not to move onto someone else's frequency in flight);
- the power changes always, including in flight.

`vtxtable` defines what the indices mean: `vtxtable bands`, `channels`, `band <n> <name> <letter> FACTORY|CUSTOM <frequencies…>`, `powerlevels`, `powervalues` (the code for the specific VTX), `powerlabels` (up to 3 characters, for the OSD). Without a table SmartAudio/Tramp are not controlled (details — the module on the VTX).

`vtx_low_power_disarm` (OFF / ON / UNTIL_FIRST_ARM, OFF by default): while disarmed the power is forced to the 1st row of the table, except in the failsafe case. ON — always while disarmed; UNTIL_FIRST_ARM — only until the first arm. This setting overrides the `vtx` slots as well. The `VTX PIT MODE` mode (Modes) and `vtx_pit_mode_freq` are a separate pit mode mechanism; SmartAudio 1.0/2.0 can enter pit only at power-up.

Legality: power and frequencies are limited by the country's rules (in the EU without a license — on the order of 25 mW EIRP in 5.8 GHz; beyond that — under an amateur radio license). A “400 mW” switch does not make 400 mW legal.

### Reference table
| Command / variable | Default | Range | Meaning |
|---|---|---|---|
| `adjrange <i> 0 <ch> <start> <end> <fn> <adj ch> [<center> <scale>]` | empty | i 0–29, fn 0–34 (4.5) / 0–35 (2025.12); do not use 0: in a non-empty slot it indexes `defaultAdjustmentConfigs[−1]`, outside the array | an adjustment slot; the second argument is the former “slot”, always 0 |
| `rate_6pos_switch` | OFF | OFF/ON | 6 positions instead of 3 for function 12 |
| `osd_adjustment_range_pos` | hidden | 0…`OSD_POSCFG_MAX` | the position of the adjustment OSD element |
| `osd_profile` | 1 | 1–3 | the active OSD profile (function 29 writes here) |
| `ledstrip_profile` | STATUS (RACE without `LED_STRIP_STATUS_MODE`) | RACE/BEACON/STATUS | the LED profile (function 30) |
| `vtx <i> <aux> <band> <ch> <power> <start> <end>` | empty | i 0–9 | VTX band/channel/power by a switch |
| `vtx_band` / `vtx_channel` | 0 / 0 | 0–8 / 0–8 | the row and column of the VTX table, 0 = not set |
| `vtx_power` | 0 | 0–7 | the power index in the table, 1 = the minimum |
| `vtx_freq` | 0 | 0–5999 MHz | the frequency directly with `vtx_band = 0` |
| `vtx_pit_mode_freq` | 0 | 0–5999 MHz | the frequency in pit mode |
| `vtx_low_power_disarm` | OFF | OFF/ON/UNTIL_FIRST_ARM | minimum power while disarmed |
| `vtx_halfduplex` / `vtx_softserial_alt` | ON / OFF | OFF/ON | the SmartAudio/Tramp line |
| `vtxtable …` | from the manufacturer | bands ≤ 8, channels ≤ 8, powerlevels ≤ 8 | what the band/channel/power indices mean |
| `profile` / `rateprofile` | 0 / 0 | 0–3 | the PID / rate profile from the CLI |

{{diagram:bf-adjustments-flow|A slot is enabled by the range channel, the function is taken from `defaultAdjustmentConfigs[N − 1]`, the mode depends on `center` and the function type; the result lives in RAM until a stick save or Save in the app.}}

### Dangers
- **P in the air.** +5 to P on a small quad can give oscillations within 1–2 s. Change by 1–2 steps, with 10–15 s of flight between steps.
- **Two axes at once.** Function 8 changes D on both pitch and roll; if you are tuning one axis — take 17 or 20.
- **An accidental switch.** A step switch that is not centered at power-up “steps” every 500 ms without stopping. Enable the switch position warning on the radio and use a momentary 3-position switch.
- **The pot jump** in absolute mode when the slot turns on.
- **Sticks**: the CMS menu and saving are on the sticks too; the save gesture works only while disarmed.
- **VTX power**: a “high power” slot on a switch forgotten in the upper position on the bench heats the VTX with no airflow.

### Place in the system

- **Receives:** the AUX channel positions from the RC receive task and ranges of the same kind as for `aux` (`bf-modes-osd`); the meaning of the band, channel and power indices — from the VTX table (`link-vtx`).
- **Provides:** PID gains and rates changed in RAM — to the controller and the stick chain (`bf-pid`, `bf-rates-rc`); an event with the function code and the new value — to the log (`bf-blackbox`); the profile and brightness of the strip (`bf-led-buzzer`).
- **If you get it wrong here:** you did not save the adjustment with the sticks → after power-off the value is gone, the next flight runs on the old D although the tuning table has the new one written down (`bf-pid`; the check is `get` in `bf-cli`). A step switch off center → P grows every 500 ms, and oscillations appear that look like a bad tune; the adjustment events in the log give the cause away (`bf-blackbox`).

## practice
The main path is a Python model that repeats the firmware logic. Betaflight SITL cannot be built in this environment (the session permission policy), so the script reads the source and reproduces `processStepwiseAdjustments()`, `processContinuosAdjustments()`, `vtxUpdateActivatedChannel()` and the stick parsing. Everything in the output below is a real run on the 4.5-maintenance source. The logic of these functions has not changed in 2025.12 (the diff of `rc_adjustments.c` between 4.5.3 and 2025.12.5 is only LED_DIMMER and the labels), but `d_roll`/`d_pitch` in 2025.12 are the base D with defaults of 30/34, not the peak 40/46: the same run of step 2 would start there from 30/34.

### Step 1. The function table from the source
The script `bf-adjustments.adj_lab.py` (the course working folder, stage 6) parses `enum adjustmentFunction_e` and the `defaultAdjustmentConfigs[]` array with regular expressions:

```
python3 -I bf-adjustments.adj_lab.py ~/src/betaflight-4.5/src/main
```

```text
enum adjustmentFunction_e: 35 names, ADJUSTMENT_FUNCTION_COUNT = 35
defaultAdjustmentConfigs[]: 34 slots, 30 initialised; CLI accepts 0..34
 24 | HORIZON_STRENGTH                  | SELECT |  255 | 24
 25 | PID_AUDIO                         | SELECT | ARRAYLEN(pidAudioPositionToModeMap) | 29  <- CLI != enum
 26 | PITCH_F                           | STEP   |    1 | 30  <- CLI != enum
 29 | OSD_PROFILE                       | SELECT |    3 | 33  <- CLI != enum
 30 | LED_PROFILE                       | SELECT |    3 | 34  <- CLI != enum
 31 | NONE (zero-filled)                | STEP   |    0 |  0  <- CLI != enum
not reachable from adjrange: ['ROLL_RC_RATE', 'PITCH_RC_RATE', 'ROLL_RC_EXPO', 'PITCH_RC_EXPO']
```

The conclusion (4.5-maintenance): from number 25 on CLI ≠ enum, and numbers 31–34 are accepted but empty. The same script on the 2025.12 branch prints `31 | LED_DIMMER | SELECT | 100 | 35`, and 32–35 remain empty.

### Step 2. Step mode and timing
The slot `adjrange 0 0 1 900 1300 8 3 0 0`: AUX2 down enables PITCH_ROLL_D, AUX4 is a momentary switch. The model ticks every 10 ms:

```python
if now >= st["timeoutAt"]:
    st["timeoutAt"], st["ready"] = now + 500, True
if rc > MIDRC + 200:   delta = 1
elif rc < MIDRC - 200: delta = -1
else:
    st["ready"], st["timeoutAt"] = True, now + 500   # centre re-arms at once
    continue
```

```text
t=  200 ms  AUX4=2000  d_pitch=47 d_roll=41  beep 2 short  OSD 'PITCH/ROLL D:  41'
t=  700 ms  AUX4=2000  d_pitch=48 d_roll=42  beep 2 short  OSD 'PITCH/ROLL D:  42'
t= 1200 ms  AUX4=2000  d_pitch=49 d_roll=43  beep 2 short  OSD 'PITCH/ROLL D:  43'
t= 1690 ms  AUX4=2000  d_pitch=50 d_roll=44  beep 2 short  OSD 'PITCH/ROLL D:  44'
t= 2190 ms  AUX4=2000  d_pitch=51 d_roll=45  beep 2 short  OSD 'PITCH/ROLL D:  45'
t= 2690 ms  AUX4=2000  d_pitch=52 d_roll=46  beep 2 short  OSD 'PITCH/ROLL D:  46'
t= 3200 ms  AUX4=1000  d_pitch=51 d_roll=45  beep 1 short  OSD 'PITCH/ROLL D:  45'
t= 3690 ms  AUX4=1000  d_pitch=50 d_roll=44  beep 1 short  OSD 'PITCH/ROLL D:  44'
thresholds: up if rc > 1700 us, down if rc < 1300 us; 1690 us -> no change
```

Two taps of 200 ms gave +2 in 0.5 s; a hold of 1.6 s gave +4 (a step immediately, then after 490 and every 500 ms). Both axes move together: from the 4.5 defaults of 40/46 to 46/52 (in 2025.12 the `d_roll`/`d_pitch` defaults are 30/34). The thresholds are strict: exactly 1700 µs is not yet a step, it has to be > 1700.

{{diagram:chart-bf-adj-step-timing|A run of the model: the first step is at the moment of the press, then every ~500 ms of holding; two short taps give as much as a second of holding.}}

### Step 3. Absolute mode and the pot jump
The slot `adjrange 1 0 2 1700 2100 14 4 67 20`: AUX3 up enables the AUX5 pot on `roll_srate` around 67 (the default in both 4.5 and 2025.12) ±20.

```text
pot 1000 us -> roll_srate 47  (Python // would give 47)
pot 1251 us -> roll_srate 58  (Python // would give 57)
pot 1500 us -> roll_srate 67  (Python // would give 67)
pot 1749 us -> roll_srate 76  (Python // would give 76)
pot 2000 us -> roll_srate 87  (Python // would give 87)
ROLL_P pot, adjrange 2 0 2 1700 2100 18 4 45 15: {1000: 30, 1500: 45, 2000: 60}
frame 1: AUX3=1000 pot=1900 -> range inactive, value stays 67
frame 2: AUX3=2000 pot=1900 -> applied roll_srate=83
```

C divides with truncation toward zero: at 1251 µs it comes out as 58, not 57. The main thing is frame 2: the pot was at 1900, the slot turned on, and `roll_srate` instantly jumped from 67 to 83 (from 670 to 830 °/s in Actual rates). The rule: center the pot before enabling the slot.

### Step 4. Select mode
```text
RATE_PROFILE (3)                   width 400 us: {988: 0, 1299: 0, 1300: 1, 1500: 1, 1699: 1, 1700: 2, 2012: 2}
RATE_PROFILE rate_6pos_switch=ON   width 200 us: {988: 0, 1299: 1, 1300: 2, 1500: 3, 1699: 3, 1700: 4, 2012: 5}
OSD_PROFILE -> osd_profile         width 400 us: {988: 1, 1299: 1, 1300: 2, 1500: 2, 1699: 2, 1700: 3, 2012: 3}
```

A three-position switch (988/1500/2012 µs with ELRS) lands in positions 0/1/2 with a margin of ≥ 200 µs from the 1300 and 1700 boundaries. CLI rate profiles are numbered from 0, in Betaflight App — from 1.

### Step 5. The VTX on a switch
The table from the VTX module (3 levels: 25/100/400 mW), `vtx_low_power_disarm = UNTIL_FIRST_ARM`, power slots 0–2 on AUX4 and a band R1 slot on AUX5:

```text
boot, AUX4 high, AUX5 low                cfg band=1 ch=1 power=3  -> sent 25 mW  locked=False
arm                                      cfg band=1 ch=1 power=3  -> sent 400 mW  locked=True
AUX4 mid in flight                       cfg band=1 ch=1 power=2  -> sent 100 mW  locked=True
AUX5 high in flight (band R ch1 slot)    cfg band=1 ch=1 power=2  -> sent 100 mW  locked=True
AUX4 low in flight                       cfg band=1 ch=1 power=1  -> sent 25 mW  locked=True
slot 3 (AUX5) is skipped only while it is lastIndex; called every RX frame, two active slots alternate (band locked here)

--- same table, band slot moved to index 0: vtx 0 4 5 1 0 1700 2100 ---
boot, AUX5 high (disarmed)               cfg band=5 ch=1 power=1  -> sent 25 mW  locked=False
arm                                      cfg band=5 ch=1 power=3  -> sent 400 mW  locked=True
AUX5 high in flight                      cfg band=5 ch=1 power=3  -> sent 400 mW  locked=True
```

The main trap is that a band on a switch works only before the first arm: in flight slot 3 is processed (every other frame, alternating with the active power slot), but the `locked` latch does not let the band change. The model calls the function once per line; in the firmware it runs on every RC frame, so two simultaneously active slots alternate rather than “the first one wins forever”. Power slots must not overlap.

### Step 6. The save sticks
```text
T1000 Y1000 P1000 R2000 armed=False -> SAVE (saveConfigAndNotify: writeEEPROM, readEEPROM, 1 beep)
T1000 Y1000 P1000 R2000 armed=True  -> ignored: armed
T1000 Y1000 P1060 R2000 armed=False -> PID profile 3
```

The gesture works only while disarmed and only if the pitch stick is ≤ `min_check`. Check in Receiver that the stick endpoints are below 1050 and above 1900.

### Step 7. A config for your own aircraft
The radio: AUX2 — a 3-position selector, AUX4 — a momentary 3-position switch, AUX5 — a pot, AUX6 — a 3-position switch, AUX7 — a 3-position switch for the VTX.

```
adjrange 0 0 1 900 1300 18 3 0 0
adjrange 1 0 1 1300 1700 20 3 0 0
adjrange 2 0 5 900 2100 12 5 0 0
adjrange 3 0 5 900 2100 29 5 0 0
vtx 0 6 0 0 1 900 1300
vtx 1 6 0 0 2 1300 1700
vtx 2 6 0 0 3 1700 2100
set vtx_low_power_disarm = UNTIL_FIRST_ARM
save
```

Selector down — ROLL_P on AUX4, middle — ROLL_D, up — nothing (there is no slot). AUX6 selects the rate profile and the OSD profile at the same time. This is the layout of a separate radio, not the team layout from `bf-modes-osd`: there AUX6 is FAILSAFE (STAGE1, 1700–2100) and AUX7 is BEEPER. They cannot be combined: the top position of AUX6 would select profile 3 and immediately trigger failsafe, and the VTX selector on AUX7 would turn on the beeper. With the team layout, move the selectors to free AUX channels and change the channel number in both `adjrange` fields and in `vtx`. Set the position of `osd_adjustment_range_pos` in the OSD tab (the value depends on the canvas). Before `save`, run `diff all` and save the file.

### Moving to real hardware
**The bench, props off, the battery through a current limiter or a “smoke stopper”.**
1. Load the config from step 7 and enable the “Adjustment range” OSD element. Save `diff all` as “before”.
2. Betaflight App → Receiver: check that AUX2/AUX4/AUX6/AUX7 give ~1000/1500/2000 µs, and the momentary AUX4 at rest — 1500 ± 20.
3. Close the CLI (adjustments do not work in CLI mode). Selector down, tap AUX4 up 3 times: `ROLL P:  48` in the goggles (from 45), 2 short beeps for every tap. Tap down 3 times — 45 again.
4. Open the CLI: `get p_roll` → 45. Exit, do +2, open the CLI: `get p_roll` → 47. Reboot without `save` — 45 again: the change was not saved.
5. AUX6 through its three positions: the OSD profile changes, a “position + 1” beep on the rate profile change. AUX7: `get vtx_power` in the CLI gives 1 → 2 → 3, but with `UNTIL_FIRST_ARM` the transmitter stays at 25 mW until the first arm — that is by design. To see the real switching, arm without props (or temporarily `set vtx_low_power_disarm = OFF` without `save`) and check by the goggles' RSSI at a fixed distance or with a power meter; write down the difference in dB (25 → 400 mW is +12 dB). Do not hold 400 mW on the bench for longer than 30 s without airflow.

**Hover (an open area, Blackbox enabled, wind < 5 m/s).**
6. Takeoff, hover at 1.5–2 m in ANGLE or ACRO. Selector at “nothing”. Record 20 s of baseline.
7. Selector to ROLL_D, +2 taps (`d_roll` 30 → 32 — in 2025.12 this is the base D; on 4.5 it would be 40 → 42, where it is the peak), 15 s of hover and a couple of roll flips. Another +2 — only if the response is better.
8. **Abort** (selector to “nothing” at once, land, no saving): oscillations or ringing, hot motors after 30 s, the OSD does not show the adjustment, the value went further than intended by more than 2 steps.
9. Landing, disarm, sticks “throttle down, yaw left, pitch down, roll right” → one beep. `diff all` “after” — the only difference is in `d_roll`. In Blackbox Explorer find the adjustment events and match the time against the steps.

Self-check: the lab is complete when:
- (model) the script has been run on the source (4.5 or 2025.12 — write down the version), the output of steps 1–6 is saved in your notes and matches the output in the module line by line (on 4.5-maintenance and 4.5.5: `35 names`, `34 slots, 30 initialised`; step 2 ends at `d_pitch=50 d_roll=44`; on 2025.12 the line `31 | LED_DIMMER` is added), and you have written down in your own words why function 26 is PITCH_F and not ROLL_RC_RATE (compare with the reference below);
- (model) for your own config the selector positions and the pot value at the endpoints are calculated; the method check — the same formulas on the data of steps 3–4 give 47 and 87 for a 67 ± 20 pot and positions 0/1/2 for 988/1500/2012 µs;
- (hardware) on the bench you saw for yourself that the adjustment is visible in the OSD/CLI and disappears after a reboot without `save` (`get p_roll`: 45 → 47 → 45 again after the reboot), and `get vtx_power` by the switch goes 1 → 2 → 3;
- (hardware) after the hover the “before” and “after” `diff all` are saved, the only difference between them is `d_roll`, and an adjustment event is found in Blackbox whose time matches your taps.

**Reference for self-check.** The function number in `adjrange` is the slot number in `defaultAdjustmentConfigs[]`, not the enum value: from number 25 on they diverge, slot 26 refers to enum 30 — PITCH_F, and ROLL_RC_RATE is in the “not reachable from adjrange” list. The pot at 1251 µs gave 57 instead of 58 — the model still has Python's `//` division, while C truncates toward zero. After the reboot `get p_roll` shows 47 and not 45 — the value was saved (the stick gesture of step 6 or `save`), and the “disappears without `save`” experiment has to be repeated. More than one line differs in the “after” `diff all` — something besides the adjustment was changed between the backups; find the extra change before the next flight.

## diagnostics
- **Symptom:** the adjustment switch changes nothing
  - Possible cause: the slot is inactive (the range channel is outside `start..end`, the end is not included), the CLI is open, or the function is empty (32–35 in 2025.12, 31–34 in 4.5).
  - What to do: `adjrange` — check the line; look at the range channel in Receiver; close the CLI; check the function number against the table.
- **Symptom:** the wrong parameter changes (you expected ROLL_F, and YAW_F is being turned)
  - Possible cause: the number was taken from the enum or from the betaflight.com table for another version.
  - What to do: CLI number = position in `defaultAdjustmentConfigs[]`; ROLL_F = 27, YAW_F = 28 (in both 4.5 and 2025.12).
- **Symptom:** the value grows by itself every half second
  - Possible cause: the step switch is off center or the channel is not centered (the center is not 1500, `mid_rc` is different).
  - What to do: a momentary switch, center 1500 ± 20 in Receiver, the switch warning on the radio.
  - What you see in the log: a series of INFLIGHT_ADJUSTMENT events at 500 ms intervals.
- **Symptom:** after the slot is enabled the quad abruptly changes its behavior
  - Possible cause: absolute mode, the pot off center — the value jumped.
  - What to do: center the pot before enabling the slot; for two parameters on one pot — a middle selector position without a slot.
- **Symptom:** after a reboot the settings came back
  - Possible cause: not saved; the pitch stick did not reach `min_check`; Save in the app without Refresh wrote the old values.
  - What to do: a stick save with one beep, or CLI `save`; check the stick endpoints.
  - Consequences: the tuning is lost, and Blackbox shows values that are not in the config.
- **Symptom:** the PID profile does not switch with a switch
  - Possible cause: there is no such function (neither in 4.5 nor in 2025.12).
  - What to do: change the profile with the sticks while disarmed, from the OSD menu or with `profile`; in flight only rates, OSD and LED are switched.
- **Symptom:** the `vtx` band slot does not take effect
  - Possible cause: the aircraft has already been armed since power-up (the `locked` latch until reboot).
  - What to do: change the band/channel before the first arm (on the bench, after a reboot); check that the slot ranges on one channel do not overlap.
- **Symptom:** the VTX power does not go up on the bench
  - Possible cause: `vtx_low_power_disarm` = ON or UNTIL_FIRST_ARM, or there is no VTX table.
  - What to do: `get vtx_low_power_disarm`, `vtx_info`, `vtxtable`; on the bench that is how it should be.

## checklist
- The function numbers are taken from the table for my version (CLI ≠ enum, a shift of 4 from number 25; 31 LED_DIMMER — only from 2025.12)
- Step slots are on a momentary switch, and the switch warning is enabled on the radio
- The OSD element `osd_adjustment_range_pos` is enabled and visible in the goggles
- The pot is centered before an absolute slot is enabled
- The “safe” selector position has no slot
- I know the save gesture (disarm, T↓ Y← P↓ R→) and have checked that it gives one beep
- `diff all` before and after every adjustment session
- VTX: power slots in order, `vtx_low_power_disarm` is chosen, power within the law

## references
- rc_adjustments.c — Betaflight 2025.12.5 (GitHub, raw) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/fc/rc_adjustments.c | primary | A
- rc_adjustments.c — Betaflight 4.5-maintenance (GitHub, raw) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/fc/rc_adjustments.c | primary | A
- rc_controls.c — stick commands, Betaflight 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/fc/rc_controls.c | primary | A
- vtx_control.c — VTX channel activation, Betaflight 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/io/vtx_control.c | primary | A
- vtx.c — vtx_low_power_disarm, Betaflight 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/io/vtx.c | primary | A
- cli.c — adjrange and vtx parsers, Betaflight 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/cli/cli.c | primary | A
- In-Flight Adjustments — Betaflight docs | https://betaflight.com/docs/wiki/guides/current/Inflight-Adjustments | primary | B
- VTX — Betaflight docs | https://betaflight.com/docs/wiki/guides/current/VTX | primary | B

## notes
The In-Flight Adjustments page on betaflight.com describes the development branch and in places matches neither 4.5 nor 2025.12: “12 ranges” (in fact 30), function 31 SLIDER_MASTER_MULTIPLIER (it exists only in `master`; in 2025.12 number 31 is LED_DIMMER), and the example with function 0 for “nothing” is better replaced with a position without a slot: function 0 in a non-empty slot indexes `defaultAdjustmentConfigs[−1]`. The Adjustments tab page in the Configurator documentation is empty.
