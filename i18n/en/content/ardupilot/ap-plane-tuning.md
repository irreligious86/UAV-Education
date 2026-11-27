---
id: ap-plane-tuning
title: "Tuning ArduPlane: fixed-wing AUTOTUNE, TECS, L1 navigation, landing"
level: L3
readingTime: 40 min
firmware: ArduPlane 4.7 (checked against 4.7.3)
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
source_hash: 2c29a175d397
---

## summary
"Wing aerodynamics" explained why a plane flies and what TECS is; "Tuning ArduPilot" explained how a copter is tuned. This module gives the order for tuning a plane in ArduPlane, which decides whether AUTO holds altitude and track or oscillates: preparation (control surfaces, center of gravity, airspeeds), AUTOTUNE of roll and pitch in the air, TECS from test flights with concrete numbers, the L1 navigation controller on a rectangular mission, and automatic landing with a flare. The PX4 equivalents are at the end: the names differ (including NPFG navigation), but the logic is the same.

## theory
### Order is what matters most
Inner loops before outer loops: roll and pitch (surfaces → angles) → TECS (height and speed through throttle and pitch) → navigation (track through roll) → landing. A poorly tuned pitch loop looks like "TECS oscillates in altitude", and a poor roll loop looks like "L1 weaves". If you start with the outer loop, you are fixing a symptom.

### Preparation before the first tune
- **Surfaces and reversals.** In FBWA, tilt the plane by hand: the ailerons and elevator must *oppose* the tilt. In MANUAL the sticks must move the surfaces the correct way. A mistake here is a crash on the very first launch in a stabilized mode. Everything in plane setup up to this point (output functions, the elevon and V-tail mixers, both direction checks, the airspeed sensor, failsafe, and the first flight) is covered in `ap-setup-plane`.
- **Center of gravity** from the calculation in "Wing aerodynamics"; slightly nose-heavy is safer.
- **Airspeeds** (Plane 4.5+, m/s): `AIRSPEED_MIN` (≥ ~1.2 times the stall speed), `AIRSPEED_CRUISE`, `AIRSPEED_MAX`; `SCALING_SPEED` is the typical cruise speed; set it before tuning and leave it alone afterwards, because all PID values are scaled from it.
- **Surface limits.** `RLL2SRV_RMAX` and `PTCH2SRV_RMAX_UP/DN` are the maximum rates the plane can actually achieve; `RLL_RATE_SMAX` and `PTCH_RATE_SMAX` are set for the servo speed.
- **Trimming.** In FBWA in level flight use `SERVO_AUTO_TRIM = 1` or manual trims; `PTCH_TRIM_DEG` is the pitch angle offset for level flight.
- **A rally point** and tested failsafes.

### Airspeed sensor: installation and calibration
Whether you need one, and the full `ARSPD_*` table, are in `ap-setup-plane`. In short: on a QuadPlane it is strongly recommended, because the transition completes at an airspeed of max(`AIRSPEED_MIN`, `Q_ASSIST_SPEED`), and without a sensor that is a synthetic estimate from GPS and the wind estimate: a wind error shifts the moment of completion, and without GPS the transition never completes at all (`Q_TRANSITION_MS` is the time after the threshold is reached, not a timeout; see `ap-vtol-modes`). It is useful in wind, for a slow wing, and for automatic landing; the ArduPilot documentation does not recommend one on a first plane because it is extra setup. If you fit one, do it before AUTOTUNE and TECS, because `SCALING_SPEED`, `AIRSPEED_MIN`, and the TECS limits are then based on its readings.

**Step 1. Type and range.** A digital I²C sensor (MS4525DO, MS5525, SDP3x, DLVR, ASP5033, AUAV) or DroneCAN; analog sensors, according to the ArduPilot documentation, are almost out of production and hold their zero worse when the temperature changes. Choose the range from the highest airspeed you will see (a dive, a head-on gust): Δp_max = V_max² / `ARSPD_RATIO`. Take a sensor limit with a margin of ≥ 1.5 × Δp_max (an **estimate**, not a rule from the documentation). With `ARSPD_RATIO = 2`:

| Sensor | Limit, Pa | Speed limit, m/s |
|---|---|---|
| DLVR 5″ H₂O | 1245 | 49.9 |
| DLVR 10″ H₂O | 2491 | 70.6 |
| MS4525DO ±1 psi | 6895 | 117 |

Example: V_max = 30 m/s → 450 Pa, 675 Pa with the margin (2.7″ H₂O), so a DLVR 5″ is enough; an MS4525 also works, but it runs in the bottom 10% of its scale.

