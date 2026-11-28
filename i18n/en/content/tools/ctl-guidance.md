---
id: ctl-guidance
title: "Guidance and trajectories: pure pursuit, L1, S-curves, minimum snap"
level: L3
readingTime: 40 min
firmware: ArduPilot 4.5+ (checked against 4.7.3) · PX4 1.15+ (checked against v1.18.0) · Python 3
status: published
tags:
  - guidance
  - trajectories
  - L1
  - S-curve
related:
  - ctl-theory
  - ap-missions
  - ap-plane-tuning
  - ros2-nav
next:
  - ap-plane-tuning
source: content/tools/ctl-guidance.md
source_hash: 202c5d50936d
---

## summary
The controllers hold attitude, velocity and position. But who decides *which* position to hold at each instant so the vehicle follows the mission line, turns smoothly and does not jerk? That is guidance and trajectory generation. This module walks through the layers from the mission down to the controller, the pure pursuit law and its relative L1 in ArduPlane (with the lookahead-distance formula through `NAVL1_PERIOD`), velocity profiles (the trapezoid and the jerk-limited S-curve that ArduCopter uses between waypoints), and minimum snap for a quadrotor, with an explanation of why it is "snap." The simulation code reproduces the module's charts; in the lab you pick the lookahead from the overshoot and the time to converge onto the line.

## theory
### Layers: from waypoints to motors
1. **Mission**: a list of waypoints and actions (the "Missions" module).
2. **Path**: the geometry between waypoints: straight segments, turn arcs, splines (`NAV_SPLINE_WAYPOINT`).
3. **Trajectory**: a path with time: where the vehicle must be at time t, at what velocity and acceleration, within the velocity, acceleration and jerk limits.
4. **Guidance / tracking**: turns the deviation from the path or trajectory into a command (acceleration, bank angle, velocity) for the position controller.

**Path following** does not care about time; all that matters is being on the line. **Trajectory tracking** requires being at the point *on time*: for formation flight, synchronized filming, cooperative maneuvers.

### Pure pursuit
The vehicle "chases" a point on the path a distance L ahead (the lookahead distance). If α is the angle between the velocity vector and the direction to that point, the curvature of the arc that brings the vehicle onto it is κ = 2·sin α / L, and the lateral acceleration is
a = V²·κ = 2·V²·sin α / L.
- Small L: an aggressive approach to the line, overshoot, and sensitivity to position noise.
- Large L: smooth but slow, and the corners of the route get "cut."
- With a 20 m cross-track offset at 10 m/s (simulation below): L = 8 m gives ~3 m of overshoot; L = 20 m gives ~1 m of overshoot and stays inside a ±1 m corridor after 35 m of travel; L = 45 m reaches the corridor only after ~90 m.

{{diagram:chart-pure-pursuit|Pure pursuit from a 20 m offset at 10 m/s: a short lookahead overshoots, a long one takes a long time to reach the line.}}

### L1 in ArduPlane and NPFG in PX4
L1 is the same lateral-acceleration law (ArduPilot uses a gain of 4ζ² instead of 2: a = 4ζ²·V²·sin η / L1, so at ζ = 0.707 it is exactly pure pursuit), but the lookahead distance grows with speed so that the convergence dynamics do not depend on speed:
L1 = (1/π)·ζ·T·V, where T = `NAVL1_PERIOD`, ζ = `NAVL1_DAMPING`, V is the ground speed.
- Example: V = 18 m/s, T = 17 s, ζ = 0.75 → L1 ≈ 0.318·0.75·17·18 ≈ 73 m.
- Reducing `NAVL1_PERIOD` shortens L1: sharper turns, with a risk of weaving (tuning is covered in the "ArduPlane tuning" module).
- The lateral acceleration becomes a bank angle: tan φ = a / g, limited by `ROLL_LIMIT_DEG`.

In PX4, fixed-wing guidance is done by NPFG (nonlinear path following guidance): the same lookahead principle plus explicit handling of wind comparable to the airspeed. When the line cannot be held, NPFG picks a feasible bearing instead of being blown sideways. The period and damping parameters (`NPFG_PERIOD`, `NPFG_DAMPING`) mean the same as in L1.

