# Lab result files (`uav-lab-result/1`)

Graders write a JSON file that the progress page imports ("Мой прогресс → Импорт результата
грейдера"). Lab criteria the grader actually measured are ticked automatically and marked "⚙" in
the transcript; everything else in a lab stays a manual tick.

```bash
python examples/sitl-pymavlink/check_lab_log.py flight.bin --lab motorfail --json result.json
python examples/blackbox-grader/check_bf_log.py LOG.01.csv --lab all --motor-range 48,2047 --json result.json
```

## Format

```json
{
  "schema": "uav-lab-result/1",
  "grader": "check_bf_log", "grader_version": 1,
  "generated": "2026-11-08T12:00:00+00:00",
  "input": {"name": "LOG.01.csv", "bytes": 1234567, "sha256": "<64 hex>"},
  "labs": [{"lab": "filters", "pass": true, "checks": [{"check": "...", "pass": true, "value": "...", "limit": "..."}]}],
  "pass": true,
  "marks": ["bf-filters:lab:0", "bf-filters:lab:1"],
  "info": {"sample_rate_hz": 2000.0}
}
```

`marks` are check ids `<module>:lab:<index>` from `data/curriculum.json`. A grader adds a mark only
when every check of the lab that proves it passed. The page ignores marks for unknown modules or
indices out of range, and refuses files without `schema` or `input.sha256`. Importing the same
result twice is a no-op.

## Which grader proves what

| Grader `--lab` | Marks |
|---|---|
| `check_lab_log` failsafe | `ap-safety-fs:lab:3` |
| `check_lab_log` mission | `ap-missions:lab:3` |
| `check_lab_log` hover | `ap-tuning:lab:2` |
| `check_lab_log` motorfail | `ap-heavy:lab:0`, `el-redundancy:lab:2` |
| `check_bf_log` filters | `bf-filters:lab:0`, `bf-filters:lab:1` |
| `check_bf_log` tracking | `bf-pid:lab:4` |
| `check_bf_log` motors | `bf-pid:lab:5` |
| `check_bf_log` rpm | `bf-rpm-filter:lab:4` |
| `check_bf_log` any lab, log ≥ 1 kHz | `bf-blackbox:lab:0` |

The tables live in each grader (`MARKS`). Changing a module's lab criteria order means updating them;
append new criteria at the end so existing progress keeps its meaning.

## Honest limit

This is self-study. The file can be edited by hand; it shows that the grader was run on a log with
that checksum, not that a mentor accepted the work. A mentor who wants more asks for the log itself
and runs the grader again — the checksum tells them it is the same file.
