---
id: per-tracking
title: "Target tracking and control"
level: L4
readingTime: 40 min
firmware: ArduPilot 4.7 (checked against 4.7.3) · PX4 1.18 (checked against v1.18.0)
status: published
added: 2026-11-08
tags:
  - tracking
  - GUIDED
  - Offboard
  - control loop
  - latency
related:
  - per-cv
  - ap-companion
  - ctl-theory
  - px4-ros2
next:
  - eng-systems
source: content/companion/per-tracking.md
source_hash: fbb0a322b297
---

## summary
Closing the "camera → error in the frame → velocity command" loop is easy; making it not oscillate and not fly away when the target is lost is an engineering problem. This module builds it from what you have already covered: the detector and tracker (per-cv), the latency of the chain (camera → inference → command → autopilot → response), control theory (phase margin with a 100–200 ms delay), the GUIDED interface (ArduPilot `SET_POSITION_TARGET_LOCAL_NED` with velocities) and the Offboard interface (PX4 `TrajectorySetpoint`), and the safeguards (velocity/acceleration limits, a detection watchdog, a target-loss timeout → hover, the geofence, manual takeover). The lab runs in SITL with a simulated target; the starter code is in `examples/ros2-skeleton`.

## theory
### From a pixel to a command
The error in the frame (e_x, e_y) is in normalized coordinates [−1, 1] from the center. For a downward camera, the target offset in meters ≈ h · tan(e·FOV/2): for small angles it is linear in e and proportional to the height h. The velocity command: v = K_p · (offset), limited to |v| ≤ v_max. For a forward or tilted camera the geometry is more complex: you need the camera angle and the height (or the range to the target from the box size), otherwise K_p "drifts" with distance. A gimbal that tracks the target (ArduPilot `MNT1_*`/`GIMBAL_MANAGER`) splits the job: the gimbal keeps the target centered, and the vehicle flies on the gimbal angles.

The loop structure: the **outer** loop (ours, 10–30 Hz, on the image error) outputs a velocity → the **inner** loop (the autopilot: velocity → angles → rates, 50–400 Hz). The cascade rule from control theory: our loop must be noticeably slower than the autopilot velocity loop, and it will be, because of the latency.

### Latency is the main limit
The chain: exposure + capture (10–30 ms) → inference (10–50) → tracker/command (1–5) → MAVLink/DDS (2–10) → the autopilot accepts the velocity setpoint and tracks it (the velocity loop `PSC_NE_VEL_P` (before 4.7, `PSC_VELXY_P`), time constant 0.3–1 s). In total 50–150 ms of pure delay plus the dynamics. With a delay T_d and a gain K_p, a P-type loop starts to oscillate at a frequency of about 1/(4·T_d) (−90° of phase from the delay + −90° from the "velocity → position" integrator): at T_d = 100 ms that is about 2.5 Hz, and the K_p limit ≈ π/(2·T_d) ≈ 15 1/s in the ideal case. But the autopilot does not change velocity instantly: with a velocity response τ ≈ 0.4 s the limit drops to ~10 1/s at 100 ms and ~3.7 1/s at 300 ms, and with velocity and acceleration limits (saturation) even lower: ~7.8 and ~2.8 1/s (the simulation in the practice section). The working K_p is chosen 3–5 times below the limit for phase margin, hence the typical 0.5–2 1/s (m/s per meter of error). Techniques: predicting the target position T_d ahead with the tracker, filtering the command, a D term on the target velocity (from the tracker), limiting the acceleration, and above all reducing the latency.

{{diagram:chart-tracking-kp-limit|The K_p limit falls as the latency grows, and the autopilot dynamics and limits push it even lower: 7.8 1/s at 100 ms and 2.8 1/s at 300 ms; the working K_p is 3–5 times lower.}}

### Interfaces
**ArduPilot GUIDED**: `SET_POSITION_TARGET_LOCAL_NED` with a `type_mask` that enables only the velocities (`0b110111000111` = 3527: position, acceleration, yaw and yaw rate are ignored, vx, vy, vz are used), frame `MAV_FRAME_BODY_OFFSET_NED` (velocity in the vehicle axes, convenient for tracking) or `LOCAL_NED`; send at ≥ 2–3 Hz, otherwise after `GUID_TIMEOUT` (3 s) the targets are cleared (the vehicle stops and hovers, which is exactly the safeguard). The pilot always takes over by switching the mode on the transmitter.