### Velocity profiles: trapezoid and S-curve
- **Trapezoid**: accelerate at constant acceleration, cruise, decelerate. The acceleration changes as a step, so the jerk (the derivative of acceleration) is infinite. For a copter a step in acceleration is a step in tilt: jerky motion, a swinging payload and camera, overshoot.
- **S-curve** (jerk-limited): acceleration ramps up at a bounded jerk. A 50 m move with v ≤ 10 m/s, a ≤ 5 m/s², jerk ≤ 10 m/s³: the trapezoid takes 7.0 s, the S-curve 7.5 s (+0.5 s for the acceleration ramps), but without steps.
- **ArduCopter** (since 4.1) builds the path between waypoints from S-curves: speed, acceleration and jerk are set by the navigation parameters (`WP_SPD`, m/s; `WP_ACC`, m/s²; `WP_JERK`, m/s³; before Copter 4.7 these were `WPNAV_SPEED`, cm/s; `WPNAV_ACCEL`, cm/s²; `WPNAV_JERK`, m/s³), and corners are rounded so the path passes within `WP_RADIUS_M` of the waypoint (m; before 4.7 `WPNAV_RADIUS`, cm).

{{diagram:chart-scurve|Acceleration during a 50 m move: the trapezoid switches acceleration as a step, the S-curve with bounded jerk, at a cost of 0.5 s.}}

### Minimum snap for a quadrotor
A quadrotor is a differentially flat system: given the trajectory of position and yaw, you can compute everything else. Thrust is determined by acceleration, the body angular velocity by jerk (the third derivative of position), and the roll and pitch torques by **snap** (the fourth derivative; the yaw torque by the second derivative of yaw). That is why the trajectory that minimizes the integral of snap squared gives the smoothest motor commands. In practice: between waypoints, piecewise polynomials on each axis (7th order is the lowest that can minimize snap; the paper allows any order n), continuous up to snap at the joints, with coefficients from a quadratic program (Mellinger, Kumar, 2011). Such trajectories are generated on the companion and sent to the autopilot as position targets **together with velocity and acceleration** (feedforward); otherwise the position controller lags.

### Feedforward: not just position
If the companion sends only position, the controller learns that it has to accelerate only once there is already an error, and the vehicle lags in turns. `SET_POSITION_TARGET_LOCAL_NED` lets you send position, velocity and acceleration at once (the `type_mask` bitmask): the position controller only has to close the remaining error.

### Where it fits

- **Takes in:** mission waypoints and splines (`ap-missions`); the `WP_SPD`, `WP_ACC`, `WP_JERK` limits; position and velocity from the estimator (`ap-ekf`); the bank limit `ROLL_LIMIT_DEG` (`ap-plane-tuning`).
- **Hands off:** an acceleration, bank or velocity command to the position controller and the cascade below it (`ctl-theory`); the L1 formula to `NAVL1_PERIOD` tuning (`ap-plane-tuning`); targets with feedforward through `SET_POSITION_TARGET_LOCAL_NED` (`ap-companion`).
- **If you get this wrong:** too short a lookahead (`NAVL1_PERIOD`) → overshoot of the line and sensitivity to position noise, the plane weaves after turns (`ap-plane-tuning`). The companion sends only position without velocity and acceleration → the controller learns about the acceleration from the error that has already built up → the vehicle lags in turns (`ap-companion`).

## practice
### Step 1. Pure pursuit in simulation
The script reproduces the module's chart and computes the overshoot and the distance to entering the ±1 m corridor:
```python
import math

def pursuit(L, y0=20.0, V=10.0, a_max=8.0, T=15.0, dt=0.02):
    """Kinematic vehicle, path = the x axis. Returns overshoot (m) and distance to settle within 1 m."""
    x, y, psi = 0.0, y0, 0.0
    overshoot, settle_x = 0.0, None
    for _ in range(int(T / dt)):
        dx = math.sqrt(L * L - y * y) if abs(y) < L else 0.0   # lookahead point on the path
        alpha = math.atan2(-y, max(dx, 0.5)) - psi
        alpha = math.atan2(math.sin(alpha), math.cos(alpha))
        a = max(-a_max, min(a_max, 2 * V * V * math.sin(alpha) / L))   # a_lat = 2V² sin α / L
        psi += a / V * dt
        x += V * math.cos(psi) * dt
        y += V * math.sin(psi) * dt
        overshoot = max(overshoot, -y)
        if abs(y) > 1.0:
            settle_x = None
        elif settle_x is None:
            settle_x = x
    return overshoot, settle_x

for L in (8, 20, 45):
    o, s = pursuit(L)
    print(f"L = {L:2d} m: overshoot {o:.1f} m, within ±1 m from {s:.0f} m")
# L =  8 m: overshoot 3.0 m, within ±1 m from 35 m
# L = 20 m: overshoot 1.0 m, within ±1 m from 35 m
# L = 45 m: overshoot 0.9 m, within ±1 m from 91 m
```
Sweep L from 5 to 50 m in steps of 5, plot the overshoot and the distance to the corridor against L, and choose L for 10 and 20 m/s. Add ±1 m of position noise and repeat: what happens with small L?

