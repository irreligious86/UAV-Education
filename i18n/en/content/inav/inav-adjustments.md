---
id: inav-adjustments
title: "INAV in-flight adjustments: adjrange, stick commands, profiles, the OSD menu"
level: L2
readingTime: 50 min
firmware: INAV 9.1 (checked against 9.1.0)
status: published
added: 2026-11-20
tags:
  - INAV
  - adjustments
  - adjrange
  - stick commands
  - profiles
  - CMS
  - CLI
related:
  - inav-mc-tuning
  - inav-ipf
  - inav-mixer-vtol
  - inav-osd-hd
  - inav-cli-backup
  - inav-setup-wing
  - bf-adjustments
next:
  - inav-mc-tuning
source: content/inav/inav-adjustments.md
source_hash: 12aaa4db3adc
---

## summary
INAV has four ways to change a setting without a laptop: adjustments on a switch (`adjrange`, the Adjustments tab), stick commands while disarmed, profile switching (control, battery, mixer) and the CMS menu in the OSD. This module goes through them from the INAV 9.1.0 source: the `adjrange` format and its limits (20 ranges, 4 slots), all 61 function numbers with their step and limits, the step timing (immediately and then once every 500 ms), where the value is written and which actions save it to EEPROM — including the unexpected ones. Separately — the stick command table from `rc_controls.c` and how all of this differs from Betaflight. The practice is a calculation exercise: decode and write `adjrange` lines, work out the value after a series of holds, decide what survives a reboot and find three errors in a config.

## theory
### Four mechanisms and which of them work in the air
This module is about changing INAV settings without a laptop and without wrecking the aircraft in the process. The reading order is this: first the overall map of the four mechanisms (the table below), then `adjrange` — the line format, slots, the step and its timing, the full function table; after that — what gets into EEPROM and when, stick commands, profiles and the CMS menu. At the end come the procedure for adjusting PIDs in the air, the differences from Betaflight and the dangers. Read the “Dangers” section before the first `adjrange` line on your own aircraft: three items in it (function 54 on a multirotor, a duplicate function in a slot, a two-position switch) are ways to crash the aircraft with a single configuration line. The starting PIDs and their tuning order are in `inav-mc-tuning`, the OSD elements for feedback in `inav-osd-hd`, the `diff all` backup in `inav-cli-backup`.

| Mechanism | Arm state | What it changes | Saving |
|---|---|---|---|
| `adjrange` (the Adjustments tab) | armed and disarmed | one number per step: PIDs, rates, expo, TPA, fixed-wing cruise throttle, VTX power | not saved by itself |
| Stick commands | disarmed only | profile, calibrations, level trim, missions, saving | some commands write EEPROM themselves |
| Profiles | the `MIXER PROFILE 2` mode and logic conditions — in flight; sticks and the CLI — on the ground | a whole set of settings at once | the active profile number is an ordinary setting in RAM |
| CMS (the OSD menu) | disarmed only | PIDs, rates, filters, navigation, VTX, OSD | the SAVE+EXIT item |

Everything that is changed on the fly takes effect immediately. One step too many in multirotor D means hot motors, an error in `nav_fw_cruise_thr` means a wing that does not hold its speed in RTH. So the mechanics come first, then the practice.

### `adjrange`: two channels and a slot
The command format (`cliAdjustmentRange` in `fc/cli.c`), all seven fields are required:

`adjrange <index> <slot> <range channel> <start> <end> <function> <adjustment channel>`

| Field | Allowed | Meaning |
|---|---|---|
| index | 0…19 | the line number, `MAX_ADJUSTMENT_RANGE_COUNT 20` |
| slot | 0…3 | `MAX_SIMULTANEOUS_ADJUSTMENT_COUNT 4`; in the Configurator this is “Slot 1…4” |
| range channel | 0…29 | AUX1 = 0 (“CH 5” in the Configurator); selects *what* to adjust |
| start, end | 900…2100, step 25 | stored as a step number 0…48; the range is active when `start ≤ channel < end` |
| function | 0…60 | the number from the table below, 0 — the line is disabled |
| adjustment channel | 0…29 | the switch that moves the value; may be the same as the range channel |

Step number = (value − 900) / 25 with the fractional part dropped, and the value is first constrained to 900…2100. Enter 1310 — 1300 is stored, enter 1690 — 1675 is stored. A line with `start ≥ end` never triggers. If even one field is out of range, the whole line is zeroed and the CLI prints a parse error.

A slot is a place for one active function. On every cycle of the receiver task (`processRx` in `fc/fc_core.c`; the task is event-driven — it runs once per received radio link frame, that is, 50 times a second on a 50 Hz link and 150 times on a 150 Hz link) the firmware goes through the lines in index order: an active line takes its slot if it is free; an inactive line frees the slot if the slot holds *its* function. Three consequences follow:

- one function at a time works in one slot; with two active lines the slot goes to the line with the lower index;
- a selector position for which there is no line is a safe “off”;
- the same function must not be put in one slot twice (the analysis is below, in the dangers).

