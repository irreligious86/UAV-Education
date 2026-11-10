#!/usr/bin/env python3
"""Collect every interface string of the site into the translation catalogs (docs/I18N.md).

Sources of keys:
  - strings the build looked up through _() / tr_html()   (i18n/.build-keys.json, written by build_site.py)
  - T("...") literals in assets/*.js and assets/widgets/*.js
  - text of the diagram generators                           (i18n/.diagram-keys.json, written by build_diagrams.py)

For every non-source language, i18n/<lang>/ui.json is rewritten sorted: existing translations are kept,
new keys are added with an empty value (empty = untranslated, the site shows the source), keys that no
longer exist anywhere are dropped and listed.

  python scripts/i18n_extract.py            update the catalogs
  python scripts/i18n_extract.py --todo     also write i18n/<lang>/todo-ui.json with only the untranslated keys
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import i18n  # noqa: E402

JS_T = re.compile(r"""\bT\(\s*("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')""")


def js_keys() -> set[str]:
    keys: set[str] = set()
    for f in sorted((ROOT / "assets").glob("*.js")) + sorted((ROOT / "assets" / "widgets").glob("*.js")):
        for lit in JS_T.findall(f.read_text(encoding="utf-8")):
            keys.add(ast.literal_eval(lit))   # our JS string escapes (\" \' \n \u....) read the same in Python
    return keys


DATA_FILES = ("data/curriculum.json", "data/content-manifest.json", "data/projects.json", "data/formulas.json", "data/glossary.json")


def data_keys() -> set[str]:
    """Text values of the data files, walked the same way i18n.tr_data translates them."""
    keys: set[str] = set()
    def walk(v, key=None):
        if isinstance(v, str):
            if key not in i18n.NON_TEXT_KEYS and re.search(r"[А-Яа-яЁё]", v):
                keys.add(v)
        elif isinstance(v, list):
            for x in v:
                walk(x, key)
        elif isinstance(v, dict):
            for k, x in v.items():
                walk(x, k)
    for f in DATA_FILES:
        walk(json.loads((ROOT / f).read_text(encoding="utf-8")))
    return keys


def load_keys(name: str, builder: list[str]) -> set[str]:
    p = ROOT / "i18n" / name
    if not p.is_file():
        subprocess.run([sys.executable, *builder], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    return set(json.loads(p.read_text(encoding="utf-8")))


def update(code: str, name: str, keys: set[str], todo: bool) -> None:
    p = ROOT / "i18n" / code / f"{name}.json"
    old = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    meta = {k: v for k, v in old.items() if k.startswith("@")}
    dropped = sorted(k for k in old if not k.startswith("@") and k not in keys and old[k])
    new = {**meta, **{k: old.get(k, "") for k in sorted(keys)}}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(new, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    untranslated = [k for k in sorted(keys) if not new.get(k)]
    print(f"{code}/{name}: {len(keys)} keys, {len(keys) - len(untranslated)} translated, {len(untranslated)} to do"
          + (f", dropped {len(dropped)} obsolete" if dropped else ""))
    for k in dropped[:20]:
        print(f"  dropped: {k[:90]}")
    if todo:
        (p.parent / f"todo-{name}.json").write_text(json.dumps({k: "" for k in untranslated}, ensure_ascii=False, indent=1) + "\n",
                                                   encoding="utf-8")


def main() -> int:
    keys = load_keys(".build-keys.json", ["scripts/build_site.py"]) | js_keys()
    dk = ROOT / "i18n" / ".diagram-keys.json"
    if dk.is_file():
        keys |= set(json.loads(dk.read_text(encoding="utf-8")))
    keys = {k for k in keys if re.search(r"[А-Яа-яЁё]", k)}
    todo = "--todo" in sys.argv
    for name, ks in (("ui", keys), ("data", data_keys())):
        for l in i18n.LANGS[1:]:
            update(l["code"], name, ks, todo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
