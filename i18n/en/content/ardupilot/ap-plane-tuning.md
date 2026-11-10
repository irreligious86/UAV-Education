---
id: ap-plane-tuning
title: "ArduPlane Tuning: Wing AUTOTUNE, TECS, L1 Navigation, Landing"
level: L3
readingTime: 40 min
firmware: ArduPlane 4.5+
status: published
tags:
  - ArduPlane
  - AUTOTUNE
  - TECS
  - L1
related:
  - aero-wing
  - ap-tuning
  - ap-quadplane
  - ap-logs
next:
  - ap-safety-fs
source: content/ardupilot/ap-plane-tuning.md
source_hash: 3bf9cd20d57d
---

## summary
“Wing Aerodynamics” explained why a plane flies and what TECS is; “ArduPilot Tuning” covered how a copter is tuned. Here is the order of setting up a plane in ArduPlane, which decides whether AUTO holds altitude and the line or oscillates: preparation (control surfaces, CG, airspeeds), in-flight AUTOTUNE of roll and pitch, TECS from test flights with concrete numbers, the L1 navigation controller on a rectangular mission, and automatic landing with a flare. PX4 equivalents are given at the end — the names differ there (including NPFG navigation), but the logic is the same.

## theory
### Order is everything
Inner loops before outer ones: roll and pitch (control surfaces → angles) → TECS (altitude and airspeed via throttle and pitch) → navigation (the path line via roll) → landing. A poorly tuned pitch looks like “TECS is oscillating altitude,” and a bad roll looks like “L1 is weaving.” Starting from the outer loop means fixing the symptom.

### Preparation before the first tuning
- **Control surfaces and reversals.** In FBWA, tilt the plane by hand: the ailerons and elevator must *counteract* the tilt. In MANUAL the sticks must move the surfaces the right way. A mistake here means a crash on the very first hand launch in a stabilized mode.
- **CG** — per the calculation from “Wing Aerodynamics”; slightly nose-heavy is safer.
- **Airspeeds** (Plane 4.5+, m/s): `AIRSPEED_MIN` (≥ ~1.2 × stall speed), `AIRSPEED_CRUISE`, `AIRSPEED_MAX`; `SCALING_SPEED` — the typical cruise speed; set it before tuning and don't touch it afterward: the gains are scaled from it.
- **Control surface limits.** `RLL2SRV_RMAX`, `PTCH2SRV_RMAX_UP/DN` — the maximum rates the plane can actually achieve; `RLL_RATE_SMAX`, `PTCH_RATE_SMAX` — matched to the servo speed.
- **Trimming.** In FBWA in level flight — `SERVO_AUTO_TRIM = 1` or manual trims; `PTCH_TRIM_DEG` — the pitch angle of level flight.
- **Return point** (rally) and verified failsafes.

### Roll and pitch AUTOTUNE
- Enabling: the AUTOTUNE mode on the mode switch, or a switch with `RCx_OPTION = 107` in FBWA/FBWB/CRUISE.
- `AUTOTUNE_LEVEL` — the target aggressiveness: 6 by default (75 °/s). Slow large wings and gliders — 2–3; above 7 — only after tuning at a lower level.
- `AUTOTUNE_AXES` — which axes to tune; yaw — only with `YAW_RATE_ENABLE = 1`.
- Maneuvers: sharp stick reversals with a short pause at the end point, one axis at a time; learning happens only when the requested rate is large enough. Without telemetry — at least 20 reversals per axis, more is better, until the completion message.
- Saving: P and D are written when an axis finishes, FF and I — when you exit the mode. Exit mid-axis — that axis gets its old values back. `RCx_OPTION = 180` — a switch to compare the old and new gains.
- Result: `RLL_RATE_FF/P/I/D`, `PTCH_RATE_FF/P/I/D`, and the angle → rate relationship via the time constants `RLL2SRV_TCONST` and `PTCH2SRV_TCONST` (0.5 s by default): within τ the plane covers ~63 % of the requested angle.

