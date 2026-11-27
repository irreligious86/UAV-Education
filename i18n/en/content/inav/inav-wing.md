---
id: inav-wing
title: "Fixed wing on INAV: mixer, autolaunch, autotune"
level: L2
readingTime: 25 min
firmware: INAV 9.1 (checked against 9.1.0)
status: published
added: 2026-11-08
tags:
  - fixed wing
  - autotune
  - autolaunch
related:
  - inav-gps
  - ap-quadplane
next:
  - inav-ipf
source: content/inav/inav-wing.md
source_hash: 6267680dba1b
---

## summary
A flying wing on INAV is the cheapest route to long-range flying with navigation. But a wing is not a quadcopter: there is no hover, there is a stall, throttle does not equal altitude, and a reversed elevon ends the flight in the first second of the launch. This module takes you through the setup: the AIRPLANE platform and the mixer, reverses and trims, the MANUAL/ANGLE/ACRO/CRUISE modes, hand launch with autolaunch, FF autotune and what changed in it, and failsafe for a fixed wing.

## theory
### The AIRPLANE platform
`platform_type = AIRPLANE` opens up the airplane mixer (Flying Wing: two elevons, one motor), flaps, the fixed-wing modes and fixed-wing navigation. The quadcopter modes disappear.

### Fixed-wing modes
- **MANUAL** — direct control of the servos, no stabilization. It must always be on a switch: it is the last resort.
- **ACRO** — rate stabilization.
- **ANGLE / HORIZON** — self-leveling.
- **NAV CRUISE** — holds heading and altitude, the stick corrects the heading.
- **NAV RTH, NAV WP** — as on a multirotor, but without hovering: over home the wing circles (loiter) or flies a landing approach.

### Throttle and speed
Three key settings: `nav_fw_cruise_thr` — the cruise throttle in navigation, `nav_fw_min_thr` and `nav_fw_max_thr` — the limits. In navigation a fixed wing gains altitude with pitch angle and throttle together; a cruise throttle that is too low in a climb leads to a stall.

### Autolaunch
The NAV LAUNCH mode: the aircraft waits for the throw, detects the launch from the acceleration, after `nav_fw_launch_motor_delay` smoothly brings the throttle up to `nav_fw_launch_thr`, and holds the climb angle `nav_fw_launch_climb_angle` until the `nav_fw_launch_timeout` timeout or until the sticks are moved. A hand launch without autolaunch means a motor at full throttle next to your fingers; autolaunch was invented precisely to prevent that.

### Autotune
AUTO TUNE is a modifier on top of ANGLE/HORIZON/ACRO; it does not work in MANUAL. It tunes the **feedforward** per axis and, in ACRO/HORIZON, the rates. **Autotune does not touch P and I** — a change from old versions; they are tuned by hand before or after. You need to fly with sharp inputs on all three axes for several minutes; an axis without sharp inputs will not be tuned. The result is not saved automatically: after landing, disarm and give the save stick command (or `save` in the CLI).

Three autotune settings of 9.1.0 (`settings.yaml`, `pid_autotune.c`) explain almost every complaint that “autotune did nothing”:

| Setting | Default | What it does | Rule |
|---|---|---|---|
| `fw_autotune_min_stick` | 50 % | the response is recorded only while the stick input (after deadband and expo) exceeds this | smooth inputs of a third of the travel are not counted at all: make them sharp and nearly full; the first changes on an axis come only after 5 s of such inputs (250 samples of 20 ms) |
| `fw_autotune_rate_adjustment` | AUTO | AUTO — the rates are adjusted up and down to match the capabilities of the airplane; LIMIT — down only, never above the starting rates; FIXED — the rates are not adjusted | in ANGLE the rates are never changed, with any value: ANGLE commands an angle, not a rate |
| `fw_autotune_max_rate_deflection` | 90 % (50…100) | the target percentage of maximum mixer output used for determining the rate | lower — lower rates and more control surface travel in reserve |

The check after the flight: in ANGLE only `fw_ff_roll`, `fw_ff_pitch`, `fw_ff_yaw` changed; in ACRO or HORIZON with AUTO — also `roll_rate`, `pitch_rate`, `yaw_rate`. If the rates did not change in ACRO with AUTO, check whether FIXED is set and whether the stick deflection was large enough.

{{diagram:inav-autotune-tree|What autotune changes depends on the mode underneath: in ANGLE — only feedforward, the rates — only in ACRO/HORIZON and not with FIXED, P and I — never; without sharp stick inputs above 50 % nothing changes.}}