**ArduCopter does not limit the speed in GUIDED with velocity targets.** `WP_SPD` (m/s; before Copter 4.7, `WPNAV_SPEED` in cm/s) is the speed for flying to waypoints and has no effect on a velocity command: `ModeGuided::velaccel_control_run()` passes the target to `AC_PosControl::input_vel_accel_NE_m()` (in 4.6, `input_vel_accel_xy()`), which shapes the trajectory with acceleration and jerk limits only, without a speed limit. Vertically it is the same: `WP_SPD_UP/DN` are not applied to a velocity target. Checked in ArduCopter 4.6.3 SITL: with `WPNAV_SPEED = 300` (in 4.7 that is `WP_SPD = 3`) a 6 m/s command gave 6.1–6.2 m/s; in the 4.7.3 source this path is unchanged. The input filter only rejects NaN and components larger than 1000 m/s. What the autopilot actually enforces on this path:

- acceleration: `WP_ACC` (2.5 m/s²; before 4.7, `WPNAV_ACCEL`, 250 cm/s²), vertically `WP_ACC_Z` (1 m/s²; before 4.7, `WPNAV_ACCEL_Z`, 100 cm/s²); jerk: `PSC_NE_JERK` (5 m/s³; in 4.6, `PSC_JERK_XY`);
- lean angle: `PSC_ANGLE_MAX` (0 = use `ATC_ANGLE_MAX`, 30°; before 4.7, `ANGLE_MAX`, 3000 centidegrees): this is an acceleration limit, not a speed limit; the steady-state speed is limited only by air drag;
- `GUID_TIMEOUT`: the target is cleared when no new commands arrive; `GUID_OPTIONS` has no speed limits;
- the **geofence** is the only boundary that stops a velocity command. With `FENCE_ENABLE = 1` and bit 0 set in `AVOID_ENABLE` (default 3: fence and proximity sensors), `AC_Avoid::adjust_velocity()` cuts the velocity component toward the boundary so that the vehicle stops `FENCE_MARGIN` (2 m) short of the `FENCE_RADIUS` circle, a polygon or `FENCE_ALT_MAX`; the braking is no harder than 1 m/s². With `AVOID_BEHAVE = 0` (default) the vehicle slides along the boundary, with 1 it stops. The companion keeps sending a velocity outward meanwhile, and the error in the frame grows; the companion has to notice that itself. If the boundary is crossed anyway (wind, overshoot), braking for that boundary is turned off and `FENCE_ACTION` fires (default 1: RTL, or Land if RTL is not possible).

Hence the rule: **the companion clips v_max and a_max before sending**; the autopilot parameters are the second line of defense, not the first.

**PX4 Offboard**: `OffboardControlMode` (velocity=true) + `TrajectorySetpoint` (velocity, position NaN) at ≥ 2 Hz (10+ recommended), `COM_OF_LOSS_T` (offboard loss timeout) and `COM_OBL_RC_ACT` (the action); entering Offboard happens after a stream of setpoints, arming is done with a `VehicleCommand`. Through MAVROS: `/mavros/setpoint_velocity/cmd_vel_unstamped` in OFFBOARD mode. Here there is a speed limit: the position controller clips the horizontal velocity at `MPC_XY_VEL_MAX` (default 12 m/s), the vertical at `MPC_Z_VEL_MAX_UP`/`MPC_Z_VEL_MAX_DN` (3/1.5 m/s), the tilt at `MPC_TILTMAX_AIR` (45°). Acceleration in Offboard is not smoothed: a step in the command goes straight into the velocity controller. The PX4 geofence checks the current position and performs `GF_ACTION` (default 2: Hold) once the fence is violated; it does not brake in advance the way ArduPilot does.

### Safeguards (mandatory)
1. **Limits in the companion**: |v| ≤ v_max (1–3 m/s for the first tests) on the vector magnitude, a command change of no more than a_max·dt (a_max 1–2 m/s²), the altitude fixed or with a lower bound. The companion clips because ArduPilot will not limit a velocity command. The second line on the autopilot: the geofence enabled (`FENCE_ENABLE = 1`, `AVOID_ENABLE` with bit 0), and on PX4 also `MPC_XY_VEL_MAX` no higher than the speed you are prepared to see if the companion fails.
2. **Detection watchdog**: no valid detection for 0.3–0.5 s → a zero-velocity command (hover), not "the last command".
3. **Target-loss timeout**: 2–5 s without the target → hover and leave tracking mode, notify the operator (PX4: Hold; ArduCopter: BRAKE or zero velocity in GUIDED, LOITER only with a pilot holding mid throttle: without one LOITER descends, see per-vision-pipeline); reacquisition only on command.
4. **Sanitizing**: NaN/infinities and error jumps above a threshold (false detection) are discarded; a tracker with a minimum number of confirmation frames.
5. **Takeover**: a mode switch on the transmitter breaks the loop instantly; the companion must not "fight" it: after a takeover it stops publishing.
6. **Logs**: the companion logs the error, the command and the tracker status with timestamps, synchronized with the FC log; otherwise analysis is impossible.

