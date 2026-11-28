---
id: eng-ci-configs
title: "CI and versioning for configs and code"
level: L3
readingTime: 50 min
firmware: "Betaflight 4.5.3 / 2025.12.5 · ArduPilot 4.7 (checked against 4.7.3; lab on a SITL 4.7.2 log) · GitHub Actions: actions/checkout v7.0.1, actions/setup-python v7.1.0 · yamllint 1.38.0, check-jsonschema 0.39.0"
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
source_hash: a6b04d555721
---

## summary
A drone's configuration is code: whether it flies depends on it. So everything engineers have long done with code applies to it: a change history with explanations, review before applying, automated checks, releases and rollback. This module sets that up for a single vehicle or a fleet: Betaflight `diff all` and ArduPilot `.param` files in git with meaningful commits, a fleet manifest under a JSON Schema, an invariant-check script that knows about parameter renames between versions and about the firmware's "silent" fixes, GitHub Actions with action versions pinned to a commit SHA, a SITL failsafe autotest that loads the fleet's actual config, a pull request as the form of review, release tags and rollback. The lab runs locally with the same commands as CI, on real exports: a `diff all` from Betaflight 4.5.3 SITL and 1015 parameters from an ArduCopter 4.7.2 SITL log; CI must go red on a broken failsafe and green once it is fixed.

## theory
### What to store
```
fleet/                     # repository root: CI runs every path below from here
  fleet.yaml               # manifest: site, craft list, firmware versions, config paths
  schema/fleet.schema.json # JSON Schema for fleet.yaml
  viking2/
    README.md              # what the aircraft is, hardware, firmware version
    betaflight/diff-all.txt  # diff all after every change
  hex1/
    ardupilot/params.param   # full parameter list (Mission Planner / mavproxy param save)
    notes/CHANGELOG.md     # what changed and why, with dates
  tools/
    export_bf.py           # takes diff all over MSP/CLI
    check_configs.py       # invariant checks
    sitl_fs_test.py        # failsafe autotest in SITL
  .yamllint
  .github/workflows/config-ci.yml
```
Rules: one commit is one change with a reason ("D roll 38→42: bounce-back 18%→9%, log 2026-11-08-03"); no reason, no commit. Binary logs do not go into the repository (Git LFS or releases).

The `fleet.yaml` manifest is the only place that records which aircraft flies which firmware and which file is its config. The check script takes the firmware version and the site's obstacle height from there instead of guessing them; that is why the manifest is itself validated against a schema, and a typo in it breaks CI before the config checks even run.

### Exporting the config automatically
Betaflight: over USB in CLI mode (not MSP: you enter the CLI with the `#` character), `diff all` from Python (`pyserial`: `#` → wait for `# ` → `diff all` → read until the `\r\n# ` prompt plus 0.3 s of silence after it), or the export from `betaflight-configurator`. The board is identified by `MSP_NAME`, and the end of the output is detected by the prompt and the pause; the details and the pitfalls are in the CLI automation module. ArduPilot: in MAVProxy, `param fetch`, wait for the download to finish (the command is asynchronous: the received-parameter counter in the console has to reach the total), then `param save params.param`; or pymavlink `param_fetch_all`, checking that exactly `param_count` parameters arrived, → a sorted text file. A `param save` right after `param fetch` can write an incomplete list: that is exactly the "200 lines" case below. Sort and normalize (strip the `#` comments with the date), otherwise the diff is noisy.

{{lesson:bf-cli-automation|How to take a diff all reliably from a script without losing the end of the output or rebooting the board needlessly: covered there.}}

What counts as a complete export. In the lab, the ArduCopter parameters were taken from the `PARM` messages of a SITL 4.7.2 log: 1370 lines, and 1015 remained after removing 355 `SIM_*` simulator parameters. If the file suddenly has 200 lines, that is not "the config got simpler" but a truncated export, and the check script must catch it (the rule "at least 300 parameters" is a course guideline for Copter). For Betaflight, the sign of a complete file is the final `save` line of the `diff all`.

