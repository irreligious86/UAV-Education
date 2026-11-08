"""Run: python -m pytest -q examples/inspection/tests"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import geotag  # noqa: E402
import plan  # noqa: E402

LINE = [(50.4500, 30.5200), (50.4520, 30.5200), (50.4520, 30.5240)]   # north, then east


def test_offset_is_parallel_and_on_the_right():
    lat0, lon0 = LINE[0]
    loc = [plan.to_local(a, b, lat0, lon0) for a, b in LINE]
    off = plan.offset_polyline(loc, 15.0)
    # first leg goes north: "right" is east → offset point has larger E
    assert abs(off[0][1] - 15.0) < 1e-6 and abs(off[0][0]) < 1e-6
    # last leg goes east: right is south → offset point has smaller N
    assert abs(off[-1][0] - (loc[-1][0] - 15.0)) < 1e-6
    # the corner keeps 15 m from both legs (mitre)
    assert abs(off[1][1] - 15.0) < 1e-6 and abs(off[1][0] - (loc[1][0] - 15.0)) < 1e-6


def test_mission_structure_and_wpl():
    items = plan.plan(LINE, 15, 30, 5)
    cmds = [i["cmd"] for i in items]
    assert cmds[0] == plan.CMD_TAKEOFF and cmds[-1] == plan.CMD_RTL
    cam = [i for i in items if i["cmd"] == plan.CMD_CAM_DIST]
    assert [c["p1"] for c in cam] == [5, 0]                       # start and stop shooting
    assert cmds.index(plan.CMD_CAM_DIST) == 2                     # after reaching the first line point
    wpl = plan.to_wpl(items, LINE[0])
    assert wpl.startswith("QGC WPL 110\n") and len(wpl.strip().splitlines()) == len(items) + 2
    assert abs(plan.length_m(LINE) - (222.4 + 283.3)) < 3


def make_logs(n=60, missed=(17, 40), offset=3600.25, seed=0):
    rng = random.Random(seed)
    cam = [{"img": k + 1, "t": 100.0 + 1.2 * k + rng.uniform(-0.02, 0.02), "lat": 50.45 + k * 1e-5, "lon": 30.52, "alt": 30.0} for k in range(n)]
    photos = [{"file": f"IMG_{k + 1:04d}.JPG", "t": c["t"] - offset + rng.uniform(-0.1, 0.1)} for k, c in enumerate(cam) if k not in missed]
    return cam, photos


def test_matching_recovers_clock_offset_and_missed_triggers():
    cam, photos = make_logs()
    m = geotag.match(cam, photos)
    assert abs(m["offset_s"] - 3600.25) < 0.15
    assert len(m["pairs"]) == 58 and [c["img"] for c in m["missed_triggers"]] == [18, 41]
    assert all(p["file"] == f"IMG_{c['img']:04d}.JPG" for p, c in m["pairs"])     # no shift after the gaps


def test_naive_index_matching_would_shift():
    cam, photos = make_logs()
    shifted = sum(1 for k, p in enumerate(photos) if p["file"] != f"IMG_{cam[k]['img']:04d}.JPG")
    assert shifted > 40      # pairing by order breaks after the first missed trigger


def test_geojson_findings():
    cam, photos = make_logs()
    m = geotag.match(cam, photos)
    gj = geotag.to_geojson(m["pairs"], {"IMG_0030.JPG": [{"label": "broken insulator", "severity": "high"}]})
    f = gj["features"][0]
    assert f["properties"]["cam_img"] == 30 and f["geometry"]["coordinates"][1] == cam[29]["lat"]
