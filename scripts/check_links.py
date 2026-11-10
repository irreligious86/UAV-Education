#!/usr/bin/env python3
"""Check local links in the built site: every relative href/src must point to an existing file,
and every #anchor must exist in the target page. External (http/https/mailto) links are skipped.

Usage: python scripts/check_links.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
SITE_DIRS = ("m", "ref", "pages", "cap", "path", "projects")
sys.path.insert(0, str(ROOT / "scripts"))
import i18n  # noqa: E402

TREES = [ROOT] + [ROOT / l["dir"] for l in i18n.LANGS if l["dir"]]   # every language tree (docs/I18N.md)
TREES += [ROOT / o for l in i18n.LANGS for o in l.get("oldDirs", [])]   # redirect pages of former URLs
ATTR = re.compile(r'(?:href|src)="([^"]+)"')
ID = re.compile(r'\bid="([^"]+)"')


def main() -> int:
    pages = []
    for tree in TREES:
        pages.append(tree / "index.html")
        for d in SITE_DIRS:
            pages += sorted((tree / d).rglob("*.html"))
    ids_cache: dict[Path, set[str]] = {}
    errors = []
    for page in pages:
        text = page.read_text(encoding="utf-8")
        for link in ATTR.findall(text):
            if re.match(r"^(https?:|mailto:|data:)", link):
                continue
            path_part, _, anchor = link.partition("#")
            path_part = path_part.split("?", 1)[0]  # query strings (e.g. ?path=betaflight) are client-side context
            target = page if not path_part else (page.parent / unquote(path_part)).resolve()
            rel = page.relative_to(ROOT)
            if not target.exists():
                errors.append(f"{rel}: broken link {link}")
                continue
            if anchor and target.suffix == ".html":
                if target not in ids_cache:
                    ids_cache[target] = set(ID.findall(target.read_text(encoding="utf-8")))
                if anchor not in ids_cache[target]:
                    errors.append(f"{rel}: missing anchor {link}")
    for e in errors:
        print(f"::error::{e}")
    print(f"check_links: {len(pages)} pages, {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
