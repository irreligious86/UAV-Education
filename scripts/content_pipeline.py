# -*- coding: utf-8 -*-
"""Общая логика: парсинг .md, рендер HTML, маркеры index.html."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "data" / "content-manifest.json"
INDEX_PATH = ROOT / "index.html"
BUILD_DIR = ROOT / "build"

REQUIRED_MD_HEADINGS = ("summary", "theory", "practice", "diagnostics", "references")

LEVEL_LABELS = {
    "L1": "L1 — Оператор",
    "L2": "L2 — Интегратор",
    "L3": "L3 — Специалист",
    "L4": "L4 — Эксперт",
}


def load_manifest() -> dict:
    with MANIFEST_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def strip_front_matter(text: str) -> str:
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4 :].lstrip()


def parse_front_matter(text: str) -> str | None:
    if not text.startswith("---"):
        return None
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    return m.group(1) if m else None


def extract_section(md_body: str, name: str) -> str:
    # MULTILINE: ^ совпадает с началом строки; DOTALL: . включает \n внутри секции
    pat = rf"^##\s+{re.escape(name)}\s*\n(.*?)(?=^##\s|\Z)"
    m = re.search(pat, md_body, flags=re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""


def format_inline(text: str) -> str:
    parts = re.split(r"(\*\*.+?\*\*)", text)
    out: list[str] = []
    for p in parts:
        if p.startswith("**") and p.endswith("**") and len(p) > 4:
            inner = html.escape(p[2:-2])
            out.append(f"<strong>{inner}</strong>")
        else:
            out.append(html.escape(p))
    return "".join(out)


def block_to_paragraphs(block: str) -> str:
    block = block.strip()
    if not block:
        return ""
    chunks: list[str] = []
    for para in re.split(r"\n\n+", block):
        para = para.strip()
        if not para:
            continue
        lines = [ln.rstrip() for ln in para.splitlines() if ln.strip()]
        if all(ln.startswith("- ") for ln in lines) and lines:
            items = "".join(f"<li>{format_inline(ln[2:].strip())}</li>" for ln in lines)
            chunks.append(f"<ul>{items}</ul>")
        elif all(re.match(r"^\d+\.\s", ln) for ln in lines if ln):
            items = "".join(
                f"<li>{format_inline(re.sub(r'^\d+\.\s+', '', ln))}</li>" for ln in lines
            )
            chunks.append(f"<ol>{items}</ol>")
        else:
            chunks.append("<p>" + format_inline(para.replace("\n", " ")) + "</p>")
    return "\n".join(chunks)


def diagnostics_to_html(block: str) -> str:
    block = block.strip()
    if not block:
        return ""
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    if all(ln.startswith("- ") for ln in lines):
        items = "".join(f"<li>{format_inline(ln[2:])}</li>" for ln in lines)
        return f"<ul>{items}</ul>"
    return block_to_paragraphs(block)


def parse_pipe_references(body: str) -> list[tuple[str, str, str]]:
    """Строки `- title | url | tier` в теле ## references."""
    out: list[tuple[str, str, str]] = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        rest = line[2:].strip()
        parts = [p.strip() for p in rest.split("|")]
        if len(parts) >= 3:
            out.append((parts[0], parts[1], parts[2]))
    return out


def parse_yaml_references(fm: str) -> list[tuple[str, str, str]]:
    """Упрощённый разбор references из YAML front matter."""
    out: list[tuple[str, str, str]] = []
    lines = fm.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("references:"):
            i += 1
            while i < len(lines):
                line = lines[i]
                stripped = line.strip()
                if stripped.startswith("- title:"):
                    title = stripped.split(":", 1)[1].strip().strip('"')
                    url, tier = "", "primary | A"
                    i += 1
                    while i < len(lines) and (lines[i].startswith(" ") or lines[i].startswith("\t")):
                        sl = lines[i].strip()
                        if sl.startswith("url:"):
                            url = sl.split(":", 1)[1].strip()
                        elif sl.startswith("tier:"):
                            tier = sl.split(":", 1)[1].strip()
                        i += 1
                    if url:
                        out.append((title, url, tier))
                    continue
                first_tok = stripped.split()[0] if stripped.split() else ""
                if stripped and not stripped.startswith("#") and ":" in first_tok:
                    # следующий ключ верхнего уровня
                    break
                i += 1
            break
        i += 1
    return out