### Test plan
SITL + a simulated target (a point moving according to a known law, projected into the "frame" from the vehicle position) → a real camera on a test stand (the vehicle tethered, the target moving on the floor) → a low flight over an open area with an observer and a pilot with a finger on the switch.

{{diagram:tracking-guards|The mandatory tracking safeguards: target loss, low confidence, minimum distance, autopilot boundaries and operator priority.}}

### Where it fits in the system

- **Takes in:** the target ID and position from the tracker (`per-cv`); the pipeline latency T_d (`per-edge-ml`); the phase margin as the criterion for choosing K_p (`ctl-theory`); the GUIDED/Offboard velocity setpoint interface (`ap-companion`).
- **Hands off:** a velocity vector clipped to v_max and a_max to the autopilot velocity loop; a log of the error, the command and the tracker status for analysis; a target for the gimbal (`payload-gimbal`).
- **If you get this wrong:** K_p chosen without accounting for T_d → oscillation at about 1/(4·T_d); in the flight controller log it shows up as velocity oscillations, while the cause is the companion latency (`ctl-theory`). The speed limit left "to the autopilot" → ArduCopter executes the velocity command without a limit, and only the geofence will stop it (`ap-safety-fs`).

## practice
### Step 1. A simulated target in SITL
Script: the target moves in a circle with R = 10 m at 0.5 m/s; a downward "camera" with a 90° FOV: the error in the frame = (target − vehicle position)/(h·tan45°), clipped to [−1, 1]; the detection is "lost" with a 5% probability per frame plus a 3 s "blind" window once a minute. 20 Hz.

### Step 2. The gain limit: calculation and simulation
Before flying, do the math. A one-dimensional loop model: the error from the frame with a delay T_d → a velocity command K_p·e → the autopilot tracks the velocity with a time constant τ and limits:

```python
import math

def run(kp, delay, tau_v=0.4, v_max=3.0, a_max=3.0, dt=0.01, T=30.0):
    """1-D loop: delayed image error -> velocity command -> autopilot velocity lag tau_v.
    Start 5 m off a still target; returns peak |error| over the last 10 s (large = unstable)."""
    n_d = int(round(delay / dt))
    seen = [5.0] * (n_d + 1)                # what the camera reported n_d steps ago
    x, v, tail = 5.0, 0.0, 0.0
    for k in range(int(T / dt)):
        cmd = max(-v_max, min(v_max, -kp * seen[0]))
        dv = max(-a_max * dt, min(a_max * dt, (cmd - v) / tau_v * dt))
        v += dv
        x += v * dt
        seen = seen[1:] + [x]
        if k * dt > T - 10:
            tail = max(tail, abs(x))
    return tail

def critical_kp(delay, **kw):
    lo, hi = 0.05, 30.0
    for _ in range(40):                     # bisection: largest Kp that still settles
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if run(mid, delay, **kw) < 0.05 else (lo, mid)
    return lo

def analytic_kp(delay, tau_v=0.4):
    """Zero phase margin of Kp·e^(-s·Td) / (s·(tau_v·s + 1))."""
    lo, hi = 0.01, 100.0
    for _ in range(100):
        w = (lo + hi) / 2
        lo, hi = (w, hi) if math.atan(w * tau_v) + w * delay < math.pi / 2 else (lo, w)
    return w * math.hypot(1, w * tau_v)

for d in (0.1, 0.3):
    print(f"T_d = {d * 1000:.0f} ms: no dynamics {math.pi / (2 * d):4.1f}, "
          f"with τ = 0.4 s {analytic_kp(d):4.1f}, with v and a limits {critical_kp(d):4.1f}  (1/s)")
# T_d = 100 ms: no dynamics 15.7, with τ = 0.4 s 10.4, with v and a limits  7.8  (1/s)
# T_d = 300 ms: no dynamics  5.2, with τ = 0.4 s  3.7, with v and a limits  2.8  (1/s)
```
Change τ (0.2 and 0.8 s: that is the difference between a light and a heavy vehicle) and `a_max`, and record how the limit shifts. Choose K_p for your own latency with a margin of 3–5 times.

