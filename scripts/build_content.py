#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборка TOC в build/<section>-toc.html. Запуск: python scripts/build_content.py

  python scripts/build_content.py --write-manifest  — перезаписать data/content-manifest.json из _manifest_data.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from content_pipeline import BUILD_DIR, filter_articles, load_manifest, render_toc_html

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_JSON = ROOT / "data" / "content-manifest.json"


def write_manifest_from_module() -> None:
    from _manifest_data import SECTIONS  # noqa: WPS433

    MANIFEST_JSON.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_JSON.write_text(
        json.dumps({"sections": SECTIONS}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Записано: {MANIFEST_JSON}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--write-manifest",
        action="store_true",
        help="Сгенерировать data/content-manifest.json из scripts/_manifest_data.py",
    )
    args = ap.parse_args()
    if args.write_manifest:
        write_manifest_from_module()
        return

    manifest = load_manifest()
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    for section in manifest["sections"]:
        arts = filter_articles(section, include_drafts=False)
        if not arts:
            continue
        html = render_toc_html(section, arts)
        out = BUILD_DIR / f'{section["sectionKey"]}-toc.html'
        out.write_text(html + "\n", encoding="utf-8")
        print(f"OK: {out.relative_to(BUILD_DIR.parent)}")


if __name__ == "__main__":
    main()