The official `Inflight Adjustments.md` in the 9.1.0 tag claims that a slot “retains its state” when the channel leaves the range and that the function numbers are 0–56. The 9.1.0 source says otherwise: the slot is freed, and the functions are 0–60. Trust the source.

Adjustments are not processed while the CLI is open (the slots freeze in their current state: both adjustment functions are simply not called), nor without a receiver signal or during failsafe (the slots are freed); there are no steps in any of the three cases.

### Step mode only: threshold, repeat, signals
All 60 entries of `defaultAdjustmentConfigs[]` have `ADJUSTMENT_MODE_STEP`. The select-by-position mode (`ADJUSTMENT_MODE_SELECT`) is compiled under `USE_INFLIGHT_PROFILE_ADJUSTMENT`, and that macro is commented out in `rc_adjustments.h`. An absolute mode, “knob = value”, does not exist in INAV at all.

- The adjustment channel **above 1700** (`PWM_RANGE_MIDDLE + 200`) — plus one step, **below 1300** — minus one step. The thresholds are hard-coded and do not depend on `mid_rc`.
- The first step comes in the same cycle in which the channel crossed the threshold. While the switch is held, the step repeats once every 500 ms (`RESET_FREQUENCY_2HZ`). Returning to the middle re-arms the slot at once, so short presses are faster than holding.
- The number of steps for a hold of length T: **n = 1 + ⌊T / 0.5 s⌋**. To get n steps, hold for at least (n − 1) · 0.5 s. The accuracy is one receiver cycle: the first repeat comes one cycle earlier than 500 ms, the following ones — after 500 ms rounded up to a cycle.
- If the slot became active when the switch was already deflected, the step happens at once. A two-position switch or a knob as the adjustment channel steps without stopping until it hits the limit.
- Sound: 2 short beeps for a step up, 1 for a step down (`beeperConfirmationBeeps`). The beep sounds before the limit check: at the limit the value stands still while the beeper keeps beeping.
- OSD: there is no separate message. If the screen has an element with this value (`OSD_ROLL_PIDS`, `OSD_NAV_FW_CRUISE_THR`, `OSD_FW_LEVEL_TRIM`, `OSD_TPA`, `OSD_VTX_POWER` and the other “adjustable” elements of `io/osd.c`), the number blinks for as long as its function is in a slot. No element — no feedback except the beeper. The layouts are in `inav-osd-hd`.
- Blackbox: with `feature BLACKBOX` every step is logged as an `INFLIGHT_ADJUSTMENT` event with the new value.

{{diagram:inav-adjustments-flow|The range channel selects a line, the line takes a slot, the adjustment channel steps on the 1300/1700 thresholds; the result sits in RAM until some EEPROM write saves the whole config.}}

### The 9.1.0 function table
The number in the CLI equals the `adjustmentFunction_e` value — there is no offset as in Betaflight. The step is 1 unless stated otherwise. The PID functions write to the bank of the current platform: `mc_*` and `nav_mc_*` on a multirotor, `fw_*` and `nav_fw_*` on an airplane.