**Step 2. Location.** The static holes on the side of the tube must be at least 1 cm ahead of the nose. If the prop is in the nose, put the tube on the wing, at least 30 cm from the fuselage, outside the prop wash. On a QuadPlane the same rule applies to the lift props (an **estimate**: in hover the tube sees their wash as airspeed). Shield the sensor from light.

**Step 3. Zero.** The firmware takes the zero offset at power-up, so cover the tube loosely against the wind. To get a warning when the calibration was done with the tube uncovered, set `ARSPD_OFF_PCNT` (Plane, % of `AIRSPEED_MIN`, 0 disables). The documentation says the DLVR needs no zero calibration, but in the 4.7.2 source only SDP3x and NMEA skip it (`set_use_zero_offset()`), so cover a DLVR too.

**Step 4. Ratio.** Fly two opposite legs at the same throttle along the wind: the average ground speed (`GPS.Spd`) ≈ the airspeed. Example: 24 and 16 m/s → 20 m/s; `ARSP.Airspeed` shows 18 → `ARSPD_RATIO` = 2 × (20/18)² = 2.47. That is within the 1.5–3.0 range; outside it you have a leak in the tubing or a bad location. The other way is `ARSPD_AUTOCAL = 1` and flying circles with frequent heading changes (on a straight route the estimate does not converge), then setting it back to 0. Up to 500 m above sea level `ARSP.Airspeed` differs from true airspeed by less than 3% (ISA: √(1.225/1.167) = 1.024), so you can ignore the correction.

**Step 5. Log check.** `ARSP.U = 1` (otherwise `ARSPD_USE = 0` and TECS does not see the sensor), `ARSP.H = 1` for the whole flight, `ARSP.Offset` barely changes from one power-up to the next, and on opposite legs the average `ARSP.Airspeed` matches the average `GPS.Spd` within ±1 m/s (an **estimate**).

### AUTOTUNE of roll and pitch
- Enabling: AUTOTUNE mode on the flight mode switch, or a switch with `RCx_OPTION = 107` in FBWA/FBWB/CRUISE.
- `AUTOTUNE_LEVEL` is the target aggressiveness: the default is 6 (75 deg/s). Use 2–3 for slow, large wings and gliders; go above 7 only after tuning at a lower level.
- `AUTOTUNE_AXES` selects the axes to tune; yaw only with `YAW_RATE_ENABLE = 1`.
- Maneuvers: sharp stick reversals with a short pause at full deflection, one axis at a time; learning happens only while the demanded rate is high enough. Without telemetry do at least 20 reversals per axis, preferably more, until the completion message.
- Saving: P and D are written when an axis finishes, FF and I when you leave the mode. If you leave in the middle of an axis, the old values come back for that axis. `RCx_OPTION = 180` is a switch for comparing the original and the tuned gains.
- Result: `RLL_RATE_FF/P/I/D`, `PTCH_RATE_FF/P/I/D`, and the angle → rate relation through the time constants `RLL2SRV_TCONST` and `PTCH2SRV_TCONST` (0.5 s by default): within τ the plane covers ~63% of the demanded angle.

{{diagram:chart-plane-tconst|Roll response to a 30° step for different time constants: a smaller τ gives a sharper response, a larger one a softer response; the default is 0.5 s.}}

### TECS from test flights
TECS is tuned *after* pitch. The starting values are measured in FBWA, not guessed:
1. `THR_MAX`: enough for the plane to climb at `PTCH_LIM_MAX_DEG` at cruise speed.
2. `TRIM_THROTTLE`: the throttle for level flight at cruise speed.
3. `PTCH_LIM_MAX_DEG`: at full throttle and maximum pitch, the airspeed should stay near cruise. If it rises, raise the limit or lower `THR_MAX`; if it falls below `AIRSPEED_MIN`, do the opposite.
4. `TECS_CLMB_MAX`: the actual climb rate at `THR_MAX` (on electric planes, measure it at the end of the battery).
5. `TECS_SINK_MIN`: the sink rate at idle and cruise airspeed; `TECS_SINK_MAX`: the fastest descent that stays within `PTCH_LIM_MIN_DEG` and `AIRSPEED_MAX`.

Check in LOITER/AUTO: altitude holds within ~10 m with no noticeable pitch oscillation; if it oscillates, `TECS_TIME_CONST` +1. Command a 50 m climb: throttle around 80% of `THR_MAX`, the airspeed holds, pitch ~5° below the limit. If it hits `THR_MAX` and loses airspeed, lower `TECS_CLMB_MAX`. For oscillation, raise `TECS_PTCH_DAMP` in steps of 0.1 (not above 0.5 without analyzing the noise), then `TECS_TIME_CONST` again. Fine tuning: `TECS_SPDWEIGHT` (0 prioritizes height, 1 is balanced, 2 prioritizes speed, for gliders), `TECS_RLL2THR` compensates for the energy lost in a turn.

