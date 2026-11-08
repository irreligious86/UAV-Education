"""Project #3 autotests: synthetic DataFlash logs with known defects -> expected findings."""
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "sitl-pymavlink"))

import log_report as lr  # noqa: E402
from make_fixture_log import Log  # noqa: E402


def flight(path, vibe=12.0, clip_step=0, err=False, sats=16, hdop=0.7, track_err=0.5, sag_mohm=25.0):
    lg = Log()
    lg.add("MODE", 0.0, Mode=0, ModeNum=0, Rsn=1)
    lg.add("MODE", 5.0, Mode=5, ModeNum=5, Rsn=1)
    lg.add("MODE", 55.0, Mode=9, ModeNum=9, Rsn=1)
    clip = 0
    for i in range(600):
        t = i * 0.1
        clip += clip_step
        lg.add("VIBE", t, IMU=0, VibeX=vibe * 0.8, VibeY=vibe * 0.9, VibeZ=vibe, Clip=clip, Clip2=0)
        curr = 2.0 if t < 5 else 25.0
        lg.add("BAT", t, Inst=0, Volt=25.0 - curr * sag_mohm / 1000.0 - t * 0.01, Curr=curr)
        lg.add("GPS", t, I=0, Status=3, NSats=sats, HDop=hdop, Lat=50.45, Lng=30.52, Alt=100)
        lg.add("ATT", t, DesRoll=5 * math.sin(t), Roll=5 * math.sin(t) + track_err, DesPitch=0, Pitch=track_err)
        lg.add("CTUN", t, Alt=min(10.0, t))
    if err:
        lg.add("ERR", 30.0, Subsys=16, ECode=2)
    lg.add("MSG", 1.0, Message="ArduCopter V4.6.0")
    lg.write(path)
    return path


def by_check(findings):
    return {f.check: f for f in findings}


def test_clean_flight_is_ok(tmp_path):
    f = by_check(lr.analyse(lr.load(str(flight(tmp_path / "ok.bin")))))
    assert f["vibration"].severity == "ok" and f["clipping"].severity == "ok"
    assert f["gps_sats"].severity == "ok" and f["attitude_tracking"].severity == "ok"
    assert f["error"].severity == "ok"


def test_high_vibration_and_clipping(tmp_path):
    f = by_check(lr.analyse(lr.load(str(flight(tmp_path / "v.bin", vibe=70, clip_step=1)))))
    assert f["vibration"].severity == "fail" and f["clipping"].severity == "fail"


def test_battery_resistance_estimate(tmp_path):
    f = by_check(lr.analyse(lr.load(str(flight(tmp_path / "b.bin", sag_mohm=80)))))
    r = f["battery_resistance"]
    assert r.severity == "warn" and 70 < r.value < 95          # 80 mΩ plus the slow discharge slope


def test_err_and_gps_and_tracking(tmp_path):
    f = lr.analyse(lr.load(str(flight(tmp_path / "e.bin", err=True, sats=7, hdop=2.2, track_err=4))))
    c = by_check(f)
    assert c["error"].severity == "fail"
    assert c["gps_sats"].severity == "warn" and c["gps_hdop"].severity == "warn"
    assert c["attitude_tracking"].severity in ("warn", "fail")
    assert lr.verdict(f) == "fail"


def test_cli_writes_json_and_html(tmp_path):
    log = flight(tmp_path / "c.bin")
    r = subprocess.run([sys.executable, str(HERE.parent / "log_report.py"), str(log), "--json", str(tmp_path / "f.json"),
                        "--html", str(tmp_path / "r.html")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    d = json.loads((tmp_path / "f.json").read_text())
    assert d["verdict"] == "ok" and any(x["check"] == "vibration" for x in d["findings"])
    h = (tmp_path / "r.html").read_text()
    assert "<svg" in h and "LOITER" in h
