---
id: per-tracking
title: "Target tracking and target-based control"
level: L4
readingTime: 40 min
firmware: ArduPilot · PX4
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
source_hash: 0aadcd02c73c
---

## summary
Closing the “camera → error in the frame → velocity command” loop is easy; making it not oscillate and not fly away when the target is lost is an engineering problem. This module assembles it from what you've already covered: the detector and tracker (per-cv), the latency of the chain (camera → inference → command → autopilot → response), control theory (phase margin with 100–200 ms of latency), the GUIDED interfaces (ArduPilot `SET_POSITION_TARGET_LOCAL_NED` with velocities) and Offboard (PX4 `TrajectorySetpoint`), and safeguards (velocity/acceleration limits, a detection watchdog, a target-loss timeout → hover, a geofence, manual takeover). The lab is in SITL with a simulated target; the starter code is in `examples/ros2-skeleton`.

## theory
### From pixel to command
The error in the frame (e_x, e_y) is in normalized coordinates [−1, 1] from the center. For a downward-looking camera: the target offset in meters ≈ h · tan(e·FOV/2), which for small angles is linear in e and proportional to the altitude h. Velocity command: v = K_p · (offset) limited to |v| ≤ v_max. For a forward-facing or tilted camera the geometry is more complex: you need to know the camera angle and the altitude (or the range to the target from the bounding box size), otherwise K_p “floats” with distance. A gimbal with target-based control (ArduPilot `MNT1_*`/`GIMBAL_MANAGER`) splits the jobs: the gimbal keeps the target centered, and the vehicle flies toward the gimbal angles.

Loop structure: the **outer** loop (ours, 10–30 Hz, on the image error) outputs a velocity → the **inner** loop (the autopilot: velocity → angles → rates, 50–400 Hz). The cascade rule from control theory: our loop must be noticeably slower than the autopilot's velocity loop, and because of the latency it will be.

### Latency is the main limiter
The chain: exposure + capture (10–30 ms) → inference (10–50) → tracker/command (1–5) → MAVLink/DDS (2–10) → the autopilot accepts the velocity setpoint and executes it (velocity loop PSC_VELXY_P, time constant 0.3–1 s). In total, 50–150 ms of pure delay + dynamics. With a delay T_d and a gain K_p, a P-type loop starts oscillating at a frequency on the order of 1/(4·T_d) (−90° of phase from the delay + −90° from the “velocity → position” integrator): at T_d = 100 ms that's about 2.5 Hz, and the limit is K_p ≈ π/(2·T_d) ≈ 15 1/s in the ideal case. But the autopilot doesn't change velocity instantly: with a velocity response of τ ≈ 0.4 s, the limit drops to ~10 1/s at 100 ms and ~3.7 1/s at 300 ms, and with velocity and acceleration limits (saturation) even lower: ~7.8 and ~2.8 1/s (simulation in the practice section). The working K_p is chosen 3–5 times below the limit for phase margin, hence the typical 0.5–2 1/s (m/s per meter of error). Techniques: having the tracker predict the target position T_d ahead, filtering the command, a D term on the target velocity (from the tracker), acceleration limiting, and above all reducing the latency.

### Interfaces
**ArduPilot GUIDED**: `SET_POSITION_TARGET_LOCAL_NED` with a `type_mask` that enables only velocities (`0b110111000111` = 3527: position, acceleration, yaw and yaw rate are ignored, vx, vy, vz are used), frame `MAV_FRAME_BODY_OFFSET_NED` (velocity in the vehicle axes, handy for tracking) or `LOCAL_NED`; send at ≥ 2–3 Hz, otherwise after `GUID_TIMEOUT` (3 s) the targets are reset (the vehicle hovers, which is exactly the safeguard). Autopilot limits: `WP_SPD` (before 4.7: `WPNAV_SPEED`), `PSC_*`, `GUID_OPTIONS`. The pilot takes over by switching the mode on the radio, always.
**PX4 Offboard**: `OffboardControlMode` (velocity=true) + `TrajectorySetpoint` (velocity, position NaN) at ≥ 2 Hz (10+ recommended), `COM_OF_LOSS_T` (offboard loss timeout) and `COM_OBL_RC_ACT` (the action); you enter Offboard after a stream of setpoints, arm with `VehicleCommand`. Via MAVROS: `/mavros/setpoint_velocity/cmd_vel_unstamped` in OFFBOARD mode.