### Step 3. The loop in SITL
A P velocity controller in GUIDED (`BODY_OFFSET_NED`) or Offboard from `examples/ros2-skeleton`: the chosen K_p, v_max = 2, a_max = 2. Record the error over time; add an artificial delay of 100 and 300 ms and raise K_p until it oscillates, then compare the limit you found with the step 2 simulation.

### Step 4. Safeguards
Check each one: the watchdog (target gone for 0.5 s → velocity 0), the timeout (3 s → Loiter with RC throttle at mid, BRAKE without a pilot), a false detection (an error jump → discarded), the takeover from the transmitter (switch the mode in SITL through RC override): the companion goes quiet. Limits: in ArduPilot SITL set `WP_SPD = 3` (on 4.6, `WPNAV_SPEED = 300`) and send 6 m/s bypassing the clipping: the vehicle flies at about 6 m/s, there is no limit on the autopilot side; with the companion clipping, it flies no faster than v_max. Geofence: `FENCE_ENABLE = 1`, `FENCE_RADIUS` 30 m, a command "outward": the vehicle stops about `FENCE_MARGIN` short of the circle, the mode stays GUIDED, and the companion must detect "velocity commanded, no movement".

### Step 5. Analysis
A combined plot: the error, the command, the actual velocity (`XKF1.VN/VE`), the mode; the chain latency from the cross-correlation of command → velocity. Self-check: the lab is done when the K_p limit is calculated for your own latency and confirmed in SITL, the loop works with limits, every safeguard is checked (watchdog, timeout, false detection, takeover), and the chain latency is measured by cross-correlation.

## diagnostics
- **Symptom:** the vehicle oscillates around the target
  - Possible cause: K_p is too high for the latency.
  - What to do: lower K_p, reduce the latency, predict the target, limit the acceleration.
- **Symptom:** it is slow to catch up with a moving target
  - Possible cause: P only, which leaves a steady-state velocity error.
  - What to do: FF on the target velocity from the tracker, a moderate I with anti-windup.
- **Symptom:** jerks on every detection
  - Possible cause: commands from the raw detector without a tracker/filter.
  - What to do: a tracker, a command filter, an acceleration limit.
- **Symptom:** after losing the target the vehicle flew off on the last command
  - Possible cause: no watchdog, the autopilot held the last velocity until GUID_TIMEOUT.
  - What to do: a 0.5 s watchdog → zero velocity; the timeout → Loiter (mid throttle) or BRAKE (no pilot).
- **Symptom:** in GUIDED the vehicle flies faster than `WP_SPD`
  - Possible cause: that is expected: `WP_SPD` has no effect on velocity targets; the companion does not clip the command.
  - What to do: clip |v| ≤ v_max and a_max in the companion; the geofence as the second line.
- **Symptom:** at the edge of the area the vehicle stopped although the velocity command is non-zero
  - Possible cause: the ArduPilot geofence kicked in (`AC_Avoid`, stopping `FENCE_MARGIN` short).
  - What to do: that is by design; the companion must notice "command present, no movement" and go to the timeout/hover, not keep increasing the command.
- **Symptom:** the commands are not accepted
  - Possible cause: not in GUIDED/Offboard, a low setpoint rate, the type_mask.
  - What to do: check the mode, ≥ 10 Hz, the mask; look at the `GUIDED` messages/`COM_OF_LOSS_T`.

## references
- ArduPilot — Copter commands in Guided mode (SET_POSITION_TARGET_LOCAL_NED, type_mask) | https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html | primary | A
- PX4 — Offboard mode (OffboardControlMode/TrajectorySetpoint, timeouts) | https://docs.px4.io/main/en/flight_modes/offboard.html | primary | A
- MAVLink — Offboard Control Interface (SET_POSITION_TARGET_LOCAL_NED) | https://mavlink.io/en/services/offboard_control.html | primary | A
- MAVLink — POSITION_TARGET_TYPEMASK | https://mavlink.io/en/messages/common.html#POSITION_TARGET_TYPEMASK | primary | A
- ArduCopter 4.7.3 — mode_guided.cpp (velaccel_control_run: the velocity target and AC_Avoid) | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.3/ArduCopter/mode_guided.cpp | primary | A
- ArduPilot — Copter Cylindrical Fence (FENCE_*, stopping at the boundary only with Object Avoidance) | https://ardupilot.org/copter/docs/common-ac2_simple_geofence.html | primary | B

## checklist
- I understand the "pixel → meters" geometry and its dependence on height
- I estimated the K_p limit from the latency and confirmed it in SITL
- The velocity loop in GUIDED/Offboard works with limits
- The watchdog, the target-loss timeout and the takeover are checked
- The companion and FC logs are synchronized for analysis