### Step 2. L1 for your own plane
Use the formula to compute L1 for your plane at cruise speed with `NAVL1_PERIOD` 12, 17, 22. Compare it with the size of the turns in your mission: if L1 is more than half a segment, the corners will be cut badly.

### Step 3. Trapezoid and S-curve
Write a generator for both profiles for a move D with limits v, a, j (for the S-curve, with acceleration ramp-up and ramp-down phases). Check numerically: durations of 7.0 and 7.5 s for the example from the theory; the maximum jerk of the S-curve does not exceed the limit.

### Step 4. SITL: jerk and corner rounding
ArduCopter SITL, a 50×50 m square mission. Two runs with different navigation jerk limits (the default and 2× lower). In the log, look at the tilt (`ATT`) and the acceleration in the turns. Describe how the time to fly the square and the maximum tilt change.

Self-check: the lab is done when the step 1 script prints the same three lines as the code comments (overshoot 3.0 / 1.0 / 0.9 m, corridor from 35 / 35 / 91 m), your choice of L for 10 and 20 m/s is backed by the overshoot and corridor-distance chart (with and without noise), the L1 formula on the theory example (V = 18 m/s, T = 17 s, ζ = 0.75) gives ≈ 73 m and is then computed for your plane at three periods, the profile generator on the theory example gives 7.0 s for the trapezoid and 7.5 s for the S-curve with jerk no higher than 10 m/s³, and the SITL comparison is recorded as numbers: time to fly the square and maximum tilt in both runs.

**Reference answer for self-check.** Correct result: with position noise, small L makes the vehicle weave (the aggressive approach to the line turns into sensitivity to noise), and with a lower jerk limit the tilt in turns builds up more smoothly at the cost of a longer flight time. Typical wrong results: (1) the S-curve came out at 7.0 s, like the trapezoid: the generator has no acceleration ramp-up and ramp-down phases; (2) L1 is more than half a mission segment: the corners will be cut badly, the period is too large for this mission.

## diagnostics
- **Symptom:** the vehicle weaves around the line
  - Possible cause: lookahead too short (L, `NAVL1_PERIOD`), position noise, a poorly tuned roll loop.
  - What to do: increase the lookahead, check the inner loops, filter the position.
- **Symptom:** route corners are cut badly
  - Possible cause: a lookahead or corner radius that is large relative to the segment length.
  - What to do: a shorter lookahead or radius, longer segments, waypoints placed at the corners.
- **Symptom:** the copter jerks at the start and end of every segment
  - Possible cause: acceleration steps from a trajectory without a jerk limit (your own generator, position targets only).
  - What to do: S-curves, a jerk limit, velocity and acceleration feedforward.
- **Symptom:** the vehicle lags in turns under companion control
  - Possible cause: only position targets are sent.
  - What to do: send velocity and acceleration in `SET_POSITION_TARGET_LOCAL_NED`.
- **Symptom:** strong wind pushes the plane off the line
  - Possible cause: the wind is close to the airspeed, and guidance cannot hold the line.
  - What to do: a higher cruise speed, a route planned around the wind; in PX4, look at what NPFG is doing.

## references
- Park, Deyst, How — A New Nonlinear Guidance Logic for Trajectory Tracking (AIAA GNC 2004) | https://arc.aiaa.org/doi/10.2514/6.2004-4900 | primary | A
- ArduPilot — AP_L1_Control (source) | https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_L1_Control/AP_L1_Control.cpp | primary | A
- Mellinger, Kumar — Minimum snap trajectory generation and control for quadrotors (ICRA 2011) | https://doi.org/10.1109/ICRA.2011.5980409 | primary | A
- ArduPilot — SCurves (source) | https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_Math/SCurve.cpp | primary | A
- PX4 — Fixed-wing position tuning (NPFG) | https://docs.px4.io/v1.17/en/config_fw/position_tuning_guide_fixedwing.html | primary | B

## checklist
- I can tell a path, a trajectory and guidance apart, and path following from trajectory tracking
- I can derive the pure pursuit law and understand the effect of the lookahead distance
- I can compute L1 from `NAVL1_PERIOD`, `NAVL1_DAMPING` and speed
- I can explain why jerk is limited and build an S-curve
- I can explain minimum snap through the differential flatness of a quadrotor
- I send velocity and acceleration feedforward together with position