### Flaperons, soaring and zero throttle
- **Flaperons.** `set has_flaps = ON` makes the FLAPERON mode (id 34) available; while it is active, `smix` input 14 (FEATURE FLAPS) equals `flaperon_throw_offset` (200 µs), and both ailerons go down by that amount on top of roll. The rule: input 14 is fed to both aileron servos so that both ailerons go down; the servos are mounted mirrored, so their weights have opposite signs (`smix 4 2 14 100 20 -1` and `smix 5 3 14 -100 20 -1` in `inav-mixer-vtol`). The bench check: FLAPERON on — both ailerons went down, and roll still moves them in opposite directions. The `smix` lines and the pulse calculation are in `inav-mixer-vtol`.
- **Soaring (SOARING, id 56).** It works only on top of NAV POSHOLD (loiter) or NAV COURSE HOLD (`navigation.c`): navigation stops holding altitude, pitch floats freely within `nav_fw_soaring_pitch_deadband` (5°), and with `nav_fw_soaring_motor_stop = ON` the motor stops. For thermals and for saving battery on a glider; navigation still holds the course or the circle.
- **Zero throttle in ANGLE.** `fw_min_throttle_down_pitch` (0, in tenths of a degree, up to 450) lowers the nose when the throttle is below `nav_fw_cruise_thr`: the addition grows linearly from 0 at cruise throttle to the full value at throttle 1000 (`pid.c`). An example: 50 (5°), `nav_fw_cruise_thr` = 1400, throttle 1200 → nose down by 5 × (1400 − 1200) / 400 = 2.5°. Without it a wing in ANGLE at closed throttle holds level and loses speed. It is tuned in flight with `adjrange` function 52 (`inav-adjustments`).

### Fixed-wing failsafe
The RTH procedure is the obvious choice when GPS is available. LAND on a fixed wing is a downward spiral with set angles, that is, a controlled impact. On a fixed wing a check of `failsafe_throttle` under load is mandatory (for LAND without altitude sensors; DROP simply shuts the motor off).

### The default numbers and how to set them
`nav_fw_cruise_thr` = 1400, `nav_fw_min_thr` = 1200, `nav_fw_max_thr` = 1700 (throttle PWM units); the throttle-to-pitch coupling `nav_fw_pitch2thr` = 10 (throttle added per degree of pitch — a simplified TECS: nose up → more throttle); the climb/dive angles `nav_fw_climb_angle` = 20°, `nav_fw_dive_angle` = 15°; the loiter radius `nav_fw_loiter_radius` = 7500 cm; the cruise speed for the remaining-distance estimate `nav_fw_cruise_speed` (0 = off). The throttle formula in navigation (`applyFixedWingPitchRollThrottleController()` in `navigation/navigation_fixedwing.c`, INAV 9.1.0): throttle = `nav_fw_cruise_thr` + `nav_fw_pitch2thr` × the commanded pitch in degrees (the pitch is negative in a dive), and the result is limited to the range `nav_fw_min_thr`…`nav_fw_max_thr`. The procedure: from the log of a manual flight find the throttle at which the wing flies level at 1.3–1.5 V_s (the “Wing aerodynamics” module) → that is `cruise_thr`; `min_thr` is the throttle at which there is still no stall in level flight; `max_thr` is set by the ESC current. `nav_fw_control_smoothness` smooths the navigation commands for large wings. In 9.0 the fixed-wing altitude controller has two methods: by vertical velocity (`nav_fw_alt_use_position = OFF`, default) and by position (ON); the default of `nav_fw_pos_z_ff` became 30 (10 in 8.0). The same release added PID scaling by airspeed `apa_pow` (0 — off) and pitch-based throttle compensation `tpa_pitch_compensation` (8).

### Autolaunch: detection settings
The throw is detected from the acceleration `nav_fw_launch_accel` (1863 cm/s² ≈ 1.9 g) or from the velocity `nav_fw_launch_velocity` (300 cm/s — for a swing launch and by GPS speed; a bungee launch or a throw is detected from the acceleration), then `nav_fw_launch_motor_delay` (500 ms) → the throttle `nav_fw_launch_thr` (1700) with the angle `nav_fw_launch_climb_angle` (18°) until `nav_fw_launch_timeout` (5000 ms) or stick input; `nav_fw_launch_max_angle` (45°) — if the tilt is greater, the launch is considered failed. The idle throttle before the throw is `nav_fw_launch_idle_thr`/`nav_fw_launch_idle_motor_delay`. A ground check: LAUNCH mode, the aircraft in your hand, a sharp forward movement **without the prop** — the motor should “start” according to the OSD.

