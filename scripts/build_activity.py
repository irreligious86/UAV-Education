#!/usr/bin/env python3
"""Build docs/activity/activity.json: how the course grows, commit by commit and day by day.

Read from git history only (no network). Grafana reads the file with the Infinity data source
(see docs/activity/README.md). Run from the repo root:

  python3 scripts/build_activity.py

The file describes history up to the commit that is checked out, so it always lags one commit
behind the commit that adds it. That is expected.
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "activity" / "activity.json"
WORD_RE = re.compile(r"\w+", re.UNICODE)
FC_RE = {
    "errors": re.compile(r"(\d+)\s+errors?\b"),
    "imprecise": re.compile(r"(\d+)\s+imprecis\w*"),
    "nits": re.compile(r"(\d+)\s+nits?\b"),
}
SKIP_MD = {"README.md", "article-template.md"}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def is_module(path: str) -> bool:
    p = Path(path)
    return (len(p.parts) == 3 and p.parts[0] == "content" and p.suffix == ".md"
            and p.parts[1] not in ("tasks", "quiz") and p.name not in SKIP_MD)


def kind_of(rec: dict) -> str:
    """Classify a commit by what it changed; the subject only breaks ties."""
    s = rec["subject"].lower()
    if rec["modules_added"]:
        return "new"
    if s.startswith("i18n") or s.startswith("ru-odessa") or (rec["i18n_files"] and not rec["modules_touched"]):
        return "i18n"
    if "visual pass" in s or (rec["diagram_scripts"] and not rec["content_lines_added"]):
        return "visual"
    if any(w in s for w in ("fix", "fact-check", "correct", "audit")) and rec["content_lines_added"] < 300:
        return "fix"
    if rec["modules_touched"] and rec["content_lines_added"] >= 40:
        return "deepen"
    if rec["modules_touched"]:
        return "fix"
    return "infra"


def commits() -> list[dict]:
    """One record per commit on the first-parent history, oldest first."""
    meta = git("log", "--first-parent", "--reverse", "--format=%x1e%H%x1f%aI%x1f%s%x1f%b")
    stats_log = git("log", "--first-parent", "--reverse", "--format=%x1e%H", "--numstat", "-M")
    stats_by_sha = {}
    for chunk in stats_log.split("\x1e")[1:]:
        sha, _, rest = chunk.partition("\n")
        stats_by_sha[sha.strip()] = rest
    out = []
    for chunk in meta.split("\x1e")[1:]:
        sha, date, subject, body = (chunk.split("\x1f") + ["", "", "", ""])[:4]
        sha = sha.strip()
        stats = stats_by_sha.get(sha, "")
        rec = {"sha": sha[:8], "date": date, "day": date[:10], "subject": subject.strip(),
               "modules_touched": 0, "content_lines_added": 0, "content_lines_removed": 0,
               "i18n_files": 0, "diagram_scripts": 0, "task_banks": 0, "quiz_banks": 0}
        touched = set()
        for line in (stats or "").splitlines():
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            a, d, path = parts
            path = path.split(" => ")[-1].replace("}", "").replace("{", "")
            if is_module(path):
                touched.add(Path(path).stem)
                if a.isdigit():
                    rec["content_lines_added"] += int(a)
                    rec["content_lines_removed"] += int(d)
            elif path.startswith("i18n/"):
                rec["i18n_files"] += 1
            elif path.startswith("scripts/diagrams/"):
                rec["diagram_scripts"] += 1
            elif path.startswith("content/tasks/"):
                rec["task_banks"] += 1
            elif path.startswith("content/quiz/"):
                rec["quiz_banks"] += 1
        rec["modules_touched"] = len(touched)
        rec["modules"] = sorted(touched)
        text = subject + "\n" + body
        for key, rx in FC_RE.items():
            m = rx.search(text)
            rec[f"fc_{key}"] = int(m.group(1)) if m else 0
        out.append(rec)
    # modules added: first commit where a module file appears
    added = git("log", "--first-parent", "--reverse", "--diff-filter=A", "--name-only", "--format=%x1e%H")
    first = {}
    for chunk in added.split("\x1e")[1:]:
        lines = chunk.strip().splitlines()
        if not lines:
            continue
        sha = lines[0][:8]
        first[sha] = sorted(Path(p).stem for p in lines[1:] if is_module(p))
    for rec in out:
        rec["modules_added"] = len(first.get(rec["sha"], []))
        rec["modules_added_ids"] = first.get(rec["sha"], [])
        rec["kind"] = kind_of(rec)
    return out


def snapshot(sha: str) -> dict:
    """Module count and word count of the Russian sources at one commit."""
    files = [p for p in git("ls-tree", "-r", "--name-only", sha, "content").splitlines() if is_module(p)]
    words = 0
    if files:
        batch = "\n".join(f"{sha}:{p}" for p in files) + "\n"
        raw = subprocess.run(["git", "cat-file", "--batch"], cwd=ROOT, input=batch.encode(), capture_output=True, check=True).stdout
        i = 0
        while i < len(raw):
            nl = raw.index(b"\n", i)
            size = int(raw[i:nl].split()[2])
            body = raw[nl + 1: nl + 1 + size].decode("utf-8", "replace")
            words += len(WORD_RE.findall(body))
            i = nl + 1 + size + 1
    diagrams = sum(1 for p in git("ls-tree", "--name-only", f"{sha}:assets/diagrams").splitlines() if p.endswith(".svg")) \
        if "assets/diagrams" in git("ls-tree", "-d", "-r", "--name-only", sha, "assets") else 0
    return {"modules_total": len(files), "words_total": words, "diagrams_total": diagrams}


def main() -> None:
    recs = commits()
    by_day = defaultdict(list)
    for r in recs:
        by_day[r["day"]].append(r)
    daily = []
    for day in sorted(by_day):
        rs = by_day[day]
        snap = snapshot(rs[-1]["sha"])
        daily.append({
            "day": day, "date": f"{day}T23:59:59Z", "commits": len(rs),
            "modules_added": sum(r["modules_added"] for r in rs),
            "modules_touched": len({m for r in rs for m in r["modules"]}),
            "content_lines_added": sum(r["content_lines_added"] for r in rs),
            "content_lines_removed": sum(r["content_lines_removed"] for r in rs),
            "fc_errors": sum(r["fc_errors"] for r in rs),
            "fc_imprecise": sum(r["fc_imprecise"] for r in rs),
            "fc_nits": sum(r["fc_nits"] for r in rs),
            **snap,
        })
    head = recs[-1]["sha"] if recs else ""
    data = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "head": head,
        "totals": {**(daily[-1] if daily else {}), "commits_total": len(recs),
                   "fc_errors_total": sum(r["fc_errors"] for r in recs),
                   "fc_imprecise_total": sum(r["fc_imprecise"] for r in recs),
                   "fc_nits_total": sum(r["fc_nits"] for r in recs)},
        "daily": daily,
        "commits": recs,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    with (OUT.parent / "daily.csv").open("w", newline="", encoding="utf-8") as f:
        cols = ["day", "commits", "modules_total", "words_total", "diagrams_total", "modules_added", "modules_touched",
                "content_lines_added", "content_lines_removed", "fc_errors", "fc_imprecise", "fc_nits"]
        w = csv.writer(f)
        w.writerow(cols)
        for r in daily:
            w.writerow([r[c] for c in cols])
    with (OUT.parent / "commits.csv").open("w", newline="", encoding="utf-8") as f:
        cols = ["date", "sha", "kind", "subject", "modules_touched", "modules_added", "content_lines_added",
                "content_lines_removed", "fc_errors", "fc_imprecise", "fc_nits", "modules"]
        w = csv.writer(f)
        w.writerow(cols)
        for r in reversed(recs):
            w.writerow([" ".join(r[c]) if c == "modules" else r[c] for c in cols])
    print(f"activity: {len(recs)} commits, {len(daily)} days, {data['totals'].get('modules_total', 0)} modules -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
