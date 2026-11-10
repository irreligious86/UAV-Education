---
id: ctl-guidance
title: "Guidance and Trajectories: Pure Pursuit, L1, S-Curves, Minimum Snap"
level: L3
readingTime: 40 min
firmware: ArduPilot 4.5+ · PX4 1.15+ · Python 3
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
source_hash: 9df9dc0d8b58
---

## summary
The controllers in this course hold angle, velocity and position. But who decides *which* position to hold at each moment so the vehicle follows the mission line, turns smoothly and doesn't jerk? That's guidance and trajectory generation. This module walks through the layers from the mission down to the controller, the pure pursuit law and its relative L1 in ArduPlane (with the lookahead distance formula via `NAVL1_PERIOD`), velocity profiles — the trapezoid and the jerk-limited S-curve that ArduCopter uses to fly between waypoints — and minimum snap for a quadcopter, with an explanation of why it's “snap” specifically. The simulation code reproduces the module's plots; the lab is to choose the lookahead from the overshoot and the time to converge onto the line.

## theory
### Layers: from waypoints to motors
1. **Mission** — a list of waypoints and actions (the “Missions” module).
2. **Path** — the geometry between waypoints: segments, turn arcs, splines (`NAV_SPLINE_WAYPOINT`).
3. **Trajectory** — a path with time: where the vehicle must be at time t, with what velocity and acceleration, within the velocity, acceleration and jerk limits.
4. **Guidance / tracking** — turns the deviation from the path or trajectory into a command (acceleration, bank, velocity) for the position controller.

**Path following** doesn't care about time — the point is to be on the line. **Trajectory tracking** requires being at the point *on time* — for formations, synchronized filming, cooperative maneuvers.

### Pure pursuit
The vehicle “chases” a point on the path that lies a distance L ahead (the lookahead distance). If α is the angle between the velocity vector and the direction to that point, the curvature that brings the vehicle onto it along an arc is κ = 2·sin α / L, and the lateral acceleration is
a = V²·κ = 2·V²·sin α / L.
- Small L — sharp convergence onto the line, overshoot and sensitivity to position noise.
- Large L — smooth but slow, and the route corners get “cut.”
- Starting 20 m to the side at 10 m/s (simulation below): L = 8 m — overshoot ~3 m; L = 20 m — overshoot ~1 m, within the ±1 m corridor after 35 m of path; L = 45 m — within the corridor only after ~90 m.

{{diagram:chart-pure-pursuit|Pure pursuit from 20 m to the side at 10 m/s: a short lookahead gives overshoot, a long one gives slow convergence onto the line.}}

