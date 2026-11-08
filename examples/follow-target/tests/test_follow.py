"""Run: python -m pytest -q examples/follow-target/tests"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from follow import Params, State, step  # noqa: E402

P = Params()


def box_at(cx, cy, h_frac):
    h = h_frac * P.img_h
    return (cx - h / 2, cy - h / 2, h, h)


def run(boxes, dt=0.05, st=None):
    st = st or State()
    out = []
    for i, b in enumerate(boxes):
        sp, st = step(b, i * dt, st, P)
        out.append(sp)
    return out, st


def test_centred_target_at_right_distance_gives_zero():
    sps, _ = run([box_at(320, 240, 0.30)] * 20)
    assert all(abs(s.vx) < 1e-9 and abs(s.yaw_rate) < 1e-9 for s in sps)


def test_target_right_turns_right_and_small_target_moves_forward():
    sps, _ = run([box_at(500, 240, 0.15)] * 60)
    assert sps[-1].yaw_rate > 0 and sps[-1].vx > 0
    assert sps[-1].yaw_rate <= P.max_yaw_rate + 1e-12 and sps[-1].vx <= P.max_fwd + 1e-12


def test_too_close_backs_off_but_slower():
    sps, _ = run([box_at(320, 240, 0.9)] * 200)
    assert -P.max_back - 1e-9 <= sps[-1].vx < 0


def test_acceleration_is_limited():
    sps, _ = run([box_at(320, 240, 0.05)] * 40, dt=0.05)
    dv = [b.vx - a.vx for a, b in zip(sps, sps[1:])]
    assert max(dv) <= P.max_accel * 0.05 + 1e-9


def test_short_gap_coasts_long_gap_hovers():
    sps, st = run([box_at(500, 240, 0.15)] * 40)
    v0 = sps[-1].vx
    # 0.5 s without detections: coasting, command decays but is not zero
    t = 40 * 0.05
    for k in range(10):
        sp, st = step(None, t + (k + 1) * 0.05, st, P)
    assert sp.mode == "coasting" and 0 < sp.vx < v0
    # beyond lost_timeout: zero command, mode lost
    for k in range(20):
        sp, st = step(None, t + 0.5 + (k + 1) * 0.05, st, P)
    assert sp.mode == "lost" and sp.vx == 0 and sp.yaw_rate == 0


def test_never_seen_is_searching_and_still():
    sp, st = step(None, 0.0, State(), P)
    sp, st = step(None, 5.0, st, P)
    assert sp.mode == "searching" and sp.vx == 0


def test_state_is_not_mutated():
    st = State()
    _, st2 = step(box_at(500, 240, 0.15), 0.0, st, P)
    assert st.mode == "searching" and st2.mode == "tracking"