### Invariants: checking configs
A script that reads a config and fails on any violation of the rules known from the course:
- Betaflight: `failsafe_procedure` is set, `failsafe_delay` is within reasonable limits, `motor_poles` = 14 for a 2207, `dshot_bidir = ON` with the RPM filter, `vbat_min_cell_voltage` ≥ 330, no `set debug_mode` in the flight profile.
- ArduPilot: `FS_THR_ENABLE ≠ 0`, `BATT_FS_LOW_ACT ≠ 0`, `FENCE_ENABLE = 1` for flights under the rules, `RTL_ALT_M` (meters; before 4.7, `RTL_ALT` in centimeters) ≥ the site's obstacle height (in the README), `ARMING_SKIPCHK = 0` (before 4.7, `ARMING_CHECK = 1`), `INS_HNTCH_ENABLE = 1` if a notch is needed, `BRD_SAFETY_DEFLT` per your policy.
Implementation: JSON Schema or plain Python with a rules table; the output is a list of violations, each with a reference to a course module.

A rule is only worth something if it knows the firmware version. Both renames above were checked in the ArduCopter 4.7.2 source (unchanged in 4.7.3): `RTL_ALT_M` is declared in `ArduCopter/mode_rtl.cpp` with the conversion table entry "RTL_ALT moved to RTL_ALT_M" (default 15 m, `config.h`), and `ARMING_SKIPCHK` in `libraries/AP_Arming/AP_Arming.cpp` (default 0, "no checks skipped"). The script keeps both names: if the file has `RTL_ALT_M`, it takes that in meters, otherwise it divides `RTL_ALT` by 100. For Betaflight the same thing happens at a different level: the version string at the top of the `diff all` (`# Betaflight / <board> (<id>) 4.5.3 …`) is compared with the version in `fleet.yaml`, and if they differ the check fails immediately: applying 4.5 rules to a 2025.12 file makes no sense. For 2025.12 a separate rule catches `d_min_<axis>`, which no longer exists (it is now `d_max_<axis>`, with the opposite meaning).

The second class of rules predicts the firmware's "silent" fixes. On save, Betaflight changes incompatible combinations by itself (`validateAndFixConfig()` in `config/config.c`): `failsafe_procedure = GPS-RESCUE` with `feature -GPS` on a flight board with a GPS build becomes `DROP` (`config.c:370` in 4.5.3, `:357` in 2025.12.5; read from the code), and in 2025.12 a `d_max` lower than `d_` is reset to zero. Such a file "goes in" without a single error when pasted, but the aircraft will fly with something other than what is recorded in git. The CI rule must say so before flashing: "firmware resets it to DROP on save". In the lab it fired on a real 4.5.3 `diff all`.

The thresholds in the rules come in two kinds, and the output has to tell them apart. Hard ones come from the documentation and the code: `FS_THR_ENABLE = 0` disables the reaction to RC loss, and that is not up for debate. Course guidelines: `failsafe_delay` ≤ 20 (2.0 s; the unit is 0.1 s, default 15, `flight/failsafe.c`), "at least 300 parameters", RTL no lower than the site obstacles from the manifest. A guideline goes into the rule with a comment saying where it came from, and it is changed deliberately, in a separate commit.

### Schemas and linters
A JSON Schema (draft 2020-12) describes what the manifest must look like: the required fields, `stack` only `betaflight` or `ardupilot`, the version in the form `X.Y.Z`, the name up to 16 characters of `[a-z0-9_-]` (like `craft_name`). It is checked with `check-jsonschema` 0.39.0: `check-jsonschema --schemafile schema/fleet.schema.json fleet.yaml`. The same tool has built-in schemas for popular formats, one of which is the GitHub Actions workflow schema: `check-jsonschema --builtin-schema vendor.github-workflows .github/workflows/*.yml` catches a typo in the `runs-on` or `steps` key locally, before you push.

`yamllint` 1.38.0 checks YAML style (indentation, line length, duplicate keys). Its `truthy` rule complains by default about the `on:` key in every workflow: in YAML 1.1, which PyYAML reads, `on` is the boolean `true`, and `yaml.safe_load` really does return the key `True` instead of `"on"` (checked: `['name', True, 'permissions', 'jobs']`). GitHub reads this key correctly, so `.yamllint` sets `truthy: {check-keys: false}`, and in your own YAML files you write the values only as `true`/`false`. With the default settings the same workflow got 5 findings (no `---`, `on` as truthy, three lines longer than 80): you fix those once in the linter config instead of silencing them line by line.