{{diagram:chart-plane-tconst|Roll response to a 30° step at different time constants: smaller τ — a sharper response, larger — softer; 0.5 s by default.}}

### TECS from test flights
TECS is tuned *after* pitch. The starting values are measured in FBWA, not guessed:
1. `THR_MAX` — so that at cruise the plane climbs at `PTCH_LIM_MAX_DEG`.
2. `TRIM_THROTTLE` — the throttle for level flight at cruise.
3. `PTCH_LIM_MAX_DEG` — full throttle, maximum pitch: airspeed should stay near cruise. If it rises — raise the limit or lower `THR_MAX`; if it drops below `AIRSPEED_MIN` — the opposite.
4. `TECS_CLMB_MAX` — the real climb rate at `THR_MAX` (for electric planes — measure at the end of the battery).
5. `TECS_SINK_MIN` — the sink rate at idle at cruise airspeed; `TECS_SINK_MAX` — the fastest descent without exceeding `PTCH_LIM_MIN_DEG` and `AIRSPEED_MAX`.

Check in LOITER/AUTO: altitude holds within ~10 m with no noticeable pitch oscillation; if it oscillates — `TECS_TIME_CONST` +1. A 50 m climb command: throttle around 80 % of `THR_MAX`, airspeed holds, pitch ~5° below the limit. If it hits `THR_MAX` and loses airspeed — lower `TECS_CLMB_MAX`. Oscillations — `TECS_PTCH_DAMP` in steps of 0.1 (no higher than 0.5 without a noise analysis), then `TECS_TIME_CONST` again. Fine tuning: `TECS_SPDWEIGHT` (0 — altitude priority, 1 — balance, 2 — airspeed, for gliders), `TECS_RLL2THR` — compensation for energy loss in a turn.

