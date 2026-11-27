---
id: eng-ci-configs
title: "CI and versioning for configs and code"
level: L3
readingTime: 35 min
firmware: Betaflight · ArduPilot
status: published
added: 2026-11-08
tags:
  - git
  - CI
  - diff all
  - SITL
  - review
related:
  - bf-cli-automation
  - ap-sitl
  - tools-overview
  - eng-method-101
next:
  - eng-systems
source: content/companion/eng-ci-configs.md
source_hash: 7e2ce4e9c154
---

## summary
A drone's configuration is code: whether it flies depends on it. So everything engineers have long done with code applies to it: a change history with explanations, review before applying, automated checks, releases and rollback. This module sets that up for one aircraft or a fleet: Betaflight `diff all` and ArduPilot `.param` in git with meaningful commits, a pull request as the form of review, GitHub Actions with a SITL autotest (mission/failsafe), linters for scripts and schemas for configs, release tags and a changelog. The lab: a CI that fails if failsafe is broken.

## theory
### What to store
```
fleet/
  viking7/
    README.md              # what aircraft it is, hardware, firmware version
    betaflight/diff-all.txt  # diff all after every change
    ardupilot/params.param   # full parameter list (Mission Planner / mavproxy param save)
    notes/CHANGELOG.md     # what changed and why, with dates
    logs/                  # links or small logs per release (large ones go to Releases/LFS)
  tools/
    export_bf.py           # pulls diff all over MSP/CLI
    check_params.py        # invariant checks
    sitl_test.py           # SITL autotest
.github/workflows/ci.yml
```
Rules: one commit — one change with a reason (“D roll 38→42: bounce-back 18%→9%, log 2026-11-08-03”); no reason — no commit. Binary logs do not go into the repository (Git LFS or releases).

### Pull the config automatically
Betaflight: over USB in CLI mode (not MSP: you enter the CLI with the `#` character) — `diff all` from Python (`pyserial`: `#` → wait for `# ` → `diff all` → read until `# `), or export via `betaflight-configurator`. ArduPilot: `mavproxy.py --master=... --cmd="param fetch; param save params.param"` or pymavlink `param_fetch_all` → a sorted text file. Sort and normalize (strip `#` comments with the date) — otherwise the diff is noisy.

### Invariants: checking configs
A script that reads the config and fails on violations of rules you know from the course:
- Betaflight: `failsafe_procedure` is set, `failsafe_delay` within reasonable limits, `motor_poles` = 14 for 2207, `dshot_bidir = ON` with rpm_filter, `vbat_min_cell_voltage` ≥ 330, no `set debug_mode` in the flight profile.
- ArduPilot: `FS_THR_ENABLE ≠ 0`, `BATT_FS_LOW_ACT ≠ 0`, `FENCE_ENABLE = 1` for flights under the rules, `RTL_ALT_M` ≥ the obstacle height at the site (in the README), `ARMING_SKIPCHK = 0` (before 4.7 — `ARMING_CHECK = 1`), `INS_HNTCH_ENABLE = 1` if a notch is needed, `BRD_SAFETY_DEFLT` per policy.
Implementation — JSON Schema/plain Python with a rule table; output — a list of violations with a link to the course module.

### SITL autotest
ArduPilot in CI (Ubuntu runner): build SITL (`./waf configure --board sitl && ./waf copter`) or take a prebuilt image; run `sim_vehicle.py` without a GUI with `--add-param-file params.param`; a pymavlink script: arm in Guided, take off to 10 m, `SIM_RC_FAIL = 1` → expect RTL/LAND mode within 5 s → `assert`; then a 4-waypoint mission → `assert` it is reached. Time — 2–4 minutes. ArduPilot's own `Tools/autotest` is an example of how the developers do it (`autotest.py test.Copter.ThrottleFailsafe`).

{{diagram:ci-config-check-chain|The config-ci job is four checks chained with &&: the schema catches a typo in the manifest, the invariant script a broken failsafe and a diff for the wrong version; any red check blocks the merge.}}

{{diagram:ci-sitl-failsafe-seq|The SITL autotest step by step: after SIM_RC_FAIL = 1 the mode must change to RTL or LAND within 5 s, otherwise the assert fails and the PR cannot be merged.}}

Betaflight: a SITL build checks compilation and the CLI; for PID logic — the `make test` unit tests. For configs — the invariant script.

### Linters and schemas
Python: `ruff`/`flake8` + `black`; Lua (ArduPilot): `luacheck` with the ArduPilot config (`Tools/scripts/run_luacheck.sh` in the ArduPilot repository — same approach); JSON configs — JSON Schema (`check-jsonschema`); YAML — `yamllint`. All of it in CI on every PR.