### Safeguards (mandatory)
1. **Limits**: v_max (1–3 m/s for the first tests), a_max (1–2 m/s²), altitude fixed or with a lower bound, geofence enabled.
2. **Detection watchdog**: no valid detection for 0.3–0.5 s → a zero-velocity command (hover), not “the last command.”
3. **Target-loss timeout**: 2–5 s without a target → hover and exit the mode (Loiter/Hold), notify the operator; reacquisition only on command.
4. **Sanitization**: drop NaN/infinities and error jumps above a threshold (false detection); a tracker with a minimum number of confirmation frames.
5. **Takeover**: a mode switch from the radio cuts the loop instantly; the companion must not “fight back”: after takeover, publishing stops.
6. **Logs**: the companion logs the error, the command and the tracker status with timestamps, synchronized with the FC log; otherwise analysis is impossible.

### Test plan
SITL + a simulated target (a point moving along a known law, projected into the “frame” from the vehicle position) → a real camera on a test stand (vehicle tethered, the target moves on the floor) → a low flight over an open area with an observer and a pilot with a finger on the switch.

{{diagram:tracking-guards|Mandatory tracking safeguards: target loss, low confidence, minimum distance, autopilot limits and operator priority.}}

## practice
### Step 1. Simulated target in SITL
Script: the target moves in a circle of R = 10 m at 0.5 m/s; a downward “camera” with a 90° FOV: error in the frame = (target − vehicle position)/(h·tan45°), clamped to [−1, 1]; the detection is “lost” with a 5% probability per frame + a 3 s “blind” window once a minute. 20 Hz.

### Step 2. Gain limit: calculation and simulation
Before flying, do the math. A one-dimensional loop model: error from the frame with a delay T_d → velocity command K_p·e → the autopilot executes the velocity with a time constant τ and limits:

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
Change τ (0.2 and 0.8 s, which is the difference between a light and a heavy vehicle) and `a_max`, and write down how the limit shifts. Choose K_p for your latency with a 3–5× margin.

### Step 3. The loop in SITL
A P velocity controller in GUIDED (`BODY_OFFSET_NED`) or Offboard from `examples/ros2-skeleton`: the chosen K_p, v_max = 2, a_max = 2. Record the error over time; add an artificial delay of 100 and 300 ms and raise K_p until it oscillates, then compare the limit you found with the simulation from step 2.

### Step 4. Safeguards
Test each one: watchdog (target gone for 0.5 s → velocity 0), timeout (3 s → Loiter), false detection (error jump → dropped), takeover from the radio (switch the mode in SITL via RC override): the companion goes silent.

### Step 5. Analysis
A combined plot: error, command, actual velocity (`XKF1.VN/VE`), mode; chain latency from the command → velocity cross-correlation. The lab counts as done when the K_p limit is calculated for your latency and confirmed in SITL, the loop works with limits, every safeguard is tested (watchdog, timeout, false detection, takeover), and the chain latency is measured by cross-correlation.

## diagnostics
- **Symptom:** the vehicle oscillates around the target
  - Possible cause: K_p is too high for the latency.
  - What to do: lower K_p, reduce the latency, target prediction, acceleration limiting.
- **Symptom:** slowly catches up with a moving target
  - Possible cause: P only, so there's a steady-state velocity error.
  - What to do: FF on the target velocity from the tracker, a moderate I with anti-windup.
- **Symptom:** jerks on every detection
  - Possible cause: commands from the raw detector without a tracker/filter.
  - What to do: tracker, command filter, acceleration limiting.
- **Symptom:** after losing the target the vehicle flew off on the last command
  - Possible cause: no watchdog, the autopilot held the last velocity until GUID_TIMEOUT.
  - What to do: watchdog 0.5 s → zero velocity; timeout → Loiter.
- **Symptom:** commands aren't accepted
  - Possible cause: not in GUIDED/Offboard, setpoint rate too low, type_mask.
  - What to do: check the mode, ≥ 10 Hz, the mask; look at the `GUIDED` messages/`COM_OF_LOSS_T`.

## references
- ArduPilot — Copter commands in Guided mode (SET_POSITION_TARGET_LOCAL_NED, type_mask) | https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html | primary | A
- PX4 — Offboard mode (OffboardControlMode/TrajectorySetpoint, timeouts) | https://docs.px4.io/main/en/flight_modes/offboard.html | primary | A
- MAVLink — Offboard Control Interface (SET_POSITION_TARGET_LOCAL_NED) | https://mavlink.io/en/services/offboard_control.html | primary | A
- MAVLink — POSITION_TARGET_TYPEMASK | https://mavlink.io/en/messages/common.html#POSITION_TARGET_TYPEMASK | primary | A

## checklist
- I understand the “pixel → meters” geometry and its dependence on altitude
- I estimated the K_p limit from the latency and confirmed it in SITL
- The velocity loop in GUIDED/Offboard works with limits
- The watchdog, target-loss timeout and takeover are tested
- The companion and FC logs are synchronized for analysis