### Fixed-wing landing
With `nav_rth_allow_landing`/LAND in a mission there are two different landings. If `fwapproach` is filled in for the selected safehome or mission (INAV 7.1+, `docs/Fixed Wing Landing.md`), the wing uses the wind estimate to build an approach into the wind and a glide slope, at the end glides with the motor off at the pitch `nav_fw_land_glide_pitch` and flares with `nav_fw_land_flare_pitch` (the flare — only with a rangefinder) — the geometry and the settings are in `inav-geozones-landing`. Otherwise the old landing is performed: a downward spiral and, below `nav_land_slowdown_minalt`, the final `nav_fw_land_dive_angle` (2°) with the motor off — a glide onto the belly; in a `fwapproach` landing this setting is not used. For landings that matter — a rangefinder and a site without obstacles; otherwise land by hand in MANUAL/ANGLE.

### A worked example: the first flight of a 1 m wing
MANUAL on a switch; the CG as calculated; `platform_type = AIRPLANE`, the Flying Wing mixer, servo directions checked (stick right — the right elevon up), `small_angle = 180`; autolaunch configured; the first throw in ANGLE with autolaunch, a climb to 50 m, trimming `cruise_thr` in level flight, then AUTO TUNE (FF/rates) with 3–5 minutes of sharp inputs, saving with the stick command after disarm, then a NAV CRUISE/RTH test at altitude. The log → `nav_fw_pitch2thr` and the angles from the actual behavior in the climb.

{{diagram:inav-autolaunch|Fixed-wing autolaunch with the default settings: throw detection, the motor delay, a climb at the set angle until the timeout or stick input.}}

### Place in the system

- **Receives:** the stall speed and the cruise from the wing calculation (`aero-wing`); checked servos and CG (`inav-setup-wing`); heading and position from GPS (`inav-gps`); the AIRPLANE platform (`inav-intro`).
- **Provides:** the cruise throttle and its limits, the climb and dive angles — to navigation: RTH, CRUISE and missions (`inav-missions`); feedforward and rates after autotune; the autolaunch settings — to the first throw (`inav-setup-wing`).
- **If you get it wrong here:** `nav_fw_cruise_thr` too low → the wing stalls while climbing in RTH or on a mission (`aero-wing`, `inav-missions`). The autotune result was not saved with the stick command after disarm → the next flight runs on the old values. Failsafe LAND on a fixed wing without a checked `failsafe_throttle` is a downward spiral, that is, a controlled impact (`inav-setup-scratch`).

## practice
### Step 1. Mixer and reverses
1. `platform_type = AIRPLANE`, the Flying Wing preset, save.
2. The Outputs tab: the motor on S1, the elevons on servos. Check: stick right — the right elevon up, the left down; stick back — both up.
3. In ANGLE tilt the wing by hand: the surfaces must oppose the tilt. If they help it — reverse in the mixer, not on the radio.
4. Trim the servos so that in MANUAL the surfaces sit at neutral.

**An exercise without hardware: where the elevons go.** Fill in a “right elevon / left elevon” table (up or down) for eight cases using only the two rules of this step: stick right — the right up, the left down; stick back — both up; in ANGLE the surfaces oppose the tilt. The cases: stick right; stick left; stick back; stick forward; ANGLE, sticks centered, the wing rolled right; rolled left; nose lowered; nose raised.

### Step 2. Modes and safety
MANUAL — a separate switch. ARM — a separate one. On a three-position switch: ANGLE / CRUISE / RTH. NAV LAUNCH — on a switch or automatically on arming (depending on the setup).

### Step 3. First flight
1. The CG per the wing's manual (usually checked with fingers under the wing).
2. Activate NAV LAUNCH, arm, throw level and firmly.
3. After the climb — ANGLE, assess the trim: if the wing drifts, adjust the servo trims, not the stick.
4. A short CRUISE, a short RTH at a small distance.

**An exercise without hardware: throttle in the climb and the autolaunch numbers.** Calculate with the throttle formula from the section “The default numbers and how to set them”: (1) the throttle in a climb with `nav_fw_climb_angle` 20° and in a dive with `nav_fw_dive_angle` 15° at the defaults; (2) the same with `nav_fw_pitch2thr = 20`; (3) the throttle in a 20° climb if `nav_fw_cruise_thr` is lowered to 1300, the rest at the defaults. Convert: the radius `nav_fw_loiter_radius` to meters and the length of one circle; `nav_fw_launch_velocity` to m/s; `nav_fw_launch_motor_delay` and `nav_fw_launch_timeout` to seconds. And answer from the Autotune section: which settings it changes in ANGLE, which in ACRO, what happens in MANUAL and what you must do after landing.