Python: `ruff` (0.17.6 as of November 2026) instead of the `flake8` + `black` pair; Lua (ArduPilot): `luacheck` with the ArduPilot config (`Tools/scripts/run_luacheck.sh` in the ArduPilot repository takes the same approach). All of it runs in CI on every PR.

### GitHub Actions: pin the versions
A workflow is code too, and it runs with permissions on your repository, so its versions are pinned as strictly as the firmware. A tag like `@v7` is a movable reference: the action's owner can move it to another commit (that is how "floating" major tags work). Only a reference to a full commit SHA is immutable, with the human-readable version next to it in a comment. Versions checked with `git ls-remote` against the action repositories on November 25, 2026: `actions/checkout` v7.0.1 = `3d3c42e5aac5ba805825da76410c181273ba90b1` (a commit from July 17, 2026; the `v7` tag points to the same place), `actions/setup-python` v7.1.0 = `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0` (October 21, 2026); both declare `using: node24` in `action.yml`. Everything else is pinned the same way: the `ubuntu-24.04` runner image instead of `ubuntu-latest`, package versions in `pip install` with `==`, `permissions: contents: read` (the job only reads), and `timeout-minutes`, so that a hung SITL does not eat your minutes.

| What | Version / value | How it was checked | Why pin it |
|---|---|---|---|
| `actions/checkout` | v7.0.1, SHA `3d3c42e5…3ba90b1` | `git ls-remote`, `action.yml`: node24 | a tag can be moved, a SHA cannot |
| `actions/setup-python` | v7.1.0, SHA `6d4fd22b…c9ca0e0` | `git ls-remote`, `action.yml`: node24 | the same |
| `runs-on` | `ubuntu-24.04` | GitHub image label | `ubuntu-latest` will one day change Python and the packages |
| `yamllint` | 1.38.0 | `pip index versions`, local run | style rules change between versions |
| `check-jsonschema` | 0.39.0 (on `jsonschema` 4.26.0) | `pip index versions`, local run | the built-in schemas are updated along with it |
| PyYAML | 6.0.4 | a yamllint dependency; `yaml.safe_load` in the script | YAML 1.1: `on` → `True` |
| `ArduCopter` SITL | 4.7.2, `--defaults copter.parm,<aircraft>.param`, `-w` | the autotest run below | without `-w`, old values stay in EEPROM |
| `RTL_ALT_M` / `RTL_ALT` | 4.7 / before 4.7 (cm) | `mode_rtl.cpp` | the rule must know both names |
| `ARMING_SKIPCHK` / `ARMING_CHECK` | 4.7 / before 4.7 | `AP_Arming.cpp` | the same |

{{diagram:ci-config-check-chain|The config-ci job: four checks chained with &&: the schema catches a typo in the manifest, the invariant script catches a broken failsafe and a diff from the wrong version; any red check blocks the merge.}}

### SITL autotest
ArduPilot in CI (an Ubuntu runner): build SITL (`./waf configure --board sitl && ./waf copter`) or use a prebuilt image; start `sim_vehicle.py` without a GUI with `--add-param-file params.param`; a pymavlink script: arm in Guided, take off to 10 m, `SIM_RC_FAIL = 1` → expect RTL/LAND mode within 5 s → `assert`; then in a separate run (with `SIM_RC_FAIL = 0`), a 4-waypoint mission → `assert` that it was completed. Time: 2–4 minutes (a course guideline; one run of `sitl_fs_test.py` in the lab takes about a minute). ArduPilot's own `Tools/autotest` is an example of how the developers do it (`autotest.py test.Copter.ThrottleFailsafe`).

The main pitfall of an autotest is that it may not be testing your config. A test that sets `FS_THR_ENABLE = 1` itself before checking (that is how the teaching example `examples/sitl-pymavlink/test_failsafe.py` in the course repository is written, to document the expectation) passes with any `.param` in the repository. A fleet test must only load the aircraft's config and fix nothing in it: `arducopter -w --defaults copter.parm,hex1/ardupilot/params.param` (the `-w` flag wipes the emulated EEPROM, and the values come from the defaults files; without it, SITL keeps the parameters from the previous run). The check that the test can fail is a mutation test: swap `FS_THR_ENABLE` to 0 and make sure the result is red. In the lab, both runs were done on ArduCopter 4.7.2 SITL: with the fixed config, `PASS: mode RTL 1.0 s after RC loss`; with the mutant, `FAIL: mode still GUIDED 5 s after RC loss`, about a minute per run.

