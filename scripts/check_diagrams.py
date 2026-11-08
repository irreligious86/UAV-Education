#!/usr/bin/env python3
"""Check assets/diagrams/*.svg: well-formed XML, has <title>, no external references, size limit.

Also verifies that every diagram referenced from content/ exists, and that each generated diagram is
referenced at least once (an unused diagram is a sign of a typo in a {{diagram:...}} tag).
"""
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "assets" / "diagrams"
MAX_BYTES = 60_000
TAG = re.compile(r"\{\{diagram:([a-z0-9-]+)\|")


def main() -> int:
    errs: list[str] = []
    files = sorted(DIR.glob("*.svg"))
    if not files:
        errs.append("no diagrams found")
    for f in files:
        raw = f.read_bytes()
        if len(raw) > MAX_BYTES:
            errs.append(f"{f.name}: {len(raw)} bytes > {MAX_BYTES}")
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as e:
            errs.append(f"{f.name}: XML error {e}")
            continue
        ns = "{http://www.w3.org/2000/svg}"
        if root.tag not in (ns + "svg", "svg"):
            errs.append(f"{f.name}: root is {root.tag}, not <svg>")
        if root.find(ns + "title") is None and root.find("title") is None:
            errs.append(f"{f.name}: missing <title>")
        if "viewBox" not in root.attrib:
            errs.append(f"{f.name}: missing viewBox")
        txt = raw.decode("utf-8", "replace")
        if re.search(r"(href|src)\s*=\s*[\"']https?://", txt) or "<script" in txt or "<image" in txt:
            errs.append(f"{f.name}: external reference / script / raster image is not allowed")
    used: dict[str, list[str]] = {}
    for md in (ROOT / "content").rglob("*.md"):
        for m in TAG.finditer(md.read_text(encoding="utf-8")):
            used.setdefault(m.group(1), []).append(str(md.relative_to(ROOT)))
    proj = ROOT / "data" / "projects.json"
    if proj.is_file():
        import json
        for pr in json.loads(proj.read_text(encoding="utf-8")).get("projects", []):
            if pr.get("diagram"):
                used.setdefault(pr["diagram"], []).append("data/projects.json")
    names = {f.stem for f in files}
    for n, where in sorted(used.items()):
        if n not in names:
            errs.append(f"diagram '{n}' referenced in {where[0]} but assets/diagrams/{n}.svg does not exist")
    unused = sorted(names - set(used))
    for n in unused:
        print(f"warning: diagram '{n}' is not referenced from any module")
    for e in errs:
        print("ERROR:", e)
    print(f"diagrams: {len(files)} files, {sum(len(v) for v in used.values())} references, {len(errs)} errors")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