def render_references_html(
    refs_body: str, fm: str | None
) -> str:
    items: list[tuple[str, str, str]] = parse_pipe_references(refs_body)
    if not items and fm:
        items = parse_yaml_references(fm)
    if not items:
        return ""
    lis = []
    for title, url, tier in items:
        if not url:
            continue
        lis.append(
            f'<li>\n              <a href="{html.escape(url)}" class="doc-link" '
            f'target="_blank" rel="noopener noreferrer">{html.escape(title)}</a>\n'
            f'              <span class="tag">{html.escape(tier)}</span>\n            </li>'
        )
    if not lis:
        return ""
    return (
        '        <div class="references">\n'
        '          <h4>📚 Источники</h4>\n'
        "          <ul>\n"
        + "\n".join(lis)
        + "\n          </ul>\n        </div>"
    )


def render_checklist_html(block: str, article_id: str) -> str:
    block = block.strip()
    if not block:
        return ""
    lines = [ln.strip()[2:].strip() for ln in block.splitlines() if ln.strip().startswith("- ")]
    if not lines:
        return ""
    cid = f"{article_id}-checklist"
    items = "".join(
        f'\n            <li><label><input type="checkbox"> {format_inline(t)}</label></li>'
        for t in lines
    )
    return (
        f'        <div class="checklist" id="{html.escape(cid)}">\n'
        f"          <h4>✅ Чек-лист</h4>\n"
        f'          <ul class="checklist-list">{items}\n'
        f"          </ul>\n        </div>"
    )


def firmware_for_article(article: dict, fm: str | None) -> str:
    if article.get("firmware"):
        return str(article["firmware"])
    if fm:
        m = re.search(r"^firmware:\s*(.+)$", fm, re.MULTILINE)
        if m:
            return m.group(1).strip()
    tags = article.get("tags") or []
    if tags:
        return str(tags[0])
    return "—"


def render_article_html(article: dict, include_drafts: bool = False) -> str:
    st = article.get("status", "published")
    if st == "draft" and not include_drafts:
        return ""

    path = ROOT / article["sourceFile"]
    if not path.is_file():
        return f"<!-- ERROR: нет файла {article['sourceFile']} -->\n"

    raw = path.read_text(encoding="utf-8")
    fm = parse_front_matter(raw)
    body = strip_front_matter(raw)

    summary = extract_section(body, "summary")
    theory = extract_section(body, "theory")
    practice = extract_section(body, "practice")
    diagnostics = extract_section(body, "diagnostics")
    refs = extract_section(body, "references")
    checklist = extract_section(body, "checklist")
    notes = extract_section(body, "notes")

    aid = article["id"]
    title = article.get("title", aid)
    level = article.get("level", "L1")
    rt = article.get("readingTime", "—")
    fw = firmware_for_article(article, fm)

    meta_parts = [
        f'<span class="tag">Уровень: {html.escape(LEVEL_LABELS.get(level, level))}</span>',
        f'<span class="tag">Время чтения: {html.escape(str(rt))}</span>',
        f'<span class="tag">{html.escape(fw)}</span>',
    ]
    for t in (article.get("tags") or [])[:2]:
        if str(t) != fw:
            meta_parts.append(f'<span class="tag">{html.escape(str(t))}</span>')

    data_added = "2026-03-21"
    if fm:
        m = re.search(r"^added:\s*(.+)$", fm, re.MULTILINE)
        if m:
            data_added = m.group(1).strip()

    parts: list[str] = [
        f'      <article id="{html.escape(aid)}" class="card" data-level="{html.escape(level)}" data-added="{html.escape(data_added)}">',
        f"        <h2>{html.escape(title)}</h2>",
        f'        <p class="muted">{format_inline(summary) if summary else ""}</p>',
        '        <div class="article-meta">',
    ]
    parts.extend(f"          {p}" for p in meta_parts)
    parts.append("        </div>")
    parts.append("")
    parts.append("        <h3>📖 Теория</h3>")
    parts.append(block_to_paragraphs(theory) if theory else "<p></p>")
    parts.append("")
    parts.append("        <h3>🛠 Практика</h3>")
    parts.append(block_to_paragraphs(practice) if practice else "<p></p>")
    parts.append("")
    parts.append("        <h3>🔍 Диагностика</h3>")
    parts.append(diagnostics_to_html(diagnostics) if diagnostics else "<p></p>")
    parts.append("")

    ref_html = render_references_html(refs, fm)
    if ref_html:
        parts.append(ref_html)

    if notes.strip():
        parts.append("        <section class=\"article-notes\" aria-labelledby=\"{0}-notes-title\">".format(aid))
        parts.append(f'          <h4 id="{aid}-notes-title">🗂 Заметки (из Markdown)</h4>')
        parts.append(f'          <div class="muted">{block_to_paragraphs(notes)}</div>')
        parts.append("        </section>")

    ch = render_checklist_html(checklist, aid)
    if ch:
        parts.append(ch)

    parts.append("      </article>")
    return "\n".join(parts)