{{diagram:ci-sitl-failsafe-seq|The SITL autotest step by step: after SIM_RC_FAIL = 1 the mode must change to RTL or LAND within 5 s, otherwise the assert fails and the PR is not merged.}}

Betaflight: a SITL build checks compilation and the CLI; for PID logic there are unit tests (`make test`). For configs, the invariant script. Building Betaflight SITL and running a `diff all` through it is covered in the CLI automation module: that way CI can check that the `diff all` pastes into the right version without `INVALID NAME` errors.

### Review
PR = change + reason + evidence (a log before/after, a spectrum, a number). A self-review checklist (the reviewer here is you): is the reason clear? the risk (failsafe, motors, limits)? tested in SITL/on the bench? rollback described? The order for one person: a PR with a description, green CI, merge the next day (a course guideline: "sleep on it"), and before merging, go through these four questions on your own PR.

### Releases and rollback
A tag `viking7-v12` on the commit you flew with; `CHANGELOG.md` by version; a GitHub release with the `diff all`/`.param` and the log of the check flight attached. Rollback is `git checkout viking7-v11 -- viking7/` plus loading the config. Firmware: its version and build key (Betaflight: `version` and the BUILD KEY from `status`; ArduPilot: the `AUTOPILOT_VERSION` message or `version` in MAVProxy) go into the release README.

{{diagram:config-ci|A config change as a code change: export, commit, check invariants and SITL, review, release with a way to roll back.}}

### Where it fits

- **Takes in:** the Betaflight `diff all` (`bf-cli-automation`) and the ArduPilot `.param`; the invariant rules from the failsafe modules (`bf-failsafe`, `ap-safety-fs`); the rename tables between versions (`bf-intro`); SITL for the autotest (`ap-sitl`); the log analysis functions for check flights (`data-python`).
- **Hands off:** the config tag you flew with, to the test log and the documentation package (`eng-systems`); a change history with reasons and logs; a tested rollback; a red CI before a broken config reaches the aircraft.
- **If you get this wrong:** a config flashed after a firmware update without the invariant check → a parameter was renamed and the failsafe silently does not work; it comes to light on an RC loss in the field (`ap-safety-fs`). The autotest set `FS_THR_ENABLE` itself → green CI with a broken config. A commit without a reason and a log → a month later nobody knows why D was changed, and the tuning starts from scratch (`bf-pid`).

## practice
The main path is a local run of the same commands as in the workflow, on real files: `viking2/betaflight/diff-all.txt` is a `diff all` from Betaflight 4.5.3 SITL (the lab of the CLI automation module: `failsafe_delay = 10`, `failsafe_procedure = GPS-RESCUE`, `d_roll = 30`, `d_min_roll = 20`, `feature -GPS`); `hex1/ardupilot/params.param` is 1015 ArduCopter 4.7.2 parameters from a SITL log (the lab of the "Python for flight data analysis" module, where `FS_THR_ENABLE = 0` for the sake of RC override). Environment: Python 3.13, `pip install yamllint==1.38.0 check-jsonschema==0.39.0` (PyYAML 6.0.4 comes in as a dependency).

### Step 1. Repository
The structure above; the first commit is the current configs with a README (hardware, versions). `.gitattributes` for LFS on `.bin/.BFL`. The manifest, the schema and the linter settings:

```text
# --- fleet.yaml ---
# Fleet manifest: one entry per aircraft; CI validates it against schema/fleet.schema.json
site:
  name: field-north
  obstacle_m: 25            # tallest obstacle around the field, m (RTL must clear it)
craft:
  - name: viking2
    stack: betaflight
    firmware: "4.5.3"
    config: viking2/betaflight/diff-all.txt
  - name: hex1
    stack: ardupilot
    firmware: "4.7.2"
    config: hex1/ardupilot/params.param

# --- schema/fleet.schema.json ---
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["site", "craft"],
  "additionalProperties": false,
  "properties": {
    "site": {
      "type": "object",
      "required": ["name", "obstacle_m"],
      "properties": {
        "name": {"type": "string"},
        "obstacle_m": {"type": "number", "minimum": 0, "maximum": 300}
      }
    },
    "craft": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["name", "stack", "firmware", "config"],
        "additionalProperties": false,
        "properties": {
          "name": {"type": "string", "pattern": "^[a-z0-9_-]{1,16}$"},
          "stack": {"enum": ["betaflight", "ardupilot"]},
          "firmware": {"type": "string", "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$"},
          "config": {"type": "string"}
        }
      }
    }
  }
}

# --- .yamllint ---
extends: default
rules:
  line-length: {max: 120}
  truthy: {allowed-values: ["true", "false"], check-keys: false}
  comments: {min-spaces-from-content: 1}
  document-start: disable
```