| No. | Function | Setting | Step | Limits |
|---|---|---|---|---|
| 1 | RC_RATE | nothing: there is no branch in the code, only a beep | — | — |
| 2, 25 | RC_EXPO, RC_YAW_EXPO | `rc_expo`, `rc_yaw_expo` | 1 | 0…100 |
| 3 | THROTTLE_EXPO | `thr_expo` | 1 | 0…100 |
| 4 | PITCH_ROLL_RATE | `pitch_rate` and `roll_rate` together | 1 | 4…180 |
| 23, 24 | PITCH_RATE, ROLL_RATE | `pitch_rate`, `roll_rate` | 1 | 4…180 |
| 5 | YAW_RATE | `yaw_rate` | 1 | 1…180 |
| 6–9 | PITCH_ROLL_P / I / D / FF | both axes at once | 1 | 0…255 |
| 10–13 | PITCH_P / I / D / FF | `mc_p_pitch`… / `fw_p_pitch`… | 1 | 0…255 |
| 14–17 | ROLL_P / I / D / FF | `mc_p_roll`… / `fw_p_roll`… | 1 | 0…255 |
| 18–21 | YAW_P / I / D / FF | `mc_p_yaw`… / `fw_p_yaw`… | 1 | 0…255 |
| 22 | RATE_PROFILE | nothing: “placeholder for compatibility”, only a beep | — | — |
| 26, 27 | MANUAL_RC_EXPO, MANUAL_RC_YAW_EXPO | `manual_rc_expo`, `manual_rc_yaw_expo` | 1 | 0…100 |
| 28–31 | MANUAL_PITCH_ROLL / ROLL / PITCH / YAW_RATE | `manual_roll_rate`, `manual_pitch_rate`, `manual_yaw_rate` | 1 | 0…100 |
| 32 | NAV_FW_CRUISE_THR | `nav_fw_cruise_thr` | 10 | 1000…2000 |
| 33 | NAV_FW_PITCH2THR | `nav_fw_pitch2thr` | 1 | 0…100 |
| 34, 35 | ROLL / PITCH_BOARD_ALIGNMENT | `align_board_roll`, `align_board_pitch` | 5 (0.5°) | −1800…3600 |
| 36–38 | LEVEL_P / I / D | `mc_p_level`… / `fw_p_level`… | 1 | 0…255 |
| 39–41 | POS_XY_P / I / D | `nav_mc_pos_xy_p` / `nav_fw_pos_xy_p`, `_i`, `_d` | 1 | 0…255 |
| 42–44 | POS_Z_P / I / D | `nav_mc_pos_z_p` / `nav_fw_pos_z_p`, `_i`, `_d` | 1 | 0…255 |
| 45 | HEADING_P | `nav_mc_heading_p` / `nav_fw_heading_p` | 1 | 0…255 |
| 46–48 | VEL_XY_P / I / D | `nav_mc_vel_xy_p`, `_i`, `_d` | 1 | 0…255 |
| 49–51 | VEL_Z_P / I / D | `nav_mc_vel_z_p`, `_i`, `_d` | 1 | 0…255 |
| 52 | FW_MIN_THROTTLE_DOWN_PITCH_ANGLE | `fw_min_throttle_down_pitch` | 5 (0.5°) | 0…450 |
| 53 | VTX_POWER_LEVEL | `vtx_power` | 1 | 0…the number of power levels of the VTX |
| 54 | TPA | `tpa_rate` | 1 | 0…200 (no higher than 100 on a multirotor, see below) |
| 55 | TPA_BREAKPOINT | `tpa_breakpoint` | 5 | 1000…2000 |
| 56 | NAV_FW_CONTROL_SMOOTHNESS | `nav_fw_control_smoothness` | 1 | 0…9 |
| 57 | FW_TPA_TIME_CONSTANT | `fw_tpa_time_constant` | 5 ms | 0…5000 |
| 58 | FW_LEVEL_TRIM | `fw_level_pitch_trim` | 0.1° | −10…10 |
| 59 | NAV_WP_MULTI_MISSION_INDEX | `nav_wp_multi_mission_index` | 1 | 1…the number of loaded missions |
| 60 | NAV_FW_ALT_CONTROL_RESPONSE | `nav_fw_alt_control_response` | 1 | 5…100 |

What works on one platform only. On a multirotor the FF functions (9, 13, 17, 21) move `mc_cd_*` (Control Derivative, see `inav-mc-tuning`), and POS_XY and POS_Z have only P: functions 40, 41, 43, 44 write to fields that multirotor navigation does not read. On an airplane VEL_XY and VEL_Z (46–51) are useless: there are no `nav_fw_vel_*` settings. Functions 32, 33, 52, 56–58, 60 make sense only on a fixed wing, 26–31 — only in MANUAL. Function 53 requires a controllable VTX (SmartAudio, Tramp or MSP), and 59 works with missions loaded and outside WP mode.

**Warning: function 54 on a multirotor.** The adjustment limits `tpa_rate` only to the range of the setting — 0…200 (`applyAdjustmentU8(…, 0, SETTING_TPA_RATE_MAX)` in `rc_adjustments.c`). The range up to 200 exists for the airplane branch, where the TPA factor is clamped to 0.3…2.0. In the multirotor branch (`calculateMultirotorTPAFactor` in `flight/pid.c`) there is no limit between `tpa_breakpoint` and maximum throttle: factor = (100 − `tpa_rate` · (throttle − breakpoint) / (max throttle − breakpoint)) / 100, and with `tpa_rate` above 100 it is negative at high throttle — P and D change sign, and the controller shakes the aircraft instead of stabilizing it. The limit `constrain(…, 0, 100)` is only in the branch “throttle exactly at maximum” and gives a factor of 0 there. A walkthrough with numbers is in `inav-mc-tuning`. The rule: do not put function 54 on a multirotor until you have calculated how far it can go. A switch without a return to center takes `tpa_rate` from 0 to 100 in 50 s and to 200 in 100 s — one step every 0.5 s; the beeper sounds the same on safe and dangerous values. If you do need function 54 — only a self-centering switch, the `OSD_TPA` element on the screen and a count of the steps so as not to go past 100.

Where the value lives matters when the profile changes:

| Storage | Functions |
|---|---|
| control profile (`control_profile 1…3`) | PIDs, LEVEL, navigation PIDs, rates, expo, TPA, 57, 58, 60 |
| battery profile (`battery_profile 1…3`) | 32 `nav_fw_cruise_thr`, 33 `nav_fw_pitch2thr` |
| master settings | 34, 35, 52, 53, 56, 59 |

A step is applied to the profile that is active at the moment of the step. Switch the profile in flight — and the next step goes into a different one.

### What is saved and when
An adjustment changes the copy of the configuration in RAM. It gets into EEPROM only together with a write of the **whole** config. Such a write is done by:

| Action | Condition | Indication |
|---|---|---|
| the Save stick command | disarmed, held for 0.4 s | “** SAVING SETTINGS **”, then 1 beep and “** SETTINGS SAVED **” for 5 s |
| CLI `save` | — | a write and a reboot |
| the Save button in the Configurator (`MSP_EEPROM_WRITE`) | disarmed | the line “EEPROM saved” in the log |
| CMS: SAVE+EXIT, SAVE+REBOOT | disarmed | the same OSD message |
| a change of the control, battery or mixer profile — with the sticks, with a CLI command (`control_profile N`, `battery_profile N`, `mixer_profile N`) or with the drop-down in the Configurator | the profile actually changed | beeps by profile number; the write happens at once, without the 0.5 s wait |
| the level trim stick commands | every command | the save message |
| `stats = ON` | a disarm after being armed for ≥ 10 s | the save message |
| servo autotrim, accelerometer and compass calibrations, optical flow calibration, saving a mission with the sticks | on completion, while disarmed | the save message |

Save requests with a notification are merged into one and executed while disarmed, no earlier than 0.5 s after the disarm (`processDelayedSave`). A profile change is not part of this sequence: it writes EEPROM immediately (`setConfigProfileAndWriteEEPROM` and the same kind of functions for the battery and mixer profiles in `fc/config.c`). Hence the rule: “I did not save” is no guarantee. If statistics are enabled, autotrim ran after the landing or you typed `control_profile 2` in the CLI to look at the second PID set, a bad adjustment is already in EEPROM. An adjustment is lost on power-off, on a reboot and on the CLI command `exit` (“unsaved changes lost”). The reliable rollback is a `diff all` taken before the flight (see `inav-cli-backup`).

### Stick commands
`processRcStickPositions` (`fc/rc_controls.c`) compares the positions of the four sticks: LOW — the channel is below `min_check` (1100), HIGH — above `max_check` (1900). A command triggers when the combination has been held for 20 counts with at least 20 ms between them (`MIN_RC_TICK_INTERVAL_MS`), that is, for at least 0.4 s. A count is added only in a receiver cycle, so on a 50 Hz receiver with jitter only every second frame is counted and you have to wait up to 0.8 s. The commands are **disabled while armed, with the CLI open and in the CMS menu**. INAV has had no stick arming since version 2.2.

| Command | Throttle | Yaw | Pitch | Roll |
|---|---|---|---|---|
| Control profile 1 / 2 / 3 | LOW | LOW | CENTER / HIGH / CENTER | LOW / CENTER / HIGH |
| Battery profile 1 / 2 / 3 | HIGH | LOW | CENTER / HIGH / CENTER | LOW / CENTER / HIGH |
| Save setting | LOW | LOW | LOW | HIGH |
| Calibrate Gyro | LOW | LOW | LOW | CENTER |
| Calibrate Acc | HIGH | LOW | LOW | CENTER |
| Calibrate Compass / Zero Yaw | HIGH | HIGH | LOW | CENTER |
| Level trim: forward / back | HIGH | CENTER | HIGH / LOW | CENTER |
| Level trim: left / right | HIGH | CENTER | CENTER | LOW / HIGH |
| Save / load the waypoint mission | LOW | CENTER | HIGH | LOW / HIGH |
| Unload the waypoint mission | LOW | CENTER | LOW | HIGH |
| Mission number + / − | LOW | CENTER | CENTER | HIGH / LOW |
| Bypass the navigation arming block (at the moment ARM is switched on) | any | HIGH | any | any |
| Enter the CMS | CENTER (1250…1750) | LOW (< 1250) | HIGH (> 1750) | any |

In `Controls.md` the last two rows are written with four sticks (LOW / HIGH / CENTER / CENTER and CENTER / LOW / HIGH / CENTER); the code checks less — the table shows what the code checks. The CMS entry compares the channels with its own thresholds of 1250 / 1750, not with `min_check` / `max_check`, and does not look at roll.

Details that are not in `Controls.md`:
- both profile groups work only with `feature TX_PROF_SEL`. Without it the combination is silently ignored;
- selecting the battery profile with the sticks disables `feature BAT_PROF_AUTOSWITCH` until a reboot;
- the “accelerometer trim” in fact shifts `align_board_roll` / `align_board_pitch` by 2 units (0.2°), repeats every 0.2 s of holding and saves the config every time;
- Zero Yaw (on a multirotor without a compass the command, while disarmed, sets the heading to 0° and marks it valid — at that moment the aircraft must be standing with the nose pointing north) is present in 9.1.0 and absent in 8.0.1; in which 9.x release exactly it appeared cannot be established from the two source trees. On an airplane without a compass the command does nothing. In 8.0.1 the table is the same, and the row was called Calibrate Mag;
- “bypass the arming block” is yaw at HIGH at the moment the ARM switch is turned on; the code does not check the other sticks (`checkStickPosition(YAW_HI)` in `navigation.c`). With `nav_extra_arming_safety = ALLOW_BYPASS` (default) it removes the protection “no GPS fix — no arming”: after such an arm RTH has nowhere to return to. The same movement bypasses the block “the first mission waypoint is farther than `nav_wp_max_safe_distance`” — with any value of `nav_extra_arming_safety`. Do not arm with yaw hard over out of habit: that disables both checks at once;
- “Profile 3” and “Save” differ only in pitch. If you do not pull pitch all the way down with `TX_PROF_SEL` enabled, you switch to profile 3.

