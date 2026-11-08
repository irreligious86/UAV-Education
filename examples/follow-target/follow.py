"""Target-following controller as a pure function (project #4 starter).

Input: the tracked target's bounding box in the image (or None), the time, and the controller state.
Output: a body-frame velocity / yaw-rate setpoint for GUIDED (ArduPilot, SET_POSITION_TARGET_LOCAL_NED with
MAV_FRAME_BODY_OFFSET_NED velocities) or Offboard (PX4, TrajectorySetpoint), plus the new state.

Geometry (forward camera, roughly level flight):
  * horizontal offset of the box centre  -> yaw rate (keep the target centred)
  * box height vs the desired height     -> forward speed (a closer target looks bigger)
  * vertical offset of the box centre    -> climb rate (optional, off by default)
Safety:
  * deadband around the set point, rate and speed limits, acceleration limit (slew)
  * target lost longer than `lost_timeout` -> zero velocity (hover), never "keep the last command"
  * target lost briefly -> decay the last command, do not jump to zero (tracker gaps are normal)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Params:
    img_w: int = 640
    img_h: int = 480
    desired_box_h: float = 0.30        # fraction of image height at the desired distance
    k_yaw: float = 1.2                 # rad/s per unit of normalised horizontal error (-1..1)
    k_fwd: float = 6.0                 # m/s per unit of box-height error
    k_climb: float = 0.0               # m/s per unit of vertical error (0 = hold altitude)
    deadband: float = 0.03             # normalised
    max_yaw_rate: float = math.radians(45)
    max_fwd: float = 5.0
    max_back: float = 2.0
    max_climb: float = 1.0
    max_accel: float = 2.0             # m/s^2, slew limit on forward speed
    lost_timeout: float = 1.0          # s
    decay_tau: float = 0.3             # s, command decay during short gaps


@dataclass
class State:
    t: float | None = None
    last_seen: float | None = None
    fwd: float = 0.0
    yaw_rate: float = 0.0
    climb: float = 0.0
    mode: str = "searching"            # searching | tracking | coasting | lost


@dataclass
class Setpoint:
    vx: float                          # body forward, m/s
    vz: float                          # body down, m/s (climb = negative)
    yaw_rate: float                    # rad/s, positive = clockwise seen from above (turn right)
    mode: str


def _dead(x: float, d: float) -> float:
    return 0.0 if abs(x) < d else x - math.copysign(d, x)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def step(box, t: float, st: State, p: Params = Params()) -> tuple[Setpoint, State]:
    """box: (x, y, w, h) in pixels or None. Returns the setpoint and the new state (input state untouched)."""
    dt = 0.0 if st.t is None else max(0.0, t - st.t)
    ns = State(**{k: getattr(st, k) for k in st.__dataclass_fields__})
    ns.t = t
    if box is not None:
        x, y, w, h = box
        ex = ((x + w / 2) - p.img_w / 2) / (p.img_w / 2)          # -1 (left) .. +1 (right)
        ey = ((y + h / 2) - p.img_h / 2) / (p.img_h / 2)          # -1 (top) .. +1 (bottom)
        eh = p.desired_box_h - h / p.img_h                         # >0: target too small -> move closer
        yaw = _clamp(p.k_yaw * _dead(ex, p.deadband), -p.max_yaw_rate, p.max_yaw_rate)
        fwd_cmd = _clamp(p.k_fwd * _dead(eh, p.deadband / 2), -p.max_back, p.max_fwd)
        climb = _clamp(-p.k_climb * _dead(ey, p.deadband), -p.max_climb, p.max_climb)   # target low in image -> descend
        # slew-limit forward speed (first call: dt = 0, so we start from the previous speed, i.e. rest)
        ns.fwd = st.fwd + _clamp(fwd_cmd - st.fwd, -p.max_accel * dt, p.max_accel * dt)
        ns.yaw_rate, ns.climb, ns.last_seen, ns.mode = yaw, climb, t, "tracking"
    else:
        gap = math.inf if st.last_seen is None else t - st.last_seen
        if gap > p.lost_timeout:
            ns.fwd = ns.yaw_rate = ns.climb = 0.0
            ns.mode = "lost" if st.last_seen is not None else "searching"
        else:
            k = math.exp(-dt / p.decay_tau) if dt > 0 else 1.0
            ns.fwd, ns.yaw_rate, ns.climb = st.fwd * k, st.yaw_rate * k, st.climb * k
            ns.mode = "coasting"
    return Setpoint(ns.fwd, -ns.climb, ns.yaw_rate, ns.mode), ns