### Step 2. Export by script
`export_bf.py` or `param save` on command; commit "snapshot before tuning". For the lab the export is already done: the files above come from two SITL runs with no manual edits (only the `SIM_*` lines were removed from the `.param`).

### Step 3. Invariants + CI
`check_configs.py` with 5+ rules; `.github/workflows/config-ci.yml`: the same four checks you run locally. Break a rule on purpose → CI goes red → fix it.

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

Keep rules whose parameters were renamed between versions (`RTL_ALT` → `RTL_ALT_M` in 4.7) with both names, or check the firmware version from the aircraft's README. For Betaflight, the same approach on the `set name = value` lines of the `diff all`.

### Step 4. Run CI locally: five cases
The script below runs the chain of checks from the workflow (with `&&`, as in the job) five times: (A) the snapshot as exported; (B) the fix: RC and battery failsafe, geofence, RTL 30 m, notch, Betaflight failsafe `DROP`; (C) a mutation test: `FS_THR_ENABLE` back to 0; (D) in the manifest the viking2 firmware was bumped to 2025.12.5 while the `diff all` was left from 4.5.3; (E) a typo in the manifest. Run it as `bash run_ci_lab.sh <copy of fleet/>`: a copy, because the script edits files with `sed`.

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

What the output proves. In case A all six violations present in the files are caught: five for `hex1` and the silent failsafe fix for `viking2`; exit code 1, so a PR with this snapshot will not merge. B is green, and it is the only green one: so the rules are not "always red". C gives exactly one error for exactly one mutation. D: the version check fired before the rules: a 4.5.3 file for 2025.12.5 firmware gives both the version mismatch and the obsolete name `d_min_roll`. E: the schema stopped the job before the config checks, pointing to the path `$.craft[1].stack`.

### Step 5. A SITL failsafe test on the fleet config
`sitl_fs_test.py` is a test that does not touch `FS_THR_ENABLE` but loads the aircraft's `.param` through `--defaults`. Run it on the fixed config and on the mutant:

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

