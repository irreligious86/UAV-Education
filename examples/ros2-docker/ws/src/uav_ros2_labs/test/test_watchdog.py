import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from uav_ros2_labs.watchdog import Level, Watchdog  # noqa: E402


def make():
    w = Watchdog(recover_s=1.0)
    w.add("status", 0.5, critical=True)
    w.add("pose", 0.2, critical=True)
    w.add("targets", 0.5, critical=False)
    return w


def run(w, t0, t1, dt, feeds):
    t = t0
    while t < t1:
        for name in feeds:
            w.feed(name, t)
        t += dt
    return t


def test_missing_inputs_failsafe_at_start():
    lv, why = make().evaluate(0.0)
    assert lv == Level.FAILSAFE and len(why) == 3


def test_all_fresh_is_ok_after_recovery_time():
    w = make()
    t = run(w, 0.0, 1.5, 0.05, ["status", "pose", "targets"])
    assert w.evaluate(t)[0] == Level.OK


def test_perception_loss_degrades_only():
    w = make()
    t = run(w, 0.0, 2.0, 0.05, ["status", "pose", "targets"])
    t = run(w, t, t + 1.0, 0.05, ["status", "pose"])
    lv, why = w.evaluate(t)
    assert lv == Level.DEGRADED and why[0].startswith("targets")


def test_pose_loss_is_failsafe():
    w = make()
    t = run(w, 0.0, 2.0, 0.05, ["status", "pose", "targets"])
    t = run(w, t, t + 0.5, 0.05, ["status", "targets"])
    assert w.evaluate(t)[0] == Level.FAILSAFE


def test_hysteresis_on_flapping_input():
    w = make()
    t = run(w, 0.0, 2.0, 0.05, ["status", "pose", "targets"])
    t = run(w, t, t + 1.0, 0.05, ["status", "pose"])          # targets lost
    t = run(w, t, t + 0.5, 0.05, ["status", "pose", "targets"])  # back, but only 0.5 s
    assert w.evaluate(t)[0] == Level.DEGRADED
    t = run(w, t, t + 0.6, 0.05, ["status", "pose", "targets"])  # now > 1 s fresh
    assert w.evaluate(t)[0] == Level.OK
