"""Stage 6 thin-module diagram for ros2-app-arch.

ros2-executor-gaps — timeline 2.95…3.55 s of the executor model of practice step 3 (same rules and load:
                     setpoint timer 20 Hz / 1 ms, inference 15 fps / 60 ms with a 400 ms stall at t = 3.0 s;
                     ready timers are taken before subscriptions, as in rclpy):
                     top two lanes — one default (MutuallyExclusive) group, setpoints wait for the stall;
                     bottom two lanes — inference in its own group on a second thread, setpoints keep 50 ms.
"""
from __future__ import annotations

from svg import timeline

SOURCES = [("setpoint", 0.050, 0.001), ("watchdog", 0.100, 0.0005), ("inference", 1 / 15, 0.060)]


def _run(threads, group_of, T=4.0):
    jobs = []
    for name, per, cost in SOURCES:
        for k in range(round(T / per)):
            stall = name == "inference" and k > 0 and k % 45 == 0
            jobs.append((k * per, name, 0.400 if stall else cost))
    jobs.sort()
    free, busy, log = [0.0] * threads, {}, []
    while jobs:
        w = min(range(threads), key=free.__getitem__)
        now = free[w]
        for src in ("setpoint", "watchdog", "inference"):     # overdue timer fires once; camera KEEP_LAST 1
            due = [j for j in jobs if j[1] == src and j[0] <= now]
            for old in due[:-1]:
                jobs.remove(old)
        ready = [j for j in jobs if j[0] <= now and busy.get(group_of[j[1]], 0) <= now]
        if not ready:
            free[w] = min(max(j[0], busy.get(group_of[j[1]], 0)) for j in jobs)
            continue
        ready.sort(key=lambda j: (j[1] == "inference", j[0]))    # rclpy: ready timers before subscriptions
        t, name, cost = ready[0]
        jobs.remove(ready[0])
        free[w] = busy[group_of[name]] = now + cost
        log.append((name, now, now + cost))
    return log


def _lane(log, name, t0, t1, accent=False, min_w=0.006):
    segs = []
    for n, a, b in log:
        if n == name and b > t0 and a < t1:
            a, b = max(a, t0), min(b, t1)
            lab = "" if name == "setpoint" else ("зависание 400 мс" if b - a > 0.2 else "")
            segs.append(((a - t0) * 1000, (a - t0 + max(b - a, min_w)) * 1000, lab, accent))
    return segs


def executor_gaps() -> str:
    t0, t1 = 2.95, 3.55
    one = _run(1, dict(setpoint="A", watchdog="A", inference="A"))
    two = _run(2, dict(setpoint="A", watchdog="A", inference="B"))
    lanes = [
        ("инференс (1)", _lane(one, "inference", t0, t1)),
        ("уставки (1)", _lane(one, "setpoint", t0, t1, True)),
        ("инференс (2)", _lane(two, "inference", t0, t1)),
        ("уставки (2)", _lane(two, "setpoint", t0, t1, True)),
    ]
    return timeline("(1) одна группа колбэков, (2) инференс в своей группе; модель шага 3, 0 = 2.95 с",
                    lanes, (t1 - t0) * 1000, marks=[(50, "зависание 400 мс"), (451, "уставки снова (1 группа)")])


def build(D: dict) -> None:
    D["ros2-executor-gaps"] = executor_gaps()