### Review
PR = change + reason + evidence (before/after log, spectrum, a number). Reviewer checklist: is the reason clear? Risk (failsafe, motors, limits)? Tested in SITL/on the bench? Rollback described? If you are alone — self-review: a PR with a description, green CI, merge a day later (the “sleep on it” effect is real).

### Releases and rollback
Tag `viking7-v12` on the commit you flew with; `CHANGELOG.md` by version; a GitHub release with the `diff all`/`.param` and the check-flight log attached. Rollback — `git checkout viking7-v11 -- viking7/` and load the config. Firmware — its version and build key (Betaflight: `version` and the BUILD KEY from `status`; ArduPilot: the `AUTOPILOT_VERSION` message or `version` in MAVProxy) in the release README.

{{diagram:config-ci|A config change as a code change: pull it, commit it, check invariants and SITL, review it, release it with the option to roll back.}}

## practice
### Step 1. Repository
The structure above; the first commit is the current configs with a README (hardware, versions). `.gitattributes` for LFS on `.bin/.BFL`.

### Step 2. Export by script
`export_bf.py` or `param save` on command; commit “snapshot before tuning”.

### Step 3. Invariants + CI
`check_params.py` with 5+ rules; `.github/workflows/ci.yml`: ruff, check_params on all configs. Break a rule on purpose → CI goes red → fix it.

Starter for ArduPilot (`.param`: lines `NAME,VALUE` or `NAME VALUE`):
```python
import re, sys

RULES = [  # (parameter, predicate, why — with the course module to read)
    ("FS_THR_ENABLE", lambda v: v != 0, "RC failsafe must act (ap-safety-fs)"),
    ("BATT_FS_LOW_ACT", lambda v: v != 0, "low battery must act (ap-safety-fs)"),
    ("FENCE_ENABLE", lambda v: v == 1, "geofence on for field flights (ap-safety-fs)"),
    ("RTL_ALT_M", lambda v: v >= 30, "RTL altitude above site obstacles (ap-safety-fs)"),
    ("INS_HNTCH_ENABLE", lambda v: v == 1, "harmonic notch configured (ap-tuning)"),
]

def load(path):
    params = {}
    for line in open(path):
        m = re.match(r"\s*([A-Z0-9_]+)[,\s]+(-?[\d.eE+-]+)", line)
        if m:
            params[m.group(1)] = float(m.group(2))
    return params

def check(params):
    errs = []
    for name, ok, why in RULES:
        if name not in params:
            errs.append(f"{name}: missing ({why})")
        elif not ok(params[name]):
            errs.append(f"{name} = {params[name]:g}: {why}")
    return errs

if __name__ == "__main__":
    bad = [f"{p}: {e}" for p in sys.argv[1:] for e in check(load(p))]
    print("\n".join(bad) or "all invariants hold")
    sys.exit(1 if bad else 0)
```
Keep rules whose parameters were renamed between versions (`RTL_ALT` → `RTL_ALT_M` in 4.7) with both names, or check the firmware version from the aircraft's README. For Betaflight — the same approach over the `set name = value` lines of `diff all`.