### Step 4. Autotune
On the next flight: activate AUTO TUNE in ANGLE or ACRO, 3–5 minutes of sharp inputs in roll, pitch and yaw (yaw is often forgotten). Disarm on the ground, then the save stick command. Check `fw_ff_roll`, `fw_ff_pitch` before and after.

Self-check: the lab is done when:
- the elevons (right / left): stick right — up / down; left — down / up; back — up / up; forward — down / down; ANGLE, rolled right — down / up; rolled left — up / down; nose lowered — up / up; nose raised — down / down;
- the throttle: (1) 1600 in the climb and 1250 in the dive; (2) 1800 → limited to 1700 and 1100 → limited to 1200; (3) 1500;
- the conversion: radius 75 m, circle 471 m; 3 m/s; 0.5 s and 5 s;
- autotune: in ANGLE — feedforward only; in ACRO — feedforward and rates; it does not work in MANUAL; after landing — disarm and the save stick command (or `save`), it does not change P and I;
- on hardware (if you have it): on the ground in ANGLE the surfaces behave as in the four bottom rows of your table, and `fw_ff_roll` and `fw_ff_pitch` after autotune and saving differ from the values before it.

**Reference for the self-check.** The response in ANGLE is the command a pilot would give to restore level: rolled right — a left roll is needed, that is, the same row as “stick left”; nose lowered — the same as “stick back”. The throttle: 1400 + 10 × 20 = 1600; 1400 − 10 × 15 = 1250; with `pitch2thr` = 20 the calculation gives 1800 and 1100, but the output is limited by `nav_fw_max_thr` = 1700 and `nav_fw_min_thr` = 1200. Common wrong answers: for ANGLE rolled right the answer is “right up, left down” — that way the surfaces help the tilt, and this is exactly the reverse that is fixed in the mixer, not on the radio; the dive throttle written as 1550 — the pitch in a dive is negative, the addition is subtracted; 1800 left in place with `pitch2thr` = 20 — the `nav_fw_max_thr` limit was forgotten; the circle length computed from 7500 m — the radius is in centimeters; P and I named in the autotune answer — those are tuned by hand.

## diagnostics
- **Symptom:** after the throw the wing dives or flips over
  - Possible cause: a reversed elevon or the wrong CG.
  - What to do: check the surface response to tilt in ANGLE on the ground, check the center of gravity.
- **Symptom:** it loses altitude in a climb in navigation
  - Possible cause: a low `nav_fw_cruise_thr`/`nav_fw_max_thr`.
  - What to do: raise the cruise and the maximum throttle.
- **Symptom:** autotune changes nothing
  - Possible cause: flying in MANUAL, or too few sharp inputs, or expecting P/I to change.
  - What to do: ANGLE/ACRO, sharp inputs on all axes; P/I — by hand.
- **Symptom:** autolaunch does not start the motor
  - Possible cause: the throw was not detected (too weak) or a timeout.
  - What to do: throw harder, check `nav_fw_launch_*`.
- **Symptom:** in a climb navigation loses speed, a stall
  - Possible cause: `nav_fw_climb_angle` is large with a small `cruise_thr`/`pitch2thr`.
  - What to do: an angle of 10–15°, a higher `pitch2thr`, `cruise_thr` from the log.
- **Symptom:** autolaunch triggers in the hand before the throw
  - Possible cause: `nav_fw_launch_accel` is low, shaking.
  - What to do: a higher threshold, hold it steady, test without the prop.
- **Symptom:** in a loiter the wing “falls” into the circle
  - Possible cause: the radius is too small for the speed, the bank is limited.
  - What to do: a larger `nav_fw_loiter_radius`, `nav_fw_bank_angle` (35° by default) from the calculation of V_s in a turn.

## references
- INAV Mixer (platform type) | https://github.com/iNavFlight/inav/blob/master/docs/Mixer.md | primary | A
- INAV Airplane Autotune | https://github.com/iNavFlight/inav/blob/master/docs/Autotune%20-%20fixedwing.md | primary | A
- INAV Failsafe | https://github.com/iNavFlight/inav/blob/master/docs/Failsafe.md | primary | A
- INAV settings reference (settings.yaml) | https://github.com/iNavFlight/inav/blob/master/src/main/fc/settings.yaml | primary | A

## checklist
- `platform_type = AIRPLANE`, the mixer preset matches the wing
- The surfaces oppose the tilt in ANGLE
- MANUAL and ARM are on separate switches
- The CG is checked, autolaunch is configured
- Autotune was done on all three axes, P/I are tuned by hand
