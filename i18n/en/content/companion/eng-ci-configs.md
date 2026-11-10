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
