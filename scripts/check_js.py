#!/usr/bin/env python3
"""Syntax-check every site script with `node --check` (skipped with a note if node is absent)."""
import shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
files = sorted((ROOT / "assets").glob("*.js")) + sorted((ROOT / "assets" / "widgets").glob("*.js"))
if not shutil.which("node"):
    print("check_js: node not found, skipped")
    sys.exit(0)
bad = 0
for f in files:
    r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
    if r.returncode:
        bad += 1
        print(f"::error::{f.relative_to(ROOT)}: {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else 'syntax error'}")
print(f"check_js: {len(files)} files, {bad} errors")
sys.exit(1 if bad else 0)
