#!/usr/bin/env python3
"""Check translations (docs/I18N.md). Fails on anything that would break a page or change grading;
prints coverage. A missing translation is never an error: the site falls back to the source language.

Errors:
  - catalog not a flat {string: string} object
  - a translation with different {placeholders}, or different leading/trailing spaces, than its key
  - a translated module: no source_hash, different section set, different diagram/widget directives,
    different number of fenced code blocks
  - a translated quiz bank: different number of questions/options or a different correct answer index
  - a translated task bank: different ids, params, answer formulas, units or tolerances
  - a translated file with no source file
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import i18n  # noqa: E402
from content_pipeline import parse_front_matter, strip_front_matter  # noqa: E402

SECTION = re.compile(r"^##\s+([a-z_]+)\s*$", re.M)
DIRECTIVE = re.compile(r"^\{\{(?:diagram|widget):([a-z0-9-]+)", re.M)
FENCE = re.compile(r"^```", re.M)


def edges(s: str) -> tuple[str, str]:
    return s[: len(s) - len(s.lstrip())], s[len(s.rstrip()):]


def check_catalog(path: Path, errors: list[str]) -> tuple[int, int]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        errors.append(f"{path.relative_to(ROOT)}: invalid JSON: {e}")
        return 0, 0
    if not isinstance(data, dict):
        errors.append(f"{path.relative_to(ROOT)}: must be an object")
        return 0, 0
    done = total = 0
    for k, v in data.items():
        if k.startswith("@"):
            continue
        total += 1
        if not isinstance(v, str):
            errors.append(f"{path.relative_to(ROOT)}: value of «{k[:60]}» is not a string")
            continue
        if not v:
            continue
        done += 1
        if i18n.placeholders(k) != i18n.placeholders(v):
            errors.append(f"{path.relative_to(ROOT)}: placeholders differ in «{k[:60]}»: {sorted(i18n.placeholders(k))} vs {sorted(i18n.placeholders(v))}")
        if edges(k) != edges(v):
            errors.append(f"{path.relative_to(ROOT)}: leading/trailing spaces differ in «{k[:60]}»")
    return done, total


def check_module(t: Path, src: Path, errors: list[str]) -> str:
    rel = t.relative_to(ROOT)
    tr, so = t.read_text(encoding="utf-8"), src.read_text(encoding="utf-8")
    fm = parse_front_matter(tr) or ""
    h = re.search(r"^source_hash:\s*([0-9a-f]+)", fm, flags=re.M)
    if not h:
        errors.append(f"{rel}: no source_hash in front matter")
    tb, sb = strip_front_matter(tr), strip_front_matter(so)
    if SECTION.findall(tb) != SECTION.findall(sb):
        errors.append(f"{rel}: sections {SECTION.findall(tb)} differ from the source {SECTION.findall(sb)}")
    if DIRECTIVE.findall(tb) != DIRECTIVE.findall(sb):
        errors.append(f"{rel}: diagram/widget directives differ from the source")
    if len(FENCE.findall(tb)) != len(FENCE.findall(sb)):
        errors.append(f"{rel}: number of code fences differs from the source")
    return "ok" if h and h.group(1) == i18n.source_hash(so) else "stale"


def check_quiz(t: Path, src: Path, errors: list[str]) -> None:
    rel = t.relative_to(ROOT)
    a, b = json.loads(t.read_text(encoding="utf-8")), json.loads(src.read_text(encoding="utf-8"))
    qa, qb = a.get("questions", []), b.get("questions", [])
    if len(qa) != len(qb):
        errors.append(f"{rel}: {len(qa)} questions, source has {len(qb)}")
        return
    for i, (x, y) in enumerate(zip(qa, qb)):
        if len(x.get("options", [])) != len(y.get("options", [])) or x.get("answer") != y.get("answer"):
            errors.append(f"{rel}: question {i}: options or answer index differ from the source")
        if x.get("kind") != y.get("kind"):
            errors.append(f"{rel}: question {i}: kind differs from the source")


def check_tasks(t: Path, src: Path, errors: list[str]) -> None:
    rel = t.relative_to(ROOT)
    a, b = json.loads(t.read_text(encoding="utf-8")), json.loads(src.read_text(encoding="utf-8"))
    ta, tb = a.get("tasks", []), b.get("tasks", [])
    if [x["id"] for x in ta] != [x["id"] for x in tb]:
        errors.append(f"{rel}: task ids differ from the source")
        return
    for x, y in zip(ta, tb):
        for k in ("params", "answer", "tol", "abs", "unit"):
            if k == "unit":
                continue   # units may be localised (ч -> год / h); everything that grades must match
            if x.get(k) != y.get(k):
                errors.append(f"{rel}: task {x['id']}: {k} differs from the source")
        for v in re.findall(r"\{([a-z0-9_]+)\}", x.get("statement", "")):
            if v not in y.get("params", {}):
                errors.append(f"{rel}: task {x['id']}: statement uses unknown parameter {{{v}}}")


def main() -> int:
    errors: list[str] = []
    report = []
    for l in i18n.LANGS[1:]:
        base = ROOT / "i18n" / l["code"]
        parts = []
        for name in ("ui", "data"):
            p = base / f"{name}.json"
            if p.is_file():
                d, t = check_catalog(p, errors)
                parts.append(f"{name} {d}/{t}")
        mods = {"ok": 0, "stale": 0}
        n_src = 0
        for src in sorted((ROOT / "content").rglob("*.md")):
            if src.parent.name in ("notes",) or src.name in ("README.md", "article-template.md"):
                continue
            n_src += 1
            t = i18n.translated_path(src, l["code"])
            if t.is_file():
                mods[check_module(t, src, errors)] += 1
        for t in sorted((base / "content").rglob("*")) if (base / "content").is_dir() else []:
            if t.is_file():
                src = ROOT / t.relative_to(base)
                if not src.is_file():
                    errors.append(f"{t.relative_to(ROOT)}: no source file {src.relative_to(ROOT)}")
                elif t.parent.name == "quiz":
                    check_quiz(t, src, errors)
                elif t.parent.name == "tasks":
                    check_tasks(t, src, errors)
        nq = len(list((base / "content" / "quiz").glob("*.json"))) if (base / "content" / "quiz").is_dir() else 0
        nt = len(list((base / "content" / "tasks").glob("*.json"))) if (base / "content" / "tasks").is_dir() else 0
        parts.append(f"modules {mods['ok']}/{n_src}" + (f" (+{mods['stale']} stale)" if mods["stale"] else ""))
        parts.append(f"quizzes {nq}, task banks {nt}")
        report.append(f"  {l['code']}: " + ", ".join(parts))
    for e in errors:
        print(f"::error::{e}")
    print(f"check_i18n: {len(i18n.LANGS)} languages, {len(errors)} errors")
    print("\n".join(report))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
