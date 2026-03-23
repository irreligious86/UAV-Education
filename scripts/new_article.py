#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Создание черновика статьи и записи в манифесте.

  python scripts/new_article.py inav inav-gps-fix "GPS Fix и диагностика" L2
"""
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

TAB_IDS = {
    "betaflight": "tab-betaflight",
    "inav": "tab-inav",
    "ardupilot": "tab-ardupilot",
    "px4": "tab-px4",
    "companion": "tab-companion",
    "tools": "tab-tools",
}

SECTION_TITLES = {
    "betaflight": "Betaflight",
    "inav": "INAV",
    "ardupilot": "ArduPilot",
    "px4": "PX4",
    "companion": "Companion",
    "tools": "Инструменты",
}

FIRMWARE_DEFAULT = {
    "betaflight": "Betaflight 4.5+",
    "inav": "INAV 7.0+",
    "ardupilot": "ArduPilot 4.5+",
    "px4": "PX4 1.15+",
    "companion": "MAVLink / Companion",
    "tools": "—",
}

TEMPLATE = """---
id: {id}
title: "{title}"
level: {level}
readingTime: 15 мин
firmware: {firmware}
status: draft
tags:
  - черновик
references:
  - title: Official docs (заменить)
    url: https://example.com
    tier: primary | A
related: []
next: []
---

## summary
Краткое описание модуля.

## theory
Теоретическая часть.

## practice
1. Шаг 1
2. Шаг 2
3. Шаг 3

## diagnostics
- Типовая ошибка 1
- Типовая ошибка 2

## references
- Official docs | https://example.com | primary | A

## checklist
- Пункт проверки 1
- Пункт проверки 2
"""


def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        return {"sections": []}
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def save_manifest(data: dict) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 5:
        print(
            "Использование: python scripts/new_article.py <section> <id> \"<title>\" <level>",
            file=sys.stderr,
        )
        raise SystemExit(1)

    section_key, article_id, title, level = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]

    if section_key not in TAB_IDS:
        print(f"Неизвестная секция: {section_key}. Допустимо: {', '.join(TAB_IDS)}", file=sys.stderr)
        raise SystemExit(1)

    manifest = load_manifest()
    section = next((s for s in manifest["sections"] if s["sectionKey"] == section_key), None)

    if section is None:
        section = {
            "tabId": TAB_IDS[section_key],
            "sectionKey": section_key,
            "title": SECTION_TITLES.get(section_key, section_key.upper()),
            "articles": [],
        }
        manifest.setdefault("sections", []).append(section)

    if any(a["id"] == article_id for s in manifest["sections"] for a in s["articles"]):
        print(f"Ошибка: id '{article_id}' уже существует.")
        raise SystemExit(1)

    section_dir = ROOT / "content" / section_key
    section_dir.mkdir(parents=True, exist_ok=True)

    source_file = section_dir / f"{article_id}.md"
    if source_file.exists():
        print(f"Ошибка: файл уже существует: {source_file}")
        raise SystemExit(1)

    firmware = FIRMWARE_DEFAULT.get(section_key, "Указать версию")

    source_file.write_text(
        TEMPLATE.format(id=article_id, title=title.replace('"', '\\"'), level=level, firmware=firmware),
        encoding="utf-8",
    )

    next_order = max((a.get("order", 0) for a in section["articles"]), default=0) + 1
    section["articles"].append(
        {
            "id": article_id,
            "title": title,
            "level": level,
            "order": next_order,
            "readingTime": "15 мин",
            "firmware": firmware,
            "sourceFile": f"content/{section_key}/{article_id}.md",
            "status": "draft",
            "tags": ["черновик"],
            "type": "article",
        }
    )

    save_manifest(manifest)
    print(f"Создана статья: {source_file}")
    print(f"Добавлена запись в manifest: {article_id} (status: draft)")


if __name__ == "__main__":
    main()
