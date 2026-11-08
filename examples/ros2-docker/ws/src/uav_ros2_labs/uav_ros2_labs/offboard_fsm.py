"""Offboard mission state machine, independent of ROS and of the autopilot.

The node feeds it observations (armed, in offboard, position, time) and executes the action it
returns. Keeping the logic here means it can be tested with plain pytest, replayed from a bag,
and reused for PX4 (Offboard) and ArduPilot (GUIDED).

States:  WAIT_READY -> STREAM_SETPOINTS -> ARMING -> OFFBOARD -> TAKEOFF -> SQUARE -> LAND -> DONE
Any state  -> ABORT (land) on: lost position, stale vehicle status, operator took over, timeout.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto


class S(Enum):
    WAIT_READY = auto()
    STREAM_SETPOINTS = auto()
    ARMING = auto()
    OFFBOARD = auto()
    TAKEOFF = auto()
    SQUARE = auto()
    LAND = auto()
    DONE = auto()
    ABORT = auto()


@dataclass
class Obs:
    t: float                      # seconds, monotonic
    status_age: float             # seconds since last vehicle status
    pos_valid: bool
    armed: bool
    offboard: bool                # vehicle reports the external-control mode (PX4 Offboard / AP GUIDED)
    pos: tuple = (0.0, 0.0, 0.0)  # local NED, metres
    landed: bool = False


@dataclass
class Action:
    setpoint: tuple | None = None      # local NED position target, or None
    request_arm: bool = False
    request_offboard: bool = False
    request_land: bool = False
    note: str = ""


@dataclass
class OffboardFSM:
    alt: float = 5.0                   # metres above start (positive up)
    side: float = 10.0
    tol: float = 0.5
    prestream_s: float = 1.0           # PX4 needs setpoints before switching to Offboard
    step_timeout_s: float = 30.0
    status_timeout_s: float = 1.0
    state: S = S.WAIT_READY
    _t_state: float = 0.0
    _start: tuple = (0.0, 0.0, 0.0)
    _wp: int = 0
    _was_offboard: bool = False
    log: list = field(default_factory=list)

    def _go(self, s: S, t: float, why: str = "") -> None:
        self.log.append((t, self.state.name, s.name, why))
        self.state, self._t_state = s, t

    def waypoints(self):
        x0, y0, z0 = self._start
        z = z0 - self.alt                                   # NED: up is negative z
        s = self.side
        return [(x0, y0, z), (x0 + s, y0, z), (x0 + s, y0 + s, z), (x0, y0 + s, z), (x0, y0, z)]

    def _hold(self):
        return self.waypoints()[0]

    def step(self, o: Obs) -> Action:
        if self.state in (S.DONE,):
            return Action()
        # safety checks first: they apply in every active state
        if self.state not in (S.WAIT_READY, S.ABORT, S.LAND):
            if o.status_age > self.status_timeout_s:
                self._go(S.ABORT, o.t, "vehicle status stale")
            elif not o.pos_valid:
                self._go(S.ABORT, o.t, "position invalid")
            elif self._was_offboard and not o.offboard and self.state in (S.TAKEOFF, S.SQUARE):
                self._go(S.DONE, o.t, "operator took over: stop sending commands")
                return Action(note="released")
            elif o.t - self._t_state > self.step_timeout_s:
                self._go(S.ABORT, o.t, f"timeout in {self.state.name}")
        if o.offboard:
            self._was_offboard = True

        st = self.state
        if st == S.WAIT_READY:
            if o.pos_valid and o.status_age <= self.status_timeout_s:
                self._start = o.pos
                self._go(S.STREAM_SETPOINTS, o.t, "position valid")
            return Action()
        if st == S.STREAM_SETPOINTS:
            if o.t - self._t_state >= self.prestream_s:
                self._go(S.ARMING, o.t)
            return Action(setpoint=self._start)
        if st == S.ARMING:
            if o.armed:
                self._go(S.OFFBOARD, o.t, "armed")
                return Action(setpoint=self._start)
            return Action(setpoint=self._start, request_arm=True)
        if st == S.OFFBOARD:
            if o.offboard:
                self._go(S.TAKEOFF, o.t, "offboard active")
                return Action(setpoint=self._hold())
            return Action(setpoint=self._start, request_offboard=True)
        if st == S.TAKEOFF:
            target = self._hold()
            if _dist(o.pos, target) < self.tol:
                self._wp = 1
                self._go(S.SQUARE, o.t, "at altitude")
            return Action(setpoint=target)
        if st == S.SQUARE:
            wps = self.waypoints()
            if _dist(o.pos, wps[self._wp]) < self.tol:
                self._wp += 1
                self._t_state = o.t
                if self._wp >= len(wps):
                    self._go(S.LAND, o.t, "square complete")
                    return Action(request_land=True)
            return Action(setpoint=wps[min(self._wp, len(wps) - 1)])
        if st in (S.LAND, S.ABORT):
            if o.landed or not o.armed:
                self._go(S.DONE, o.t, "landed")
                return Action()
            return Action(request_land=True)
        return Action()


def _dist(a, b) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))
