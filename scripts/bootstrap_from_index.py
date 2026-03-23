#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Разовая подготовка / миграция (документация + резервные копии).

В текущей репозитории:
- исходники статей лежат в content/<section>/*.md;
- порядок и разделы — в data/content-manifest.json;
- сборка в index.html — scripts/publish.py (маркеры AUTO:TOC / AUTO:ARTICLES / AUTO:PROGRESS).

Полноценный парсер index.html → .md не включён (хрупкий, ломается на кастомной вёрстке).
Если нужна миграция из старого HTML — делайте выборочно по статьям или вручную.

Использование:
  python scripts/bootstrap_from_index.py --backup
      Создаёт копии index.html и curriculum.html с суффиксом .backup.pre-automation.*
      только если таких файлов ещё нет.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
CURR = ROOT / "curriculum" / "curriculum.html"


def maybe_backup(src: Path, dst: Path) -> str:
    if not src.is_file():
        return f"пропуск: нет {src.name}"
    if dst.exists():
        return f"уже есть: {dst.name}"
    shutil.copy2(src, dst)
    return f"создано: {dst}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Резервные копии перед массовой автоматизацией")
    ap.add_argument(
        "--backup",
        action="store_true",
        help="Сохранить index.html и curriculum.html как *.backup.pre-automation.*",
    )
    args = ap.parse_args()

    if not args.backup:
        print(__doc__)
        print("\nДля создания резервных копий: python scripts/bootstrap_from_index.py --backup")
        sys.exit(0)

    out = []
    if INDEX.is_file():
        out.append(
            maybe_backup(INDEX, ROOT / "index.backup.pre-automation.html")
        )
    if CURR.is_file():
        out.append(
            maybe_backup(CURR, ROOT / "curriculum" / "curriculum.backup.pre-automation.html")
        )
    for line in out:
        print(line)


if __name__ == "__main__":
    main()