Compare it with the teaching example in the course repository: [examples/sitl-pymavlink](https://github.com/irreligious86/UAV-Education/tree/main/examples/sitl-pymavlink) (`test_failsafe.py` + `ci.yml`). The example sets `FS_THR_ENABLE = 1` itself and pins `actions/checkout@v4` by tag; for a fleet, take the approach from `sitl_fs_test.py` and the SHAs from the theory table. One PR with a parameter change, a description, CI and a merge.

### Moving to real hardware
CI checks files, not the aircraft, so the last step is to confirm that the aircraft has the same thing as git. Props off. Betaflight: after flashing the config, take a `diff all` with the same command as for the repository and compare it with the file from the tag by key (`parse_diff` from the CLI automation module); the difference must be empty, and if the firmware fixed something on `save`, the difference will show it. ArduPilot: `param fetch` + `param save` and a `diff` against the file from the tag; then in the field, a check of the failsafe per the "Safety and failsafe" module (switch the radio off while hovering at a safe height; the expected mode is RTL or LAND within `RC_FS_TIMEOUT`). Abort: any difference between the file on the aircraft and the tag means no flying until it is explained. Criteria on hardware: the "aircraft − tag" difference is empty for both stacks; the release tag points to a commit with green CI; the field failsafe test gives the mode that SITL checked.

Self-check: the lab is done when (locally) case A prints `1 ERROR(S)` for `viking2` and `5 ERROR(S)` for `hex1` with exit code 1; case B prints `OK` for both with exit code 0; C gives exactly one `FS_THR_ENABLE` error and exit code 1; D gives two errors for `viking2` (the version and `d_min_roll`); E gives two schema errors with the paths `$.craft[1].stack` and `$.craft[1].firmware`; (SITL) the fixed config gives `PASS: mode RTL`, and the mutant with `FS_THR_ENABLE = 0` gives `FAIL: mode still GUIDED`; the PR has a change, a reason and evidence, and before merging you went through the self-review checklist from the theory section on it yourself: each of the four questions (reason, risk, testing, rollback) has a written answer in the PR description.

**Reference answer for self-check.** A correct result is the step 4 output line for line (error counts and exit codes) and the PASS/FAIL pair of step 5; the time to RTL after RC loss is about 1 s. Typical wrong results: (1) the mutant also gives PASS: the test sets `FS_THR_ENABLE` itself, or SITL was started without `-w` and took the parameters from the EEPROM of the previous run; (2) in case A, `hex1` has no `RTL_ALT_M` error: the rule has a 15 m threshold instead of the 25 m obstacle height from the manifest, or the script looks for `RTL_ALT` and divides 15 by 100; (3) `yamllint` is red on the workflow with `truthy`: there is no `check-keys: false` in `.yamllint`; (4) case E passes the schema: the schema has no `additionalProperties: false` or no `enum` on `stack`.

## diagnostics
- **Symptom:** the diff all differs completely every time
  - Possible cause: ordering/comments/a date in the export.
  - What to do: normalize and sort before committing; compare by key, not by line.
- **Symptom:** SITL does not start in CI/times out
  - Possible cause: a long build, no `--no-mavproxy`/headless, ports.
  - What to do: a build cache or a prebuilt image, a headless start, waiting for the heartbeat with a timeout; `timeout-minutes` on the job.
- **Symptom:** the test passes even though the failsafe is broken
  - Possible cause: the assert checks the wrong thing (the mode is not read), the test does not wait, or the test sets the parameter under test itself.
  - What to do: check that the test fails with a broken config (a mutation test); the test only loads the `.param` (`--defaults … -w`).
- **Symptom:** I do not remember which config I flew with that time
  - Possible cause: no tags/releases.
  - What to do: a tag for every flight config, a log attached to the release.
- **Symptom:** CI "suddenly" went red with no changes in the repository
  - Possible cause: floating versions: `ubuntu-latest`, `@v7`, `pip install` without `==`.
  - What to do: pin the image, the actions by SHA, the packages by version; update them in a separate PR.
- **Symptom:** `yamllint` complains about `on:` in the workflow
  - Possible cause: the `truthy` rule checks keys; in YAML 1.1 `on` is a boolean.
  - What to do: `truthy: {check-keys: false}` in `.yamllint`.
- **Symptom:** the RTL rule passes on an old config with RTL at 15 m
  - Possible cause: a config from before 4.7 has the `RTL_ALT` parameter in centimeters, and the rule reads only `RTL_ALT_M`.
  - What to do: a rule with both names and the unit conversion; the firmware version comes from the manifest.

## references
- GitHub Docs — GitHub Actions workflows | https://docs.github.com/en/actions/writing-workflows | primary | A
- actions/checkout (tags, action.yml) | https://github.com/actions/checkout | primary | A
- actions/setup-python (tags, action.yml) | https://github.com/actions/setup-python | primary | A
- check-jsonschema — documentation | https://check-jsonschema.readthedocs.io/ | primary | A
- yamllint — documentation (rules: truthy) | https://yamllint.readthedocs.io/ | primary | A
- ArduPilot — Autotest framework (Tools/autotest) | https://ardupilot.org/dev/docs/the-ardupilot-autotest-framework.html | primary | A
- ArduPilot — source code Copter-4.7.3 (ArduCopter/mode_rtl.cpp, libraries/AP_Arming/AP_Arming.cpp; the lab ran on 4.7.2) | https://github.com/ArduPilot/ardupilot/tree/Copter-4.7.3 | primary | A
- Betaflight — Command Line Interface (CLI) | https://betaflight.com/docs/wiki/guides/current/Cli | primary | A

## checklist
- Configs in git with "what and why" commits, a fleet manifest under a schema
- Configs exported by script, normalized, checked for completeness
- Invariants are checked in CI and know the renames between versions
- Actions pinned by SHA, the image and packages by version
- The SITL failsafe test loads the fleet config and fails with a broken config
- Releases as tags, rollback rehearsed