### L1 navigation
The L1 controller turns the deviation from the track into a roll command. `NAVL1_PERIOD` is the period, in seconds, of "how sharply to return to the track": smaller is sharper. `NAVL1_DAMPING` is the damping ratio (0.75 by default; do not go noticeably below 0.6).
- `ROLL_LIMIT_DEG`: the bank angle the plane can hold without stalling (~50° for slow gliders, ~65° for aerobatic planes).
- Fly a rectangular mission within visual range, with `WP_RADIUS` about two seconds of flight at cruise speed.
- Sluggish turns with the plane overshooting the track: `NAVL1_PERIOD` −5; weaving after a turn: +1…2. Then adjust `NAVL1_DAMPING` in steps of 0.05.

### Automatic landing
The mission ends with `NAV_LAND` and an approach into the wind. The key parameters: `LAND_FLARE_ALT` (the altitude at which the flare starts), `LAND_FLARE_SEC` (how many seconds before touchdown), `TECS_LAND_ARSPD` (the approach airspeed), `TECS_LAND_SINK` (the sink rate for the final stage), `LAND_PITCH_DEG` (the pitch in the flare). Without a lidar the height comes from the barometer, and an error of several meters is normal: a rangefinder for landing (`RNGFND_LANDING = 1`) turns a lottery into a repeatable procedure. Fly the first approaches with an abort (go-around) at a safe altitude.

### PX4: the same stages
Roll and pitch: `FW_RR_*`, `FW_PR_*`, and the fixed-wing autotune; TECS: `FW_T_*` (`FW_T_CLMB_MAX`, `FW_T_SINK_MIN`, `FW_T_SINK_MAX`, and others); navigation: NPFG (`NPFG_PERIOD`, `NPFG_DAMPING`), the same idea as L1; landing: `FW_LND_*`. The parameter set depends on the version, so check the Fixed-wing tuning guide for your version.

### Place in the system

- **Receives:** a plane with verified surface directions, airspeed limits, and failsafes (`ap-setup-plane`); V_s, cruise speed, and center of gravity from `aero-wing`, which `AIRSPEED_MIN` and `SCALING_SPEED` are set for; the "inner loop before outer loop" rule (`ctl-theory`); the L1 law and the meaning of `NAVL1_PERIOD` (`ctl-guidance`).
- **Provides:** `RLL_RATE_*`, `PTCH_RATE_*`, TECS, and L1 to the AUTO and RTL modes (`ap-missions`); the fixed-wing tune and an `ARSPD_RATIO` verified on opposite legs to the QuadPlane, where the transition completes on airspeed (`ap-quadplane`).
- **If you get it wrong here:** you tuned TECS or L1 before roll and pitch → in a mission "TECS oscillates in altitude" and "L1 weaves", although the cause is in the inner loops (`ap-missions`). `TECS_CLMB_MAX` was measured on a fresh battery → at the end of the flight the plane hits `THR_MAX` and loses airspeed toward `AIRSPEED_MIN`, that is, toward a stall (`aero-wing`).

## practice
### Step 1. SITL plane
`sim_vehicle.py -v ArduPlane --map --console`. Take off in AUTO with the standard mission, switch to FBWA, and check that the surfaces move the right way (in SITL, from the `RCOU` plot). Record the starting `RLL2SRV_TCONST`, `PTCH2SRV_TCONST`, `NAVL1_PERIOD`, and `TECS_*`.

### Step 2. AUTOTUNE
In SITL or in the field (at altitude, in light wind): AUTOTUNE mode, `AUTOTUNE_LEVEL = 6`, roll reversals, then pitch, until the completion message. Compare `RLL_RATE_*`/`PTCH_RATE_*` before and after; in the log (`PIDR`, `PIDP`) compare the target and actual rate before and after.

### Step 3. TECS
Fly the five tests from the theory in FBWA and record the measured numbers: level-flight throttle, climb rate, sink rate at idle. Set the parameters, then in AUTO climb and descend 50 m and check throttle, pitch, and airspeed in the `TECS` log (`h`, `dh`, `sp`, `th`). Record what you changed and why.

### Step 4. L1
A rectangular mission. Three values of `NAVL1_PERIOD` (default, −5, −8). In the `NTUN` log look at the crosstrack error (XT) after the turns. Choose a value and justify it with a plot.

### Step 5. Landing (SITL)
`NAV_LAND` with an approach; experiment with `LAND_FLARE_ALT` and `TECS_LAND_SINK`. Record the vertical speed at touchdown and the ground roll.

