#!/usr/bin/env python3
"""Self-test for check_lab_log.py on synthetic fixtures (run in CI). Exit 0 when the grader passes
the 'pass' logs and fails the 'fail' logs."""
import json, subprocess, sys, tempfile, pathlib

HERE = pathlib.Path(__file__).parent
CASES = [("failsafe_pass", "failsafe", 0), ("failsafe_fail", "failsafe", 1), ("hover_pass", "hover", 0),
         ("hover_fail", "hover", 1), ("mission_pass", "mission", 0), ("motorfail_pass", "motorfail", 0)]

with tempfile.TemporaryDirectory() as d:
    subprocess.run([sys.executable, str(HERE / "make_fixture_log.py"), d], check=True, stdout=subprocess.DEVNULL)
    bad = 0
    for name, lab, expected in CASES:
        r = subprocess.run([sys.executable, str(HERE / "check_lab_log.py"), str(pathlib.Path(d) / f"{name}.bin"), "--lab", lab],
                           capture_output=True, text=True)
        ok = r.returncode == expected
        print(("ok  " if ok else "BAD ") + f"{name:16s} expected exit {expected}, got {r.returncode}")
        if not ok:
            bad += 1; print(r.stdout)
    # lab result file: marks only when the lab passed
    for name, lab, want in (("motorfail_pass", "motorfail", ["ap-heavy:lab:0", "el-redundancy:lab:2"]), ("failsafe_fail", "failsafe", [])):
        out = pathlib.Path(d) / f"{name}.json"
        subprocess.run([sys.executable, str(HERE / "check_lab_log.py"), str(pathlib.Path(d) / f"{name}.bin"), "--lab", lab, "--json", str(out)],
                       capture_output=True, text=True)
        res = json.loads(out.read_text())
        ok = res["schema"] == "uav-lab-result/1" and res["marks"] == want and res["labs"][0]["lab"] == lab
        print(("ok  " if ok else "BAD ") + f"{name:16s} result file marks {res['marks']}")
        bad += 0 if ok else 1
    sys.exit(1 if bad else 0)