def render_toc_html(section: dict, articles: list[dict]) -> str:
    title = section.get("title", section["sectionKey"])
    aria = f"Содержание раздела {title}"
    items: list[str] = []
    for i, a in enumerate(articles, start=1):
        num = str(i).zfill(2)
        items.append(
            f'        <a href="#{a["id"]}">\n'
            f'          <span class="toc__num">{num}</span>\n'
            f'          <span class="toc__level">{html.escape(a["level"])}</span>\n'
            f'          <span class="toc__label">{html.escape(a["title"])}</span>\n'
            f"        </a>"
        )
    inner = "\n".join(items)
    return (
        f'      <nav class="toc toc--enhanced" aria-label="{html.escape(aria)}">\n'
        f"{inner}\n"
        f"      </nav>"
    )


def render_progress_html(section: dict, n: int) -> str:
    sk = section["sectionKey"]
    title = section.get("title", sk)
    label = f"Раздел {title}"
    pct = 100 if n else 0
    if sk == "tools":
        stats = "Обзор стека ПО" if n <= 1 else f"{n} модулей"
        aria = f"{n} обзорный модуль" if n == 1 else f"{n} модулей"
    else:
        stats = f"{n} из {n} базовых модулей" if n else "0 модулей"
        aria = f"{n} из {n} модулей в базовой версии"
    return f"""      <div class="section-progress" aria-label="Прогресс раздела {html.escape(title)}">
        <span class="section-progress__label">{html.escape(label)}</span>
        <span class="section-progress__bar" role="progressbar" aria-valuenow="{n}" aria-valuemin="0" aria-valuemax="{n}" aria-label="{html.escape(aria)}">
          <span class="section-progress__fill" style="width:{pct}%"></span>
        </span>
        <span class="section-progress__stats">{html.escape(stats)}</span>
      </div>"""


def replace_between_markers(html: str, start: str, end: str, inner: str) -> tuple[str, bool]:
    pattern = re.escape(start) + r".*?" + re.escape(end)
    repl = start + "\n" + inner.rstrip() + "\n" + end
    new_html, n = re.subn(pattern, repl, html, count=1, flags=re.DOTALL)
    return new_html, n == 1


def filter_articles(
    section: dict, include_drafts: bool
) -> list[dict]:
    arts = section.get("articles", [])
    out = []
    level_order = {"L1": 1, "L2": 2, "L3": 3, "L4": 4}
    for a in arts:
        st = a.get("status", "published")
        if st == "published" or (include_drafts and st == "draft"):
            out.append(a)
    return sorted(
        out,
        key=lambda x: (
            level_order.get(str(x.get("level", "")).upper(), 99),
            int(x.get("order", 0)),
        ),
    )
