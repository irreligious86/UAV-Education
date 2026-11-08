"""Minimal mock of the ArduPilot Lua bindings used by guard.lua, driven from Python via lupa.

It mirrors the real signatures that matter (millis() returns an object with :tofloat(), get_location()
returns nil without a fix, Location lat/lng in 1e-7 degrees, set_mode returns a boolean). It is a unit-test
harness: the SITL test in the course (ap-sitl + pymavlink) is still the acceptance test.
"""
from __future__ import annotations

from pathlib import Path

import lupa

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "guard.lua"


class Vehicle:
    def __init__(self):
        self.t_ms = 0
        self.armed = True
        self.vibe = (5.0, 5.0, 8.0)
        self.latlon = (-35.3636, 149.1660)
        self.fix = True
        self.mode = 3           # AUTO
        self.texts: list[str] = []
        self.params: dict[str, float] = {}
        self.logs: list[tuple] = []
        self.fail_vibration = False


def load(v: Vehicle):
    lua = lupa.LuaRuntime(unpack_returned_tuples=True)
    g = lua.globals()
    mk = lua.eval("function(t) return setmetatable({}, {__index = t}) end")

    def tbl(**fns):
        return mk(lua.table_from({k: (lambda f: (lambda self, *a: f(*a)))(f) for k, f in fns.items()}))

    def vec(x, y, z):
        return tbl(x=lambda: x, y=lambda: y, z=lambda: z)

    def get_vibration():
        if v.fail_vibration:
            raise RuntimeError("bad vibration read")
        return vec(*v.vibe)

    def get_location():
        if not v.fix:
            return None
        la, lo = v.latlon
        return tbl(lat=lambda: int(la * 1e7), lng=lambda: int(lo * 1e7))

    def add_param(key, idx, name, default):
        v.params.setdefault("GRD_" + name, float(default)); return True

    def set_mode(m):
        v.mode = int(m); return True

    g.millis = lambda: tbl(tofloat=lambda: float(v.t_ms))
    g.param = tbl(add_table=lambda *a: True, add_param=add_param, get=lambda n: v.params.get(n))
    g.arming = tbl(is_armed=lambda: v.armed)
    g.ahrs = tbl(get_vibration=get_vibration, get_location=get_location)
    g.vehicle = tbl(set_mode=set_mode)
    g.gcs = tbl(send_text=lambda sev, s: v.texts.append(str(s)))
    g.logger = tbl(write=lambda *a: v.logs.append(a))
    fn, period = lua.execute(SCRIPT.read_text())
    return lua, fn, period


def run(v: Vehicle, fn, seconds: float, period_ms: int = 100, each=None):
    for _ in range(int(seconds * 1000 / period_ms)):
        v.t_ms += period_ms
        if each:
            each(v)
        fn, period_ms = fn()
    return fn
