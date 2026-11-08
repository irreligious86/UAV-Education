"""Freshness watchdog for an on-board ROS 2 system (ros2-app-arch lab). No ROS imports.

Each monitored input has a maximum age and a severity. The watchdog turns "how old is each
input" into one system state the decision node must respect:

  OK        everything fresh
  DEGRADED  a non-critical input is stale (e.g. perception): keep flying, stop the feature
  FAILSAFE  a critical input is stale (vehicle status, pose): stop commanding, request hold/land

Hysteresis: an input must be fresh for `recover_s` before it counts as recovered, so a flapping
camera does not toggle the mission on and off.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class Level(IntEnum):
    OK = 0
    DEGRADED = 1
    FAILSAFE = 2


@dataclass
class Input:
    name: str
    max_age_s: float
    critical: bool
    last_t: float | None = None
    fresh_since: float | None = None
    stale: bool = True


@dataclass
class Watchdog:
    recover_s: float = 1.0
    inputs: dict = field(default_factory=dict)

    def add(self, name: str, max_age_s: float, critical: bool) -> None:
        self.inputs[name] = Input(name, max_age_s, critical)

    def feed(self, name: str, t: float) -> None:
        i = self.inputs[name]
        if i.last_t is None or t - i.last_t > i.max_age_s:
            i.fresh_since = t                  # first message after a gap starts the recovery clock
        i.last_t = t

    def evaluate(self, t: float):
        level, reasons = Level.OK, []
        for i in self.inputs.values():
            age = None if i.last_t is None else t - i.last_t
            now_stale = age is None or age > i.max_age_s
            if now_stale:
                i.stale = True
            elif i.stale and i.fresh_since is not None and t - i.fresh_since >= self.recover_s:
                i.stale = False
            if i.stale:
                lv = Level.FAILSAFE if i.critical else Level.DEGRADED
                level = max(level, lv)
                reasons.append(f"{i.name} {'missing' if age is None else f'age {age:.2f}s'}")
        return level, reasons