The calibration and trim commands change the reference angles and the sensor zeros: run them on a stationary aircraft standing level.

### Profiles: what is switched and with what
| Profile | Count | CLI | Sticks | In flight |
|---|---|---|---|---|
| control (PIDs, rates) | 3 | `control_profile N` | yes, `TX_PROF_SEL` | logic operation 42 Set Control Profile; following the battery profile (`use_control_profile`, `controlrate_profile` before 9.0) or the mixer profile (`mixer_control_profile_linking`) |
| battery | 3 | `battery_profile N` | yes, `TX_PROF_SEL` | no; `BAT_PROF_AUTOSWITCH` selects the profile when the battery is plugged in |
| mixer | 2 | `mixer_profile N` | no | the `MIXER PROFILE 2` mode, `mixer_automated_switch` |

INAV has no “control profile on a switch” mode, and function 22 is a dummy. In the air the profile is changed only by logic (`inav-ipf`) or by the link to the mixer profile (`inav-mixer-vtol`). A profile change in flight instantly substitutes other PIDs and rates: check both sets on the ground and in a hover before you tie the change to a condition. `MIXER PROFILE 2` changes the assignment of the motors and servos — with propellers on the bench that means other motors starting.

The same logic gives the “tuning on a switch” that `adjrange` does not have: VTX power, band and channel, throttle scale, OSD layout, loiter radius — the operation numbers are in `inav-ipf`. INAV has no `vtx` command as in Betaflight.

### CMS: setup without a laptop on the ground
Entry is the stick command from the table, only while disarmed; while the menu is open, arming is disabled (`ARMING_DISABLED_CMS_MENU`) and the other stick commands do not work. The 9.1.0 sections: PID TUNING (PID PROF, EZTUNE, PID, PID ALTMAG, PID GPSNAV, FILTERING, MECHANICS, RATE PROF, RATE, MANU RATE), FEATURES (BLACKBOX, MIXER & SERVOS, NAVIGATION, VTX, LED STRIP), OSD, BATTERY, MISC. Exit: EXIT — the values stay in RAM until power-off, SAVE+EXIT — a write, SAVE+REBOOT — a write and a reboot. More in `inav-osd-hd`.

### How to adjust PIDs in the air
1. Before the flight: `diff all` to a file, and an element with the adjusted value on the OSD.
2. One function per flight. The selector in a position without a line — the adjustment is off; turn it on only at altitude and in steady flight.
3. A self-centering three-position switch on the adjustment channel. Count the beeps: every step is audible.
4. Multirotor P and D — in steps of 1–2 with a check of motor temperature after landing; the order and the signs of “too much / too little” are in `inav-mc-tuning`.
5. After landing: disarm, check the number on the OSD, the Save stick command, `diff all` once more — one line should have changed in the diff.

### Differences from Betaflight
| What | INAV 9.1.0 | Betaflight 2025.12 |
|---|---|---|
| `adjrange` lines | 20 | 30 |
| Slot | 0…3, really limits the number of simultaneous functions | the field remains in the format, always 0 |
| Modes | step only | step, absolute (`center`, `scale`), select by position |
| Function number in the CLI | equals the enum | position in the array + 1 |
| Profile on a switch | no (22 is a dummy) | RATE_PROFILE in select mode |
| Profile with the sticks | with `feature TX_PROF_SEL` | always |
| VTX | function 53 and logic operations | a separate `vtx` command |
| OSD feedback | its own element blinks | a message with the name and the value |

The details of the Betaflight side are in `bf-adjustments`.

### Dangers
- **One function twice in one slot.** By the code of `updateAdjustmentStates` an inactive line frees the slot if the slot holds its function — even when the slot was taken by another line with the same function. If the active line has the lower index, the adjustment is dead. If it has the higher one, the slot is taken anew on every cycle with a zeroed timer, and a step happens on every receiver cycle instead of 2 times a second. A receiver cycle is not a fixed 50 Hz: `processRx` is called once per received frame, so the runaway rate equals the frame rate of the radio link. On a 50 Hz link that is 50 steps a second (P from 40 to 255 in 4.3 s), on a 150 Hz link — 150 steps a second (the same 215 steps in 1.4 s), at 500 Hz — less than half a second. This conclusion was drawn by reading the source and porting it into a model (and independently repeated during fact-checking); it was not reproduced on hardware.
- **A two-position switch or a knob on the adjustment channel**: the value runs to the limit. Multirotor D at 255 means overheated motors, `nav_fw_cruise_thr` at 1000 means the motor at idle in RTH and on a mission, and the wing loses speed and altitude.
- **Combined functions** (4, 6–9, 28) move two axes at once.
- **Function 54 (`tpa_rate`) on a multirotor.** The adjustment limit is 200, and the multirotor TPA branch above 100 gives a negative factor at high throttle: P and D change sign (`inav-mc-tuning`). Do not raise `tpa_rate` above 100 with an adjustment and do not put function 54 on a switch without a return to center: it reaches 200 in 100 s. The formula and the rule are under the function table.
- **Functions 34 and 35** shift the flight controller's level in the air by 0.5° per step: ANGLE and navigation immediately fly with a different “level”. With a non-zero `align_board_yaw` the step is split between both settings (`updateBoardAlignment` rotates it by the board yaw angle): function 34 changes both `align_board_roll` and `align_board_pitch`. The level trim stick command behaves the same way.
- **The switch off center at power-up**: the steps start as soon as the receiver signal appears, still on the ground.

