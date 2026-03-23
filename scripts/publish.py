#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Валидация, сборка TOC и статей, вставка в index.html по маркерам AUTO:*.

  python scripts/publish.py
  python scripts/publish.py --include-drafts --dry-run
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_scripts = Path(__file__).resolve().parent
if str(_scripts) not in sys.path:
    sys.path.insert(0, str(_scripts))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from content_pipeline import (  # noqa: E402
    INDEX_PATH,
    filter_articles,
    load_manifest,
    render_article_html,
    render_progress_html,
    render_toc_html,
    replace_between_markers,
)


def run_validate() -> None:
    validate_script = _scripts / "validate_content.py"
    r = subprocess.run([sys.executable, str(validate_script)], cwd=_scripts.parent)
    if r.returncode != 0:
        raise SystemExit(r.returncode)


def publish_index(include_drafts: bool, dry_run: bool) -> None:
    manifest = load_manifest()
    html = INDEX_PATH.read_text(encoding="utf-8")
    missing = []

    for section in manifest.get("sections", []):
        sk = section["sectionKey"]
        arts = filter_articles(section, include_drafts=include_drafts)
        toc = render_toc_html(section, arts)
        progress = render_progress_html(section, len(arts))
        articles_inner = "\n\n".join(
            render_article_html(a, include_drafts=include_drafts) for a in arts
        ).strip()

        start_toc = f"<!-- AUTO:TOC:{sk}:start -->"
        end_toc = f"<!-- AUTO:TOC:{sk}:end -->"
        start_art = f"<!-- AUTO:ARTICLES:{sk}:start -->"
        end_art = f"<!-- AUTO:ARTICLES:{sk}:end -->"
        start_pr = f"<!-- AUTO:PROGRESS:{sk}:start -->"
        end_pr = f"<!-- AUTO:PROGRESS:{sk}:end -->"

        html, ok_toc = replace_between_markers(html, start_toc, end_toc, toc)
        if not ok_toc:
            missing.append(f"TOC:{sk}")
        html, ok_art = replace_between_markers(html, start_art, end_art, articles_inner)
        if not ok_art:
            missing.append(f"ARTICLES:{sk}")
        html, ok_pr = replace_between_markers(html, start_pr, end_pr, progress)
        if not ok_pr:
            missing.append(f"PROGRESS:{sk}")

    if missing:
        print(
            "В index.html не найдены маркеры (добавьте комментарии AUTO:...): "
            + ", ".join(missing),
            file=sys.stderr,
        )
        raise SystemExit(1)

    if dry_run:
        print("--- dry-run: index.html не записан ---")
        print(html[:4000])
        if len(html) > 4000:
            print("\n... [обрезано]")
        return

    INDEX_PATH.write_text(html, encoding="utf-8")
    print(f"Обновлён: {INDEX_PATH}")


def main() -> None:
    ap = argparse.ArgumentParser(description="UAV Student — публикация контента в index.html")
    ap.add_argument(
        "--include-drafts",
        action="store_true",
        help="Включить статьи со status: draft в TOC и HTML",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Не писать index.html, вывести начало результата",
    )
    ap.add_argument(
        "--skip-validate",
        action="store_true",
        help="Не запускать validate_content.py перед сборкой",
    )
    args = ap.parse_args()

    if not args.skip_validate:
        run_validate()

    publish_index(include_drafts=args.include_drafts, dry_run=args.dry_run)

    if not args.dry_run:
        print("Готово. Откройте index.html в браузере.")


if __name__ == "__main__":
    main()