### Step 4. SITL test in CI
A ready-made starter is in the course repository: [examples/sitl-pymavlink](https://github.com/irreligious86/UAV-Education/tree/main/examples/sitl-pymavlink) (`test_failsafe.py` + `ci.yml`). A job with ArduPilot SITL and the test (RC failsafe → RTL/LAND). Break it with `FS_THR_ENABLE = 0` in the `.param` → the test fails. One PR with a parameter change, a description, CI and a merge. The lab: a repository with a readable history, a SITL test in CI, one change through a PR.

Lab code and output (verbatim from the source module):

```python
"""Check every config listed in fleet.yaml against invariants. Exit 1 on any ERROR.
Betaflight: `diff all` text (4.5.x / 2025.12.x). ArduPilot: .param ("NAME,VALUE" or "NAME VALUE").
"""
import os, re, sys
import yaml  # PyYAML 6.0.4

BF_RENAMED_2025 = {f"d_min_{a}": f"d_max_{a}" for a in ("roll", "pitch", "yaw")}  # meaning flipped too


def load_bf(path):
    text = open(path, encoding="utf-8").read()
    ver = re.search(r"^# Betaflight / \S+ \(\S+\) (\S+)", text, re.M)
    ctx, vals = "master", {}
    for line in text.splitlines():
        if m := re.match(r"(profile|rateprofile) (\d)\s*$", line):
            ctx = f"{m[1]} {m[2]}"
        elif m := re.match(r"set (\S+) = (.*?)\s*$", line):
            vals[(ctx, m[1])] = m[2]
    features = set(re.findall(r"^feature (-?\w+)", text, re.M))
    return (ver[1] if ver else None), vals, features


def check_bf(craft, errs):
    ver, vals, feats = load_bf(craft["config"])
    if ver != craft["firmware"]:
        errs.append(f"firmware in file {ver} != fleet.yaml {craft['firmware']} (bf-cli-automation)")
    major = int(craft["firmware"].split(".")[0])
    master = {k: v for (c, k), v in vals.items() if c == "master"}
    if major >= 2025:
        for (c, k) in vals:
            if k in BF_RENAMED_2025:
                errs.append(f"{c}: {k} does not exist in 2025.12, now {BF_RENAMED_2025[k]} "
                            "with the opposite meaning (bf-intro)")
    if master.get("failsafe_procedure") == "GPS-RESCUE" and "-GPS" in feats:
        errs.append("failsafe_procedure = GPS-RESCUE without feature GPS: firmware resets it "
                    "to DROP on save (config.c validateAndFixConfig) (bf-failsafe)")
    if int(master.get("failsafe_delay", 15)) > 20:
        errs.append(f"failsafe_delay = {master['failsafe_delay']} x0.1 s > 2.0 s (bf-failsafe)")
    for (c, k), v in vals.items():
        if major >= 2025 and (m := re.match(r"d_max_(roll|pitch|yaw)$", k)):
            d = vals.get((c, f"d_{m[1]}"))
            if d is not None and 0 < int(v) < int(d):
                errs.append(f"{c}: {k} = {v} < d_{m[1]} = {d}: zeroed on save (bf-pid)")


def load_ap(path):
    params = {}
    for line in open(path, encoding="utf-8"):
        if m := re.match(r"\s*([A-Z][A-Z0-9_]*)[,\s]+(-?[\d.]+(?:[eE][-+]?\d+)?)\s*(#.*)?$", line):
            params[m[1]] = float(m[2])
    return params


def check_ap(craft, site, errs):
    p = load_ap(craft["config"])
    if len(p) < 300:
        errs.append(f"only {len(p)} parameters: partial export? (eng-ci-configs)")
    rtl_m = p["RTL_ALT_M"] if "RTL_ALT_M" in p else p.get("RTL_ALT", -100) / 100  # cm before 4.7
    skip = p.get("ARMING_SKIPCHK", 0 if p.get("ARMING_CHECK", 1) == 1 else 1)   # 4.7 rename
    rules = [("FS_THR_ENABLE", p.get("FS_THR_ENABLE", 0) != 0, "RC failsafe must act (ap-safety-fs)"),
             ("BATT_FS_LOW_ACT", p.get("BATT_FS_LOW_ACT", 0) != 0, "low battery must act (ap-safety-fs)"),
             ("FENCE_ENABLE", p.get("FENCE_ENABLE", 0) == 1, "geofence on for field flights (ap-safety-fs)"),
             ("RTL_ALT_M", rtl_m >= site["obstacle_m"],
              f"RTL altitude {rtl_m:g} m must clear obstacles {site['obstacle_m']} m (ap-safety-fs)"),
             ("ARMING_SKIPCHK", skip == 0, "no arming checks skipped (ap-safety-fs)"),
             ("INS_HNTCH_ENABLE", p.get("INS_HNTCH_ENABLE", 0) == 1, "harmonic notch configured (ap-tuning)")]
    errs += [f"{name}: {why}" for name, ok, why in rules if not ok]


if __name__ == "__main__":
    fleet = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
    os.chdir(os.path.dirname(os.path.abspath(sys.argv[1])))
    bad = 0
    for craft in fleet["craft"]:
        errs = []
        if not os.path.isfile(craft["config"]):
            errs.append(f"config file {craft['config']} missing")
        elif craft["stack"] == "betaflight":
            check_bf(craft, errs)
        else:
            check_ap(craft, fleet["site"], errs)
        print(f"{craft['name']:8s} {craft['stack']:10s} {craft['firmware']:9s} "
              f"{'OK' if not errs else str(len(errs)) + ' ERROR(S)'}")
        for e in errs:
            print("   ERROR", e)
        bad += len(errs)
    sys.exit(1 if bad else 0)
```

```yaml
# .github/workflows/config-ci.yml
name: config-ci
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
jobs:
  validate:
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1
      - uses: actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0  # v7.1.0
        with:
          python-version: "3.13"
      - run: pip install yamllint==1.38.0 check-jsonschema==0.39.0
      - name: YAML style
        run: yamllint --strict .
      - name: Fleet manifest schema
        run: check-jsonschema --schemafile schema/fleet.schema.json fleet.yaml
      - name: Workflow schema
        run: check-jsonschema --builtin-schema vendor.github-workflows .github/workflows/*.yml
      - name: Config invariants
        run: python3 tools/check_configs.py fleet.yaml
```

```bash
#!/bin/bash
# Local run of the config-ci job, step by step (same commands as .github/workflows/config-ci.yml).
cd "$1" || exit 2
ci() { yamllint --strict . && check-jsonschema --schemafile schema/fleet.schema.json fleet.yaml \
       && check-jsonschema --builtin-schema vendor.github-workflows .github/workflows/*.yml \
       && python3 -I tools/check_configs.py fleet.yaml; echo "CI exit code: $?"; }
p=hex1/ardupilot/params.param; d=viking2/betaflight/diff-all.txt
echo "== A. snapshot as exported"; ci
echo "== B. fix: RC/battery failsafe, fence, RTL 30 m, notch; BF failsafe DROP"
sed -i -e 's/^FS_THR_ENABLE,0$/FS_THR_ENABLE,1/' -e 's/^BATT_FS_LOW_ACT,0$/BATT_FS_LOW_ACT,2/' \
       -e 's/^FENCE_ENABLE,0$/FENCE_ENABLE,1/' -e 's/^RTL_ALT_M,15$/RTL_ALT_M,30/' \
       -e 's/^INS_HNTCH_ENABLE,0$/INS_HNTCH_ENABLE,1/' $p
sed -i 's/^set failsafe_procedure = GPS-RESCUE$/set failsafe_procedure = DROP/' $d; ci
echo "== C. mutation test: FS_THR_ENABLE back to 0"
sed -i 's/^FS_THR_ENABLE,1$/FS_THR_ENABLE,0/' $p; ci
sed -i 's/^FS_THR_ENABLE,0$/FS_THR_ENABLE,1/' $p
echo "== D. firmware bumped in fleet.yaml, diff left from 4.5.3"
sed -i 's/firmware: "4.5.3"/firmware: "2025.12.5"/' fleet.yaml; ci
echo "== E. typo in the manifest: stack: inav, firmware: 4.7"
sed -i -e 's/stack: ardupilot/stack: inav/' -e 's/firmware: "4.7.2"/firmware: "4.7"/' fleet.yaml; ci
```

```text
== A. snapshot as exported
ok -- validation done
ok -- validation done
viking2  betaflight 4.5.3     1 ERROR(S)
   ERROR failsafe_procedure = GPS-RESCUE without feature GPS: firmware resets it to DROP on save (config.c validateAndFixConfig) (bf-failsafe)
hex1     ardupilot  4.7.2     5 ERROR(S)
   ERROR FS_THR_ENABLE: RC failsafe must act (ap-safety-fs)
   ERROR BATT_FS_LOW_ACT: low battery must act (ap-safety-fs)
   ERROR FENCE_ENABLE: geofence on for field flights (ap-safety-fs)
   ERROR RTL_ALT_M: RTL altitude 15 m must clear obstacles 25 m (ap-safety-fs)
   ERROR INS_HNTCH_ENABLE: harmonic notch configured (ap-tuning)
CI exit code: 1
== B. fix: RC/battery failsafe, fence, RTL 30 m, notch; BF failsafe DROP
ok -- validation done
ok -- validation done
viking2  betaflight 4.5.3     OK
hex1     ardupilot  4.7.2     OK
CI exit code: 0
== C. mutation test: FS_THR_ENABLE back to 0
ok -- validation done
ok -- validation done
viking2  betaflight 4.5.3     OK
hex1     ardupilot  4.7.2     1 ERROR(S)
   ERROR FS_THR_ENABLE: RC failsafe must act (ap-safety-fs)
CI exit code: 1
== D. firmware bumped in fleet.yaml, diff left from 4.5.3
ok -- validation done
ok -- validation done
viking2  betaflight 2025.12.5 2 ERROR(S)
   ERROR firmware in file 4.5.3 != fleet.yaml 2025.12.5 (bf-cli-automation)
   ERROR profile 0: d_min_roll does not exist in 2025.12, now d_max_roll with the opposite meaning (bf-intro)
hex1     ardupilot  4.7.2     OK
CI exit code: 1
== E. typo in the manifest: stack: inav, firmware: 4.7
Schema validation errors were encountered.
  fleet.yaml::$.craft[1].stack: 'inav' is not one of ['betaflight', 'ardupilot']
  fleet.yaml::$.craft[1].firmware: '4.7' does not match '^[0-9]+\\.[0-9]+\\.[0-9]+$'
CI exit code: 1
```

```python
"""RC-failsafe test of the FLEET config in ArduCopter SITL: loads copter.parm + the aircraft's .param,
never sets FS_THR_ENABLE itself. Exit 0 = RTL/LAND within 5 s of SIM_RC_FAIL=1, else 1.
Usage: python3 -I sitl_fs_test.py <arducopter> <copter.parm> <aircraft.param> <workdir>
"""
import os, subprocess, sys, time
from pymavlink import mavutil

ardu, parm, fleet, work = sys.argv[1:5]
os.makedirs(work, exist_ok=True)
I = 23                                                 # TCP 5990
sitl = subprocess.Popen([ardu, "-S", "--model", "+", "--speedup", "1", "-I", str(I), "-w",
                         "--defaults", f"{parm},{os.path.abspath(fleet)}", "--home", "50.45,30.52,100,0"],
                        cwd=work, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
code = 1
try:
    time.sleep(2)
    m = mavutil.mavlink_connection(f"tcp:127.0.0.1:{5760 + 10 * I}")
    m.wait_heartbeat(timeout=30)
    m.mav.request_data_stream_send(m.target_system, m.target_component,
                                   mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)
    m.param_fetch_one("FS_THR_ENABLE")
    p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=5)
    print("FS_THR_ENABLE in SITL =", p.param_value)
    t_end = time.time() + 180
    while time.time() < t_end:                         # wait for GPS-based EKF
        msg = m.recv_match(type="STATUSTEXT", blocking=True, timeout=1)
        if msg and "using GPS" in msg.text:
            break
    m.set_mode("GUIDED")
    for _ in range(60):
        m.arducopter_arm(); time.sleep(1)
        m.recv_match(type="HEARTBEAT", blocking=True, timeout=2)
        if m.motors_armed():
            break
    m.mav.command_long_send(m.target_system, m.target_component,
                            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, 10)
    time.sleep(12)
    m.mav.param_set_send(m.target_system, m.target_component, b"SIM_RC_FAIL", 1,
                         mavutil.mavlink.MAV_PARAM_TYPE_REAL32)  # simulated RC loss
    t0 = time.time(); seen = None
    while time.time() - t0 < 5:
        hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
        seen = mavutil.mode_string_v10(hb) if hb else seen
        if seen in ("RTL", "LAND", "SMART_RTL"):
            print(f"PASS: mode {seen} {time.time() - t0:.1f} s after RC loss"); code = 0
            break
    else:
        print(f"FAIL: mode still {seen} 5 s after RC loss")
finally:
    sitl.terminate(); sitl.wait()
sys.exit(code)
# python3 -I sitl_fs_test.py arducopter copter.parm run/hex1/ardupilot/params.param fs_ok   (after case B)
# FS_THR_ENABLE in SITL = 1.0
# PASS: mode RTL 1.0 s after RC loss          exit=0, 60 s
# python3 -I sitl_fs_test.py arducopter copter.parm mut.param fs_mut                     (FS_THR_ENABLE,0)
# FS_THR_ENABLE in SITL = 0.0
# FAIL: mode still GUIDED 5 s after RC loss   exit=1, 64 s
```

## diagnostics
- **Symptom:** diff all differs completely every time
  - Possible cause: order/comments/date in the export.
  - What to do: normalize and sort before committing.
- **Symptom:** SITL in CI does not start/times out
  - Possible cause: the build is slow, no `--no-mavproxy`/headless, ports.
  - What to do: build cache or a prebuilt image, headless launch, wait for heartbeat with a timeout.
- **Symptom:** the test passes even though failsafe is broken
  - Possible cause: the assert checks the wrong thing (mode is not read) or the test does not wait.
  - What to do: verify that the test fails on a broken config (mutation test).
- **Symptom:** I don't remember which config I flew with that time
  - Possible cause: no tags/releases.
  - What to do: a tag on every flight config, a log attached to the release.

## references
- ArduPilot — Autotest framework (Tools/autotest) | https://ardupilot.org/dev/docs/the-ardupilot-autotest-framework.html | primary | A
- GitHub Docs — GitHub Actions workflows | https://docs.github.com/en/actions/writing-workflows | primary | A
- Betaflight — Command Line Interface (CLI) | https://betaflight.com/docs/wiki/guides/current/Cli | primary | A

## checklist
- Configs are in git with “what and why” commits
- Configs are exported by a script, normalized
- Invariants are checked in CI
- A SITL failsafe test runs in CI and fails on a broken config
- Releases are tagged, rollback has been practiced