### Place in the system
- **Receives:** the AUX channels and their ranges from the receiver (`inav-setup-scratch`), the profile structure and the starting PIDs (`inav-mc-tuning`), logic conditions for changing the profile and the VTX (`inav-ipf`), the mixer profiles (`inav-mixer-vtol`), the OSD elements for feedback (`inav-osd-hd`).
- **Provides:** the tuned values of PIDs, rates, TPA and cruise throttle — to the control and battery profiles; the “before / after” `diff all` — to the backup (`inav-cli-backup`).
- **If you get it wrong here:** an adjustment saved by a side-effect EEPROM write looks like a tune that “went bad” (`inav-mc-tuning`); `nav_fw_cruise_thr` at the limit shows up in RTH (`inav-setup-wing`); a step into the inactive profile is “the value did not change” after a VTOL transition (`inav-mixer-vtol`).

## practice
The lab is a calculation exercise: no flight controller and no simulator. The configurations below are a teaching example assembled by hand, not the output of a real aircraft. The numbers of step 2 were obtained by running a model — a port of `updateAdjustmentStates` and `processRcAdjustments` from 9.1.0 to Python with a 20 ms receiver cycle.

### Step 1. Decode and write the lines
A fixed wing. AUX3 is a three-position selector (1000 / 1500 / 2000), AUX4 is a self-centering three-position switch, AUX7 is a second one of the same kind.

```
adjrange 0 0 2 900 1300 32 3
adjrange 1 0 2 1300 1700 58 3
adjrange 2 0 2 1700 2100 33 3
adjrange 3 2 6 900 2100 53 6
adjrange 4 1 2 1310 1690 56 3
```

Write down for each line: the slot, which channel enables it and in which position, which setting changes, the step, how often it repeats. Then write two lines for a quadcopter: the selector on AUX5, a self-centering switch on AUX6, slot 1, indexes 0 and 1; in the low selector position — nothing, in the middle — `nav_mc_vel_z_p`, in the high — `nav_mc_pos_xy_p`.

Answer. Lines 0–2: slot 0, the AUX3 selector low / center / high selects `nav_fw_cruise_thr` (step 10), `fw_level_pitch_trim` (step 0.1°), `nav_fw_pitch2thr` (step 1); AUX4 moves the value. Line 3: slot 2, AUX7 is its own range and adjustment channel — `vtx_power` is always available. Line 4: it is stored as 1300…1675 (steps 16 and 31), slot 1, `nav_fw_control_smoothness` in the middle selector position — with the same AUX4, that is, one press in the center changes both the trim and the smoothness. Everywhere the first step is immediate and the repeat is once every 500 ms. For the quadcopter: `adjrange 0 1 4 1300 1700 49 5` and `adjrange 1 1 4 1700 2100 39 5`; there is no line for the low position.

### Step 2. The value after a series of presses
Lines 0–3 from step 1 (line 4 was deleted). `nav_fw_cruise_thr = 1400`, `fw_level_pitch_trim = 0`, `nav_fw_pitch2thr = 10`.

1. Selector low. AUX4 held high for 2.3 s, then two short presses down of 0.2 s each.
2. Selector centered. AUX4 held low for 1.2 s.
3. Selector high. AUX4 held low for 6 s.
4. How long do you have to hold AUX4 high to raise the cruise throttle from 1430 to 1600?

Answer. (1) n = 1 + ⌊2.3 / 0.5⌋ = 5 steps of 10 → 1450; two presses → 1430. (2) n = 1 + ⌊1.2 / 0.5⌋ = 3 steps of 0.1° → −0.3°. (3) n = 1 + ⌊6 / 0.5⌋ = 13 attempts, but the limit 0 is reached on the 10th step, after 9 · 0.5 = 4.5 s; the beeper beeps three more times to no effect, and the result is 0. (4) 170 / 10 = 17 steps, hold for (17 − 1) · 0.5 = 8 s. The model gave steps at 0, 480, 980, 1480, 1980 ms — the same 5.

{{diagram:chart-inav-adj-staircase|A 2.3 s hold gives 5 steps of 10 (one at once and four more with a period of about 500 ms), two short presses down — two more steps: 1400 → 1450 → 1430.}}

### Step 3. Will it survive a reboot
In flight `nav_fw_cruise_thr` was adjusted from 1400 to 1450. `stats = OFF` unless stated otherwise. For each case decide what the value will be after the power is turned on again.

