---
id: inav-wing
title: "A Wing on INAV: Mixer, Auto Launch, Autotune"
level: L2
readingTime: 25 min
firmware: INAV 7.0+
status: published
added: 2026-11-08
tags:
  - wing
  - autotune
  - auto launch
related:
  - inav-gps
  - ap-quadplane
next:
  - inav-ipf
source: content/inav/inav-wing.md
source_hash: 1513d87a39af
---

## summary
A flying wing on INAV is the cheapest path to long-range flights with navigation. But a wing is not a quadcopter: there's no hover, there is stall, throttle doesn't equal altitude, and an elevon reversal error ends in the first second of the launch. This module walks you through the setup: the AIRPLANE platform and mixer, reversals and trims, MANUAL/ANGLE/ACRO/CRUISE modes, hand launch with auto launch, the FF autotune and what changed in it, and failsafe for a wing.

## theory
### The AIRPLANE platform
`platform_type = AIRPLANE` unlocks the airplane mixer (Flying Wing: two elevons, one motor), flaps, wing modes and fixed-wing navigation. The quadcopter modes disappear.

### Wing modes
- **MANUAL** — direct servo control, no stabilization. It must always be on a switch: it's your last resort.
- **ACRO** — angular rate stabilization.
- **ANGLE / HORIZON** — self-leveling.
- **NAV CRUISE** — heading and altitude hold, the stick corrects the heading.
- **NAV RTH, NAV WP** — like on a multirotor, but without hover: over home the wing circles (loiter) or goes in to land.

### Throttle and airspeed
Three key parameters: `nav_fw_cruise_thr` — cruise throttle in navigation, `nav_fw_min_thr` and `nav_fw_max_thr` — the limits. In navigation, a wing gains altitude with pitch angle and throttle together; cruise throttle that's too low during a climb leads to a stall.

### Auto launch
NAV LAUNCH mode: the aircraft waits for the throw, detects the start by acceleration, after `nav_fw_launch_motor_delay` smoothly brings throttle up to `nav_fw_launch_thr`, holds the climb angle `nav_fw_launch_climb_angle` until the `nav_fw_launch_timeout` timeout or until you move the sticks. A hand launch without auto launch means a motor at full throttle next to your fingers; auto launch was invented precisely against that.

### Autotune
AUTOTUNE is a modifier on top of ANGLE/HORIZON/ACRO; it doesn't work in MANUAL. It tunes **feedforward** on each axis and, in ACRO/HORIZON, the rates. **Autotune doesn't touch P and I** — that's a change compared to older versions; you tune them manually before or after. You need to fly with sharp inputs on all three axes for several minutes; an axis without sharp inputs won't get tuned. The result isn't saved automatically: after landing, disarm and use the save stick command (or `save` in the CLI).

### Wing failsafe
The RTH procedure is the obvious choice when you have GPS. LAND on a wing is a downward spiral at preset angles, i.e. a controlled crash. For a wing, checking `failsafe_throttle` under load is mandatory (for LAND without altitude sensors; DROP simply cuts the motor).

### Default numbers and how to set them
`nav_fw_cruise_thr` = 1400, `nav_fw_min_thr` = 1200, `nav_fw_max_thr` = 1700 (PWM throttle units); the throttle-to-pitch link `nav_fw_pitch2thr` = 10 (extra throttle per degree of pitch — a simplified TECS: nose up → more throttle); climb/dive angles `nav_fw_climb_angle` = 20°, `nav_fw_dive_angle` = 15°; loiter radius over a point `nav_fw_loiter_radius` = 7500 cm; cruise speed for the remaining range calculation `nav_fw_cruise_speed` (0 = off). The order: from a manual flight log, find the throttle at which the wing flies level at 1.3–1.5 V_s (the “Wing Aerodynamics” module) → that's `cruise_thr`; `min_thr` — the throttle at which it still doesn't stall in level flight; `max_thr` — by ESC current. `nav_fw_control_smoothness` smooths navigation commands for large wings.

### Auto launch: detection parameters
The throw is detected by acceleration `nav_fw_launch_accel` (1863 cm/s² ≈ 1.9 g) or by velocity `nav_fw_launch_velocity` (300 cm/s — for a swing launch and by GPS speed; a bungee/throw is detected by acceleration), then `nav_fw_launch_motor_delay` (500 ms) → throttle `nav_fw_launch_thr` (1700) at the angle `nav_fw_launch_climb_angle` (18°) until `nav_fw_launch_timeout` (5000 ms) or until the sticks move; `nav_fw_launch_max_angle` (45°) — if the tilt is bigger, the launch is considered failed. Idle throttle before the throw — `nav_fw_launch_idle_thr`/`nav_fw_launch_idle_motor_delay`. Ground check: LAUNCH mode, aircraft in your hand, a sharp forward movement **without the prop** — the motor should “launch” per the OSD.