### L1 navigation
The L1 controller turns deviation from the line into a roll command. `NAVL1_PERIOD` — the period of “how sharply to return to the line” in seconds: smaller is sharper. `NAVL1_DAMPING` — damping (0.75 by default; don't drop it noticeably below 0.6).
- `ROLL_LIMIT_DEG` — the bank the plane holds without stalling (~50° for slow gliders, ~65° for aerobatic planes).
- A rectangular mission within line of sight, `WP_RADIUS` — about two seconds of flight at cruise.
- Turns are sluggish, the plane overshoots the line — `NAVL1_PERIOD` −5; it weaves after a turn — +1…2. Then adjust `NAVL1_DAMPING` in steps of 0.05.

### Automatic landing
The mission ends with `NAV_LAND` with an approach into the wind. Key parameters: `LAND_FLARE_ALT` (the altitude where the flare starts), `LAND_FLARE_SEC` (how many seconds before touchdown), `TECS_LAND_ARSPD` (approach airspeed), `TECS_LAND_SINK` (sink rate on the glide slope), `LAND_PITCH_DEG` (pitch during the flare). Without a lidar, altitude comes from the barometer, and an error of a few meters is common: a rangefinder for landing (`RNGFND_LANDING = 1`) turns a lottery into a repeatable procedure. The first approaches — with an abort (go-around) at a safe altitude.

### PX4: the same stages
Roll and pitch — `FW_RR_*`, `FW_PR_*` and the fixed-wing autotune; TECS — `FW_T_*` (`FW_T_CLMB_MAX`, `FW_T_SINK_MIN`, `FW_T_SINK_MAX` and others); navigation — NPFG (`NPFG_PERIOD`, `NPFG_DAMPING`), the same idea as L1; landing — `FW_LND_*`. The parameter set depends on the version — check against the Fixed-wing tuning page for your version.

## practice
### Step 1. A SITL plane
`sim_vehicle.py -v ArduPlane --map --console`. Take off in AUTO with the standard mission, switch to FBWA, check that the control surfaces move the right way (in SITL — via the `RCOU` plot). Write down the starting `RLL2SRV_TCONST`, `PTCH2SRV_TCONST`, `NAVL1_PERIOD`, `TECS_*`.

### Step 2. AUTOTUNE
In SITL or in the field (at altitude, in light wind): AUTOTUNE mode, `AUTOTUNE_LEVEL = 6`, roll reversals, then pitch, until the completion message. Compare `RLL_RATE_*`/`PTCH_RATE_*` before and after; in the log (`PIDR`, `PIDP`) — requested vs. actual rate before and after.

### Step 3. TECS
The five tests from the theory in FBWA; write down the measured numbers: level-flight throttle, climb rate, sink rate at idle. Set the parameters; in AUTO — a 50 m climb and descent, check throttle, pitch and airspeed in the `TECS` log (`h`, `dh`, `sp`, `th`). Write down what you changed and why.

### Step 4. L1
A rectangular mission. Three `NAVL1_PERIOD` values (default, −5, −8). In the `NTUN` log — the crosstrack error (XT) after turns. Choose a value and justify it with a plot.

### Step 5. Landing (SITL)
`NAV_LAND` with an approach; play with `LAND_FLARE_ALT` and `TECS_LAND_SINK`. Write down the touchdown sink rate and the rollout.

The lab counts as done when AUTOTUNE is completed with the gains saved, the TECS parameters are justified by measurements, the choice of `NAVL1_PERIOD` is confirmed by the crosstrack error log, and the SITL landing succeeds with a measured touchdown sink rate.

## diagnostics
- **Symptom:** in FBWA the plane immediately rolls over
  - Possible cause: a control surface reversed in stabilization (wrong servo direction or `SERVOn_REVERSED`).
  - What to do: the “tilt by hand — surfaces counteract” check before every first flight after changes.
- **Symptom:** AUTOTUNE goes on forever
  - Possible cause: reversals aren't sharp enough, airspeed is below `AIRSPEED_MIN`, `RLL2SRV_RMAX` is too small.
  - What to do: sharper and all the way to the stop, higher airspeed, check the rate limits.
- **Symptom:** altitude oscillates by ±10–20 m in LOITER
  - Possible cause: under-tuned pitch, `TECS_TIME_CONST` too small, wrong `TECS_CLMB_MAX/SINK_*`.
  - What to do: pitch first, then `TECS_TIME_CONST` +1, re-measure the limits.
- **Symptom:** it loses airspeed in a climb
  - Possible cause: `TECS_CLMB_MAX` exceeds the real climb rate, throttle at `THR_MAX`.
  - What to do: lower `TECS_CLMB_MAX` to the measured value, check at the end of the battery.
- **Symptom:** it weaves after every turn
  - Possible cause: `NAVL1_PERIOD` is too small or roll is poorly tuned.
  - What to do: `NAVL1_PERIOD` +1…2, check roll (`PIDR`).
- **Symptom:** the landing “stabs” into the ground or overshoots
  - Possible cause: barometric altitude error, a late flare, high approach airspeed.
  - What to do: a rangefinder for landing, `LAND_FLARE_ALT/SEC`, `TECS_LAND_ARSPD`, approach into the wind.

## references
- ArduPlane — Automatic tuning with AUTOTUNE | https://ardupilot.org/plane/docs/automatic-tuning-with-autotune.html | primary | A
- ArduPlane — TECS tuning guide | https://ardupilot.org/plane/docs/tecs-total-energy-control-system-for-speed-height-tuning-guide.html | primary | A
- ArduPlane — Navigation tuning (L1) | https://ardupilot.org/plane/docs/navigation-tuning.html | primary | A
- ArduPlane — Automatic landing | https://ardupilot.org/plane/docs/automatic-landing.html | primary | A
- PX4 — Fixed-wing tuning | https://docs.px4.io/main/en/config_fw/ | primary | A

## checklist
- I tune a plane in this order: control surfaces → roll/pitch → TECS → navigation → landing
- I check control surface reversals in a stabilized mode before flight
- I run AUTOTUNE and understand what gets saved and when
- I measure TECS limits with test flights and verify them in the log
- I tune `NAVL1_PERIOD` by the crosstrack error
- I prepare automatic landing and know its main parameters
