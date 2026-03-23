#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Создаёт недостающие content/**/*.md по data/content-manifest.json (черновики)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "data" / "content-manifest.json"

STUB = """---
id: {id}
title: "{title}"
level: {level}
readingTime: "{readingTime}"
status: published
tags:
{tags_yaml}
references:
  - title: Заглушка — заменить на первичный источник
    url: https://example.com
    tier: primary | A
related: []
next: []
---

## summary
Краткое описание модуля (черновик; при переносе в сайт синхронизировать с `index.html`).

## theory
Теоретическая основа (черновик).

## practice
1. Первый практический шаг (черновик).

## diagnostics
- **Симптом:** что проверить (черновик).

## references
- Официальная документация стека — заменить конкретной ссылкой (tier A).
"""


def main() -> None:
    if not MANIFEST_PATH.is_file():
        print(f"Нет {MANIFEST_PATH}", file=sys.stderr)
        sys.exit(1)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    created = 0
    skipped = 0
    for sec in manifest.get("sections", []):
        for art in sec.get("articles", []):
            rel = art.get("sourceFile")
            if not rel:
                continue
            path = ROOT / rel
            if path.is_file():
                skipped += 1
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            tags = art.get("tags") or []
            tags_yaml = "\n".join(f"  - {t}" for t in tags) if tags else "  - черновик"
            text = STUB.format(
                id=art["id"],
                title=art["title"].replace('"', '\\"'),
                level=art["level"],
                readingTime=art.get("readingTime", ""),
                tags_yaml=tags_yaml,
            )
            path.write_text(text, encoding="utf-8")
            created += 1
            print(f"+ {rel}")
    print(f"Готово: создано {created}, пропущено (уже есть) {skipped}")


if __name__ == "__main__":
    main()