| No. | What was done after the adjustment | Answer |
|---|---|---|
| 1 | landing, disarm, power off | 1400 |
| 2 | disarm, the Save stick command | 1450 |
| 3 | the Save stick command while armed, then disarm and power off | 1400: the commands are disabled while armed |
| 4 | disarm, the Configurator connected, Save pressed on the Adjustments tab | 1450: the whole config is written |
| 5 | disarm, `get nav_fw_cruise_thr` in the CLI showed 1450, then `exit` | 1400 |
| 6 | `stats = ON`, a 5-minute flight, disarm | 1450: statistics save the config themselves |
| 7 | `feature TX_PROF_SEL`, after the disarm control profile 2 was selected with the sticks (it was 1) | 1450, and the flight controller boots in profile 2 |
| 8 | disarm, entering the CMS, EXIT | 1400 |

### Step 4. Find three errors
The radio: AUX3 is a three-position selector, AUX4 a self-centering switch, AUX5 a two-position switch (1000 / 2000), AUX6 a three-position switch, AUX7 a self-centering one. A quadcopter, `mc_p_pitch = mc_p_roll = 40`, `mc_d_pitch = mc_d_roll = 23`, a 50 Hz receiver.

```
adjrange 0 0 2 900 1300 6 3
adjrange 1 0 2 1300 1700 7 3
adjrange 2 0 2 1700 2100 6 3
adjrange 3 1 4 900 2100 8 4
adjrange 4 2 5 1700 2100 22 3
adjrange 5 3 6 900 2100 53 6
```

Answer. (a) Lines 0 and 2: function 6 twice in slot 0. Selector low — P does not change at all; selector high — a step on every receiver cycle, and P goes from 40 to 255 in 215 cycles of 20 ms = 4.3 s of holding (on a 150 Hz link the same 215 cycles would take 1.4 s: the pace is set by the receiver frame rate). (b) Line 3: the two-position AUX5 is both the range and the adjustment channel; it is always beyond a threshold. In the 1000 position D of both axes goes from 23 to 0 in 22 · 0.5 = 11 s, in the 2000 position — to 255 in 231 · 0.5 = 115.5 s. (c) Line 4: function 22 switches nothing, it only beeps; besides, it sits on the same AUX4 as slot 0. Line 5 is fine.

### Moving to real hardware
The propellers stay off until item 4.
1. Save a `diff all`. Enter the lines from step 1 for your channels, `save`.
2. On the bench: the selector in the position of a function, press the adjustment switch — two beeps up, one down; `get` in the CLI shows the new value.
3. Reboot without saving — the value is back. Repeat the adjustment and give the Save stick command: the OSD shows “** SETTINGS SAVED **”, and after a reboot the value is the new one.
4. Flight: a fixed wing at an altitude of at least 50 m in CRUISE or a multirotor in a hover. One function, one step at a time. The check: in the `diff all` after landing and saving one line has changed.

Self-check: the lab is done when:
- step 1: the decoding of the five lines matches the answer, line 4 is written as 1300…1675, the two lines you wrote match character for character (calculation);
- step 2: you got 1430, −0.3°, 0 with the limit reached after 4.5 s, and 8 s of holding (calculation);
- step 3: the eight answers match the table (calculation);
- step 4: lines 0 + 2, 3 and 4 are named, with the numbers 4.3 s, 11 s, 115.5 s within a tolerance of 0.5 s (calculation);
- hardware: after a reboot without saving the value is the original one, after Save — the new one, and one line differs in `diff all`.

**Reference for the self-check.** The correct result is the numbers above. Typical errors: (1) in step 2 you got 1440 or −0.2° — the first step at the moment of the press was forgotten, ⌊T / 0.5⌋ was counted without the one; (2) the range of line 4 was left as 1310…1690 — the firmware stores steps of 25, and the end is rounded down; (3) in step 3 cases 6 and 7 are marked “1400” — it was forgotten that any EEPROM write saves the whole config; (4) in step 4 line 5 was named as an error — one channel in both roles is allowed if the switch is self-centering.

## diagnostics
- **Symptom:** the switch is pressed, there are no beeps, the value does not change
  - Possible cause: the CLI is open; the range channel is outside `start…end` (the end is not included); function 0; the slot is taken by a line with a lower index; the same function is in this slot once more.
  - What to do: `adjrange` in the CLI, compare the steps with the Receiver tab; spread the functions across slots, remove duplicates.
- **Symptom:** the beeper beeps, the value stands still
  - Possible cause: the value is at the limit; function 1 or 22 (dummies); function 53 without a controllable VTX; function 59 without loaded missions.
  - What to do: check against the function table and the limits.
- **Symptom:** the value runs to the limit by itself
  - Possible cause: the adjustment channel is a two-position switch or a knob; the switch is off center at power-up; one function twice in a slot (then the step runs at the frame rate of the radio link — 50…500 times a second).
  - What to do: a self-centering switch; a switch position warning on the radio; remove the duplicate.
  - Consequences: overheated motors (D), a wing losing speed in RTH (`nav_fw_cruise_thr`), on a multirotor with function 54 — `tpa_rate` above 100.