Self-check: the lab is done when AUTOTUNE has run to the completion message on roll and on pitch, `RLL_RATE_*`/`PTCH_RATE_*` are recorded before and after, and in `PIDR`/`PIDP` the relative tracking error e = RMS(`Tar` − `Act`) / RMS(`Tar`), calculated over a stretch of reversals before the tune and over a similar stretch after it, went down (e after < e before; if the difference is less than 10%, treat the tune as having changed nothing and check that the gains were actually saved: P and D are written when an axis finishes, FF and I when you leave the mode); the TECS parameters are set from five measurements in FBWA, and in AUTO on a 50 m climb the throttle is around 80% of `THR_MAX`, the airspeed holds, pitch is about 5° below the limit, and in level flight the altitude holds within ~10 m with no oscillation; `NAVL1_PERIOD` is chosen from the plot of the `NTUN` crosstrack error for three values; the landing in SITL succeeds, and the vertical speed at touchdown and the ground roll are recorded for every combination of `LAND_FLARE_ALT` and `TECS_LAND_SINK`.

**Reference for the self-check.** A correct L1 result: after a turn the plane joins the track without overshooting it and without weaving. Typical wrong results: (1) sluggish turns with the plane overshooting the track mean the period is too long, `NAVL1_PERIOD` −5; (2) weaving after a turn means the period is too short, +1…2. For TECS: hitting `THR_MAX` and losing airspeed in a climb means `TECS_CLMB_MAX` is too high; altitude oscillation calls for `TECS_TIME_CONST` +1, but first make sure pitch is tuned: a poor pitch loop looks like "TECS oscillates in altitude".

## diagnostics
- **Symptom:** in FBWA the plane rolls over immediately
  - Possible cause: a reversed surface in stabilization (wrong servo direction or `SERVOn_REVERSED`).
  - What to do: the "tilt it by hand, the surfaces oppose" check before every first flight after a change.
- **Symptom:** AUTOTUNE never finishes
  - Possible cause: the reversals are not sharp enough, the airspeed is below `AIRSPEED_MIN`, `RLL2SRV_RMAX` is too low.
  - What to do: sharper and to full deflection, more airspeed, check the rate limits.
- **Symptom:** altitude oscillates by ±10–20 m in LOITER
  - Possible cause: an undertuned pitch loop, `TECS_TIME_CONST` too low, wrong `TECS_CLMB_MAX/SINK_*`.
  - What to do: pitch first, then `TECS_TIME_CONST` +1, remeasure the limits.
- **Symptom:** it loses airspeed in a climb
  - Possible cause: `TECS_CLMB_MAX` is higher than the actual climb rate, throttle at `THR_MAX`.
  - What to do: lower `TECS_CLMB_MAX` to the measured value, check at the end of the battery.
- **Symptom:** it weaves after every turn
  - Possible cause: `NAVL1_PERIOD` is too low or roll is poorly tuned.
  - What to do: `NAVL1_PERIOD` +1…2, check roll (`PIDR`).
- **Symptom:** the landing digs in or overshoots
  - Possible cause: barometer altitude error, a late flare, a high approach airspeed.
  - What to do: a rangefinder for landing, `LAND_FLARE_ALT/SEC`, `TECS_LAND_ARSPD`, an approach into the wind.

## references
- ArduPlane — Automatic tuning with AUTOTUNE | https://ardupilot.org/plane/docs/automatic-tuning-with-autotune.html | primary | A
- ArduPlane — TECS tuning guide | https://ardupilot.org/plane/docs/tecs-total-energy-control-system-for-speed-height-tuning-guide.html | primary | A
- ArduPlane — Navigation tuning (L1) | https://ardupilot.org/plane/docs/navigation-tuning.html | primary | A
- ArduPlane — Automatic landing | https://ardupilot.org/plane/docs/automatic-landing.html | primary | A
- PX4 — Fixed-wing tuning | https://docs.px4.io/v1.17/en/config_fw/index.html | primary | A
- ArduPlane — Airspeed Sensor (tube location, types, ARSPD_AUTOCAL; accessed 2026-11-22) | https://ardupilot.org/plane/docs/airspeed.html | primary | A
- ArduPilot Plane-4.7.2 — AP_Airspeed.cpp (ARSPD_OFF_PCNT, airspeed formula) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_Airspeed/AP_Airspeed.cpp | primary | A
- ArduPilot Plane-4.7.2 — AP_Airspeed_SDP3X.cpp (a sensor with no zero calibration) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_Airspeed/AP_Airspeed_SDP3X.cpp | primary | A

## checklist
- I tune a plane in this order: surfaces → roll/pitch → TECS → navigation → landing
- I check surface reversals in a stabilized mode before flight
- I run AUTOTUNE and understand what is saved and when
- I measure the TECS limits with test flights and verify them in the log
- I tune `NAVL1_PERIOD` from the crosstrack error
- I prepare an automatic landing and know its main parameters
