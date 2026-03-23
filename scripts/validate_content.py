#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка манифеста и .md. Запуск: python scripts/validate_content.py"""
from __future__ import annotations

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "data" / "content-manifest.json"
REQUIRED_ARTICLE_KEYS = ("id", "title", "level", "order", "status", "sourceFile", "type")
REQUIRED_MD_HEADINGS = ("summary", "theory", "practice", "diagnostics", "references")


def load_manifest():
    import json

    with MANIFEST_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def collect_article_ids(manifest):
    ids = []
    for section in manifest.get("sections", []):
        for art in section.get("articles", []):
            ids.append(art["id"])
    return ids


def validate_manifest_structure(manifest):
    errors = []
    if "sections" not in manifest:
        return ["Корень manifest: отсутствует ключ 'sections'"]
    for i, sec in enumerate(manifest["sections"]):
        for k in ("tabId", "sectionKey", "title", "articles"):
            if k not in sec:
                errors.append(f"Секция [{i}]: нет ключа '{k}'")
        arts = sec.get("articles", [])
        for j, art in enumerate(arts):
            for k in REQUIRED_ARTICLE_KEYS:
                if k not in art:
                    errors.append(f"Секция {sec.get('sectionKey', '?')}, статья [{j}]: нет '{k}'")
    return errors


def validate_duplicate_ids(ids):
    seen = {}
    for i in ids:
        seen[i] = seen.get(i, 0) + 1
    return [f"Дублируется id: {k} ({v} раз)" for k, v in seen.items() if v > 1]


def validate_source_files(manifest):
    errors = []
    for sec in manifest.get("sections", []):
        for art in sec.get("articles", []):
            rel = art.get("sourceFile")
            if not rel:
                continue
            path = ROOT / rel
            if art.get("status") == "published" and not path.is_file():
                errors.append(f"published, файл не найден: {rel} (id={art.get('id')})")
    return errors


def _parse_front_matter(text):
    if not text.startswith("---"):
        return None
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    return m.group(1) if m else None


def _extract_yaml_id_list(fm, key):
    lines = fm.splitlines()
    collecting = False
    items = []
    key_line = re.compile(rf"^{re.escape(key)}\s*:\s*(.*)$")
    for line in lines:
        m = key_line.match(line.strip())
        if m:
            collecting = True
            inline = m.group(1).strip()
            if inline.startswith("[") and inline.endswith("]"):
                inner = inline[1:-1].strip()
                if inner:
                    for part in inner.split(","):
                        p = part.strip().strip("'\"")
                        if p:
                            items.append(p)
                collecting = False
            continue
        if not collecting:
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(stripped[2:].strip().strip("'\""))
            continue
        if not stripped:
            continue
        if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*\s*:", stripped):
            break
    return items


def validate_related_in_frontmatter(md_path, all_ids):
    errors = []
    text = md_path.read_text(encoding="utf-8")
    fm = _parse_front_matter(text)
    if fm is None:
        return []
    for label in ("related", "next"):
        for ref in _extract_yaml_id_list(fm, label):
            if not ref or ref.startswith("http"):
                continue
            if re.match(r"^[a-z0-9-]+$", ref) and ref not in all_ids:
                rel = md_path.relative_to(ROOT)
                errors.append(f"{rel}: {label} → несуществующий id «{ref}»")
    return errors


def _markdown_body(text):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4 :]
    return text


def validate_published_sections(md_path, published):
    if not published:
        return []
    text = md_path.read_text(encoding="utf-8")
    body = _markdown_body(text).lower()
    errors = []
    rel = md_path.relative_to(ROOT)
    for sec in REQUIRED_MD_HEADINGS:
        token = f"## {sec}"
        if token not in body:
            errors.append(f"{rel}: нет секции «{token}» (обязательно для published)")
    return errors


def main():
    if not MANIFEST_PATH.is_file():
        print(f"Нет {MANIFEST_PATH}", file=sys.stderr)
        sys.exit(1)

    manifest = load_manifest()
    errs = validate_manifest_structure(manifest)
    ids = collect_article_ids(manifest)
    errs.extend(validate_duplicate_ids(ids))

    all_ids_set = set(ids)
    errs.extend(validate_source_files(manifest))

    published_by_file = {}
    for sec in manifest.get("sections", []):
        for art in sec.get("articles", []):
            rel = art.get("sourceFile")
            if not rel:
                continue
            published_by_file[ROOT / rel] = art.get("status") == "published"

    for p in (ROOT / "content").rglob("*.md"):
        if p.name.upper() == "README.MD":
            continue
        errs.extend(validate_related_in_frontmatter(p, all_ids_set))
        pub = published_by_file.get(p, False)
        errs.extend(validate_published_sections(p, pub))

    if errs:
        print("Ошибки валидации:\n", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    print("validate_content: OK")
    print(f"  статей в манифесте: {len(ids)}")
    print(f"  уникальных id: {len(all_ids_set)}")


if __name__ == "__main__":
    main()