- **Symptom:** a multirotor shakes or flips at high throttle and flies normally at low throttle; the config has an `adjrange` line with function 54
  - Possible cause: an adjustment took `tpa_rate` above 100 — the TPA factor above `tpa_breakpoint` became negative, and P and D work with the opposite sign (`inav-mc-tuning`).
  - What to do: reduce the throttle below `tpa_breakpoint` and land; on the ground `get tpa_rate`, restore the value from `diff all`, remove the line with function 54 or move it to a self-centering switch.
  - Consequences: loss of control at high throttle; the value may turn out to be saved by a side-effect EEPROM write and survive a reboot.
- **Symptom:** after a reboot the adjustment is still there although Save was not given
  - Possible cause: `stats = ON`, autotrim, level trim with the sticks, a profile change with the sticks, with a CLI command (`control_profile N`, `battery_profile N`, `mixer_profile N`) or with the drop-down in the Configurator, the Save button in the Configurator.
  - What to do: restore the value from the `diff all` taken before the flight.
- **Symptom:** a stick command does not trigger
  - Possible cause: the aircraft is armed; the CMS or the CLI is open; the channel endpoints do not reach 1100 / 1900; `feature TX_PROF_SEL` is not enabled for the profiles; the hold is shorter than 0.4 s (on a 50 Hz receiver hold for up to 0.8 s).
  - What to do: check the channels on the Receiver tab, widen the endpoints on the radio.
- **Symptom:** instead of saving, the flight controller beeped three times and changed the profile
  - Possible cause: with `TX_PROF_SEL` pitch did not reach LOW — that is the “profile 3” command.
  - What to do: `control_profile 1` in the CLI or with the sticks; the values are not lost — the profile change wrote the config.
- **Symptom:** you adjusted a PID, and after a VTOL transition “nothing changed”
  - Possible cause: `mixer_control_profile_linking = ON`, the steps went into the control profile of the other mode.
  - What to do: adjust in the mode the value is meant for; compare `diff all` for both profiles.

## checklist
- [ ] A `diff all` is saved before the flight
- [ ] The adjustment channel is a self-centering three-position switch, centered at power-up
- [ ] In each slot a function occurs once; the selector has a position without a line
- [ ] Functions 1 and 22 are not used; the combined ones (4, 6–9, 28) are chosen deliberately
- [ ] On a multirotor there is no function 54, or it has been calculated how high `tpa_rate` can go, and that is no more than 100 (`inav-mc-tuning`)
- [ ] The OSD has an element with the adjusted value
- [ ] You know whether `stats`, `TX_PROF_SEL` and autotrim are enabled and that a profile change (sticks, CLI, Configurator) writes EEPROM at once — what will save the config without a command
- [ ] After landing: Save with the sticks, one line changed in `diff all`

## references
- INAV 9.1.0 rc_adjustments.c (functions, step, limits, timing, slots) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/rc_adjustments.c | primary | A
- INAV 9.1.0 rc_adjustments.h (function numbers, 20 ranges, 4 slots) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/rc_adjustments.h | primary | A
- INAV 9.1.0 cli.c (`adjrange`, `save`, `exit`, the profile commands) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/cli.c | primary | A
- INAV 9.1.0 rc_controls.c (stick commands) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/rc_controls.c | primary | A
- INAV 9.1.0 config.c (saving, profile changes) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/config.c | primary | A
- INAV 9.1.0 rc_modes.h (range steps 900–2100 in 25s) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/rc_modes.h | primary | A
- INAV 9.1.0 settings.yaml (limits and defaults of the settings) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/settings.yaml | primary | A
- INAV 9.1.0 stats.c (saving on disarm) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/stats.c | primary | A
- INAV 9.1.0 cms_menu_imu.c and cms.c (CMS sections, exit with saving) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/cms/cms_menu_imu.c | primary | A
- INAV 9.1.0 Controls.md (the stick command table) | https://github.com/iNavFlight/inav/blob/9.1.0/docs/Controls.md | primary | A
- INAV 9.1.0 Inflight Adjustments.md (outdated in two places, see notes) | https://github.com/iNavFlight/inav/blob/9.1.0/docs/Inflight%20Adjustments.md | primary | B
- Betaflight 2025.12 rc_adjustments.h (30 ranges) | https://github.com/betaflight/betaflight/blob/2025.12.5/src/main/fc/rc_adjustments.h | primary | B

## notes
The firmware was not built or run: all the behavior was obtained by reading the INAV 9.1.0 source and porting two functions of `rc_adjustments.c` into a Python model; it was not checked on hardware or in SITL. This concerns first of all the conclusion about one function placed twice in one slot and the step rate in that case (the frame rate of the radio link, not a fixed 50 Hz).

`docs/Inflight Adjustments.md` in the 9.1.0 tag disagrees with the code: it says “Adjustment function 0 – 56” (0–60 in the code) and “a slot retains its state outside the range” (in the code the slot is freed). `rc_adjustments.c` in 9.1.0 differs from 8.0.1 only by the rename `controlRateConfig` → `controlConfig`; the stick command table in the code is the same.
