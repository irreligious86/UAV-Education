"""Grader self-test on synthetic logs. Run: python -m pytest -q examples/blackbox-grader/tests"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_bf_log as g  # noqa: E402
import make_bf_fixture as fx  # noqa: E402


@pytest.fixture(scope="module")
def logs(tmp_path_factory):
    out = {}
    for kind in ("good", "noisy", "sluggish", "oscillating", "saturated", "imbalanced", "no_rpm", "no_unfilt"):
        p = tmp_path_factory.mktemp("bb") / f"{kind}.csv"
        fx.write_csv(str(p), fx.make(kind, seconds=5.0))
        out[kind] = str(p)
    return out


def failed(res):
    return {c["check"] for c in res["checks"] if not c["pass"]}


def test_good_log_passes_everything(logs):
    r = g.grade(logs["good"], ["filters", "tracking", "motors", "rpm"])
    assert r["pass"], failed(r)
    assert abs(r["sample_rate_hz"] - 2000) < 1


def test_noisy_fails_filters_and_reports_motor_frequency(logs):
    r = g.grade(logs["noisy"], ["filters"])
    assert "roll noise after filters" in failed(r)
    peak = next(c for c in r["checks"] if c["check"] == "roll dominant noise frequency")["value"]
    assert abs(peak - 250) < 5


def test_sluggish_fails_tracking(logs):
    assert {"roll tracking error", "pitch tracking error"} <= failed(g.grade(logs["sluggish"], ["tracking"]))


def test_oscillation_in_hover_is_caught(logs):
    assert {"roll rate with centred sticks", "pitch rate with centred sticks"} <= failed(g.grade(logs["oscillating"], ["tracking"]))


def test_saturated_and_imbalanced_motors(logs):
    assert "motor saturation" in failed(g.grade(logs["saturated"], ["motors"]))
    r = g.grade(logs["imbalanced"], ["motors"])
    assert failed(r) == {"motor imbalance in steady flight"}


def test_missing_fields_fail_with_explanation(logs):
    r = g.grade(logs["no_rpm"], ["rpm"])
    assert not r["pass"] and "dshot_bidir" in r["checks"][0]["meaning"]
    r = g.grade(logs["no_unfilt"], ["filters"])
    assert not r["pass"] and r["checks"][0]["check"] == "gyroUnfilt logged"


def test_header_units_are_normalised(tmp_path):
    p = tmp_path / "u.csv"
    p.write_text("loopIteration, time (us), gyroADC[0] (deg/s)\n0, 0, 1\n1, 500, 2\n2, 1000, 3\n")
    d = g.load_csv(str(p))
    assert set(d) == {"loopIteration", "time", "gyroADC[0]"} and abs(g.sample_rate(d) - 2000) < 1e-6


def test_threshold_override(logs):
    r = g.grade(logs["imbalanced"], ["motors"], overrides={"imbalance_max": 0.5})
    assert r["pass"]