### Wing landing
Via `nav_rth_allow_landing`/LAND in a mission: approach into the wind (INAV 7.1+ can estimate wind and has landing patterns, `docs/Fixed Wing Landing.md`), glide slope, final `nav_fw_land_dive_angle` (2°) with the motor off — gliding in on the belly. For critical landings — a rangefinder and a landing site without obstacles; otherwise land manually in MANUAL/ANGLE.

### Worked example: first flight of a 1 m wing
MANUAL on a switch; CG per the calculation; `platform_type = AIRPLANE`, Flying Wing mixer, servo direction checked (stick right — right elevon up), `small_angle = 180`; auto launch configured; first throw in ANGLE with auto launch, climb to 50 m, trim `cruise_thr` from level flight, then AUTOTUNE (FF/rates) with 3–5 minutes of sharp inputs, save with the stick command after disarming, then a NAV CRUISE/RTH test at altitude. Log → `nav_fw_pitch2thr` and the angles based on the actual behavior during the climb.

{{diagram:inav-autolaunch|Wing auto launch with default parameters: throw detection, motor delay, climb at a set angle until the timeout or the sticks.}}

## practice
### Step 1. Mixer and reversals
1. `platform_type = AIRPLANE`, the Flying Wing preset, save.
2. Outputs tab: motor on S1, elevons on servos. Check: stick right — right elevon up, left one down; stick back — both up.
3. In ANGLE, tilt the wing by hand: the surfaces should counteract the tilt. If they help it — reverse in the mixer, not on the radio.
4. Servo trims so that the surfaces sit at neutral in MANUAL.

### Step 2. Modes and safety
MANUAL — its own switch. ARM — its own. On a three-position switch: ANGLE / CRUISE / RTH. NAV LAUNCH — on a switch or automatic on arming (depending on the setting).

### Step 3. First flight
1. Balance per the wing's instructions (usually checked with your fingers under the wing).
2. Enable NAV LAUNCH, arm, throw level and with some force.
3. After the climb — ANGLE, evaluate the trim: if the wing drifts, adjust the servo trims, not the stick.
4. A short CRUISE, a short RTH at a small distance.

### Step 4. Autotune
On the next flight: enable AUTOTUNE in ANGLE or ACRO, 3–5 minutes of sharp inputs in roll, pitch and yaw (yaw is often forgotten). Disarm on the ground, then the save stick command. Check `fw_ff_roll`, `fw_ff_pitch` before and after.

## diagnostics
- **Symptom:** after the throw the wing noses down or flips over
  - Possible cause: a reversed elevon or wrong balance.
  - What to do: check how the surfaces react to tilt in ANGLE on the ground, check the center of gravity.
- **Symptom:** loses altitude while climbing in navigation
  - Possible cause: low `nav_fw_cruise_thr`/`nav_fw_max_thr`.
  - What to do: raise the cruise and maximum throttle.
- **Symptom:** autotune doesn't change anything
  - Possible cause: flying in MANUAL, or too few sharp inputs, or expecting P/I to change.
  - What to do: ANGLE/ACRO, sharp inputs on all axes; P/I — manually.
- **Symptom:** auto launch doesn't start the motor
  - Possible cause: the throw wasn't detected (too weak) or a timeout.
  - What to do: throw more energetically, check `nav_fw_launch_*`.
- **Symptom:** navigation loses airspeed in a climb, stall
  - Possible cause: `nav_fw_climb_angle` is large with low `cruise_thr`/`pitch2thr`.
  - What to do: angle 10–15°, higher `pitch2thr`, `cruise_thr` from the log.
- **Symptom:** auto launch triggers in your hand before the throw
  - Possible cause: `nav_fw_launch_accel` is low, shaking.
  - What to do: higher threshold, hold it steady, test without the prop.
- **Symptom:** in loiter the wing “falls” into the circle
  - Possible cause: the radius is too small for the speed, bank is limited.
  - What to do: larger `nav_fw_loiter_radius`, `max_angle` based on the V_s calculation in a turn.

## references
- INAV Mixer (platform type) | https://github.com/iNavFlight/inav/blob/master/docs/Mixer.md | primary | A
- INAV Airplane Autotune | https://github.com/iNavFlight/inav/blob/master/docs/Autotune%20-%20fixedwing.md | primary | A
- INAV Failsafe | https://github.com/iNavFlight/inav/blob/master/docs/Failsafe.md | primary | A
- INAV settings reference (settings.yaml) | https://github.com/iNavFlight/inav/blob/master/src/main/fc/settings.yaml | primary | A

## checklist
- `platform_type = AIRPLANE`, the mixer preset matches the wing
- The surfaces counteract tilt in ANGLE
- MANUAL and ARM on separate switches
- Balance checked, auto launch configured
- Autotune done on all three axes, P/I tuned manually