### L1 in ArduPlane and NPFG in PX4
L1 is the same lateral acceleration law (in ArduPilot with a gain of 4ζ² instead of 2: a = 4ζ²·V²·sin η / L1; at ζ = 0.707 it's exactly pure pursuit), but the lookahead distance grows with speed so that the convergence dynamics don't depend on speed:
L1 = (1/π)·ζ·T·V, where T = `NAVL1_PERIOD`, ζ = `NAVL1_DAMPING`, V is the ground speed.
- Example: V = 18 m/s, T = 17 s, ζ = 0.75 → L1 ≈ 0.318·0.75·17·18 ≈ 73 m.
- Reducing `NAVL1_PERIOD` shortens L1 — sharper turns, risk of weaving (tuning is covered in the “ArduPlane Tuning” module).
- The lateral acceleration is turned into bank: tan φ = a / g, limited by `ROLL_LIMIT_DEG`.

In PX4, fixed-wing guidance is done by NPFG (nonlinear path following guidance): the same lookahead principle plus explicit handling of wind comparable to the airspeed — when the line can't be held, NPFG picks a feasible heading instead of being “blown” sideways. The period and damping parameters (`NPFG_PERIOD`, `NPFG_DAMPING`) mean the same as in L1.

### Velocity profiles: trapezoid and S-curve
- **Trapezoid**: acceleration at constant rate, cruise, deceleration. Acceleration changes in a step — the jerk (the derivative of acceleration) is infinite. For a copter, a step in acceleration = a step in tilt: jerking, swinging of the payload and camera, overshoot.
- **S-curve** (jerk-limited): acceleration ramps up with limited jerk. A 50 m move with v ≤ 10 m/s, a ≤ 5 m/s², jerk ≤ 10 m/s³: trapezoid — 7.0 s, S-curve — 7.5 s (+0.5 s for the acceleration ramp time), but with no steps.
- **ArduCopter** (since 4.1) builds the waypoint path from S-curves: velocity, acceleration and jerk are set by the navigation parameters (`WPNAV_SPEED`, cm/s; `WPNAV_ACCEL`, cm/s²; `WPNAV_JERK`, m/s³; in Copter 4.7 — `WP_SPD`, m/s; `WP_ACC`, m/s²; `WP_JERK`, m/s³), and route corners are rounded with radius `WPNAV_RADIUS` (4.7 — `WP_RADIUS_M`).

{{diagram:chart-scurve|Acceleration during a 50 m move: the trapezoid switches acceleration in a step, the S-curve with limited jerk, at a cost of 0.5 s.}}

### Minimum snap for a quadcopter
A quadcopter is a differentially flat system: knowing the position and heading trajectory, you can compute everything else. Thrust is determined by acceleration, the body angular rate by jerk (the third derivative of position), and the motor torques by **snap** (the fourth derivative). That's why the trajectory with the minimum integral of snap squared gives the smoothest motor commands. In practice: 7th-order polynomials per axis between waypoints, continuous up to snap at the joints, with coefficients from a quadratic optimization problem (Mellinger, Kumar, 2011). Such trajectories are built on the companion and sent to the autopilot as position targets **together with velocity and acceleration** (feedforward), otherwise the position controller lags.

### Feedforward: not just position
If the companion sends only position, the controller learns it needs to accelerate only once the error already exists — the vehicle lags in turns. `SET_POSITION_TARGET_LOCAL_NED` lets you send position, velocity and acceleration at once (the `type_mask`): the position controller only has to catch up with the residual error.

## practice
### Step 1. Pure pursuit in simulation
The script reproduces the module's plot and computes the overshoot and the distance until entering the ±1 m corridor:
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
Sweep L from 5 to 50 m in steps of 5, plot the overshoot and the distance to the corridor against L, choose L for 10 and 20 m/s. Add ±1 m position noise and repeat: what happens with small L?

### Step 2. L1 of your own plane
Use the formula to compute L1 for your plane at cruise speed with `NAVL1_PERIOD` 12, 17, 22. Compare with the size of the turns in your mission: if L1 is more than half a segment, turns will be cut heavily.

### Step 3. Trapezoid and S-curve
Write a generator for both profiles for a move D with limits v, a, j (for the S-curve — the acceleration ramp-up and ramp-down phases). Check numerically: durations of 7.0 and 7.5 s for the example from the theory; the maximum jerk of the S-curve doesn't exceed the limit.

### Step 4. SITL: jerk and corner rounding
ArduCopter SITL, a 50×50 m square mission. Two runs with different navigation jerk limits (half the default and the default). In the log — tilt (`ATT`) and acceleration in the turns. Describe how the completion time and the maximum tilt change.

The lab counts as done when your choice of L is justified by a plot of overshoot and convergence (with and without noise), L1 is computed for your plane, the profile generator gives correct durations and bounded jerk, and the SITL comparison is described with numbers.

## diagnostics
- **Symptom:** the vehicle weaves around the line
  - Possible cause: short lookahead (L, `NAVL1_PERIOD`), position noise, poorly tuned roll.
  - What to do: increase the lookahead, check the inner loops, filter the position.
- **Symptom:** route corners are cut heavily
  - Possible cause: a lookahead or rounding radius that is large relative to the segment length.
  - What to do: a shorter lookahead or radius, longer segments, waypoints at the corners.
- **Symptom:** the copter jerks at the start and end of every segment
  - Possible cause: acceleration steps — a trajectory without a jerk limit (your own generator, position targets only).
  - What to do: S-curves, a jerk limit, velocity and acceleration feedforward.
- **Symptom:** a vehicle controlled by the companion lags in turns
  - Possible cause: only position targets are sent.
  - What to do: send velocity and acceleration in `SET_POSITION_TARGET_LOCAL_NED`.
- **Symptom:** strong wind pushes the plane off the line
  - Possible cause: the wind is close to the airspeed, and guidance can't hold the line.
  - What to do: a higher cruise speed, a route that accounts for the wind; in PX4 — look at the NPFG behavior.

## references
- Park, Deyst, How — A New Nonlinear Guidance Logic for Trajectory Tracking (AIAA GNC 2004) | https://arc.aiaa.org/doi/10.2514/6.2004-4900 | primary | A
- ArduPilot — AP_L1_Control (source) | https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_L1_Control/AP_L1_Control.cpp | primary | A
- Mellinger, Kumar — Minimum snap trajectory generation and control for quadrotors (ICRA 2011) | https://doi.org/10.1109/ICRA.2011.5980409 | primary | A
- ArduPilot — SCurves (source) | https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_Math/SCurve.cpp | primary | A
- PX4 — Fixed-wing position tuning (NPFG) | https://docs.px4.io/main/en/config_fw/position_tuning_guide_fixedwing.html | primary | B

## checklist
- I distinguish path, trajectory and guidance; path following and trajectory tracking
- I can derive the pure pursuit law and understand the effect of the lookahead distance
- I compute L1 from `NAVL1_PERIOD`, `NAVL1_DAMPING` and speed
- I can explain why jerk is limited, and I can build an S-curve
- I can explain minimum snap through the differential flatness of a quadcopter
- I send velocity and acceleration feedforward together with position
