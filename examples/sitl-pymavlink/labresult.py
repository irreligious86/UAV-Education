"""Lab result file shared by the course graders (schema uav-lab-result/1, see docs/LAB-RESULTS.md).

Identical copies live next to each grader so every example stays standalone; a test checks they match.
The progress page imports the file and ticks the lab criteria listed in "marks" — only criteria the grader
actually measured, and only when its checks passed. Self-study honesty: the file can be edited by hand;
it shows the grader was run, not that anyone supervised it.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os

SCHEMA = "uav-lab-result/1"


def file_digest(path: str) -> dict:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return {"name": os.path.basename(path), "bytes": os.path.getsize(path), "sha256": h.hexdigest()}


def build(grader: str, version: int, input_path: str, labs: dict[str, list[dict]], marks_for: dict[str, list[str]],
          extra_marks: list[str] | None = None, info: dict | None = None) -> dict:
    """labs: lab name -> checks [{check, pass, value?}]; marks_for: lab name -> criteria ids proven by a pass."""
    marks = []
    for lab, checks in labs.items():
        if checks and all(c["pass"] for c in checks):
            marks += marks_for.get(lab, [])
    marks += extra_marks or []
    return {
        "schema": SCHEMA, "grader": grader, "grader_version": version,
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "input": file_digest(input_path),
        "labs": [{"lab": lab, "pass": bool(checks) and all(c["pass"] for c in checks), "checks": checks} for lab, checks in labs.items()],
        "pass": all(c["pass"] for checks in labs.values() for c in checks),
        "marks": sorted(set(marks)),
        **({"info": info} if info else {}),
    }


def write(path: str, result: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
