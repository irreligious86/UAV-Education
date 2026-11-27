# -*- coding: utf-8 -*-
"""Shared Markdown parsing and HTML fragment rendering used by build_site.py."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "data" / "content-manifest.json"

SYMPTOM_WORDS = ("Симптом:", "Symptom:", "Příznak:")   # diagnostics card marker in every site language
REQUIRED_MD_HEADINGS = ("summary", "theory", "practice", "diagnostics", "references")

# Article lifecycle:
#   published — real content, rendered in full
#   planned   — slot reserved in the course map; module page shows goals + "in progress"
#   draft     — work in progress; not built into the site
VALID_STATUSES = ("published", "planned", "draft")

ROADMAP_URL = "https://github.com/irreligious86/UAV-Education/blob/main/ROADMAP.md"

# Placeholder fragments that must never reach a published article.
PLACEHOLDER_MARKERS = (
    "example.com",
    "(черновик)",
    "Заглушка",
    "заменить конкретной ссылкой",
)

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
    # Поддержка inline markdown: **bold** и `inline code`
    parts = re.split(r"(\*\*.+?\*\*|`[^`]+`)", text)
    out: list[str] = []
    for p in parts:
        if p.startswith("**") and p.endswith("**") and len(p) > 4:
            inner = html.escape(p[2:-2])
            out.append(f"<strong>{inner}</strong>")
        elif p.startswith("`") and p.endswith("`") and len(p) > 2:
            inner = html.escape(p[1:-1])
            out.append(f"<code>{inner}</code>")
        else:
            out.append(html.escape(p))
    return "".join(out)


# ---------------------------------------------------------------- stable heading ids
# Section headings of a lesson body (h2, h3, h4.md-subheading — the selector of assets/history.js headings()) get an
# id derived from their text, so reading history, notes, bookmarks and feedback (docs/MULTIUSER-PLAN.md §14) keep
# pointing at the same section when a heading is added above. The id fits the anchor check of
# supabase/migrations/0007 (^[A-Za-z0-9_-]{0,80}$) with room for a "-copy-N" suffix of a note copy.
TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i", "й": "y",
    "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "і": "i", "ї": "yi", "є": "ye", "ґ": "g", "ў": "u",
}
SLUG_MAX = 60
LEGACY_ANCHOR_RE = re.compile(r"^sec-\d+$")      # the old positional ids; a slug must never look like one
HEADING_RE = re.compile(r"<(h2|h3|h4)(\s[^>]*)?>(.*?)</\1>", re.DOTALL)
_ID_ATTR_RE = re.compile(r'\sid="([^"]*)"')
_DIV_RE = re.compile(r"<(/?)div\b[^>]*>", re.IGNORECASE)
_BODY_DIV_RE = re.compile(r'<div\b[^>]*\sclass="[^"]*\bmodule-body\b[^"]*"[^>]*>')


def module_body_span(page: str) -> tuple[int, int] | None:
    """(start, end) of the inside of the lesson body <div class="… module-body"> — the same region as the JS selector
    ".module-body h2" (descendants, nested <article class="diag-item"> included). The end is found by <div> depth:
    the body's children close their divs, and code is HTML-escaped, so no literal "<div" hides in text."""
    m = _BODY_DIV_RE.search(page)
    if not m:
        return None
    depth = 1
    for d in _DIV_RE.finditer(page, m.end()):
        depth += -1 if d.group(1) else 1
        if depth == 0:
            return m.end(), d.start()
    return m.end(), len(page)


def slugify(text: str) -> str:
    """Heading text -> "[a-z0-9-]" id: Cyrillic transliterated, other letters without diacritics, at most SLUG_MAX."""
    import unicodedata
    text = html.unescape(re.sub(r"<[^>]+>", "", text)).lower()
    out = "".join(TRANSLIT.get(ch, ch) for ch in text)
    out = unicodedata.normalize("NFKD", out).encode("ascii", "ignore").decode("ascii")
    out = re.sub(r"[^a-z0-9]+", "-", out).strip("-")
    if len(out) > SLUG_MAX:
        cut = out[:SLUG_MAX]
        out = (cut.rsplit("-", 1)[0] if "-" in cut[SLUG_MAX // 2:] else cut).strip("-")
    if not out:
        out = "section"
    if LEGACY_ANCHOR_RE.match(out):
        out += "-h"
    return out


def _unique(base: str, taken: set[str]) -> str:
    """base, or base-2, base-3 … — never taken, never a legacy "sec-N" look-alike (a heading "Sec" twice)."""
    stem = base[:SLUG_MAX - 4].rstrip("-") or "section"
    cand, n = base, 1
    while cand in taken or LEGACY_ANCHOR_RE.match(cand):
        n += 1
        cand = f"{stem}-{n}"
        if LEGACY_ANCHOR_RE.match(cand):
            cand = f"{stem}-h{n}"
    return cand


def assign_heading_ids(page: str, source: list[tuple[str, str]] | None = None,
                       fresh: bool = True) -> tuple[str, list[tuple[str, str]]]:
    """Give every section heading of the lesson body (module_body_span) a stable id.

    Without `source` (the source-language page) the id comes from the heading text. With `source` — [(tag, id)] of
    the same page in the source language — a translated page reuses those ids, so a note or bookmark (keyed by
    module + anchor) lands on the same section in every language:
      - fresh=True (the translation matches the current source, or the page shows the source / build-generated
        headings only): the whole list by position when the heading structure is the same;
      - otherwise (a stale translation, whose sub-headings may be a different set with the same count) only the
        h2 ids, when the h2 count matches — the h2 skeleton (Теория, Практика, Диагностика, …) comes from fixed
        section keys; every h3/h4 gets a slug of its own text. A wrong section is worse than no shared id.
    Ids the page already has are kept. Returns the page and its [(tag, id)] list.
    """
    span = module_body_span(page)
    if not span:
        return page, []
    start, end = span
    found = []
    for m in HEADING_RE.finditer(page, start, end):
        tag, attrs = m.group(1), m.group(2) or ""
        if tag == "h4" and "md-subheading" not in attrs:
            continue                                      # diagnostics cards and the like are not sections
        idm = _ID_ATTR_RE.search(attrs)
        found.append((m, tag, idm.group(1) if idm else None, m.group(3)))
    if not found:
        return page, []
    taken = set(_ID_ATTR_RE.findall(page))
    wanted: list[str | None] = [None] * len(found)
    tags = [f[1] for f in found]
    if source:
        stags = [t for t, _ in source]
        if fresh and stags == tags:
            wanted = [i for _, i in source]
        else:
            h2, sh2 = [k for k, t in enumerate(tags) if t == "h2"], [k for k, t in enumerate(stags) if t == "h2"]
            if len(h2) == len(sh2):
                for i, j in zip(h2, sh2):
                    wanted[i] = source[j][1]
    ids: list[str] = []
    for k, (m, tag, own, text) in enumerate(found):
        if own:
            ids.append(own)
            continue
        new = _unique(wanted[k] or slugify(text), taken)
        taken.add(new)
        ids.append(new)
    out, pos = [], 0
    for (m, tag, own, text), new in zip(found, ids):
        if own:
            continue
        cut = m.start() + len(tag) + 1                    # right after "<h2"
        out.append(page[pos:cut] + f' id="{html.escape(new)}"')
        pos = cut
    out.append(page[pos:])
    return "".join(out), [(f[1], i) for f, i in zip(found, ids)]


# Interactive widgets: a line "{{widget:name}}" in Markdown becomes <uav-name></uav-name>.
# Registered names only, so a typo fails validation instead of rendering a dead tag.
WIDGETS = {"pid-sim", "filter-response", "elrs-calc", "tw-calc", "wire-drop", "link-latency", "attitude-3d",
           "kalman-1d", "link-margin", "gsd-calc", "rpm-harmonics", "antenna-pol"}
WIDGET_RE = re.compile(r"^\{\{widget:([a-z0-9-]+)\}\}$")

# Diagrams: a line "{{diagram:id|Caption}}" inlines assets/diagrams/<id>.svg inside a <figure>.
# Inline SVG inherits CSS variables (theme) and works offline; the validator checks the file exists.
DIAGRAM_RE = re.compile(r"^\{\{diagram:([a-z0-9-]+)\|(.+?)\}\}$")
DIAGRAMS_DIR = ROOT / "assets" / "diagrams"
_svg_cache: dict[str, str] = {}


def diagram_svg(name: str) -> str | None:
    import i18n   # the current language's diagram if it was generated (assets/diagrams/<dir>/), else the source one
    key = f"{i18n.lang()}:{name}"
    if key in _svg_cache:
        return _svg_cache[key]
    f = DIAGRAMS_DIR / f"{name}.svg"
    for code in reversed(i18n.chain(i18n.lang())):      # nearest language wins
        d = i18n.lang_dir(code)
        if (DIAGRAMS_DIR / d / f"{name}.svg").is_file():
            f = DIAGRAMS_DIR / d / f"{name}.svg"
    if not f.is_file():
        return None
    svg = f.read_text(encoding="utf-8")
    svg = re.sub(r"<\?xml[^>]*\?>\s*", "", svg).strip()
    _svg_cache[key] = svg
    return svg


def render_diagram(name: str, caption: str) -> str:
    import i18n   # the scroll hint is an interface string (i18n/<lang>/ui.json)
    svg = diagram_svg(name)
    if svg is None:
        return ""
    return (f'<figure class="diagram" data-diagram="{name}"><div class="diagram__svg">{svg}</div>'
            f'<figcaption class="gc-muted">{format_inline(caption)}</figcaption>'
            f'<div class="diagram__hint">{html.escape(i18n._("Схему можно прокрутить по горизонтали"))}</div></figure>')


# Lesson cards: a line "{{lesson:id|Why to read it}}" becomes a highlighted link card to another module
# (title from the manifest, translated through the data catalog). The validator checks the id exists.
LESSON_RE = re.compile(r"^\{\{lesson:([a-z0-9-]+)\|(.+?)\}\}$")
_titles: dict[str, str] = {}


def module_title(mid: str) -> str | None:
    if not _titles:
        import json
        man = json.loads((ROOT / "data" / "content-manifest.json").read_text(encoding="utf-8"))
        for sec in man.get("sections", []):
            for a in sec.get("articles", []):
                _titles[a["id"]] = a.get("title", a["id"])
    return _titles.get(mid)


def render_lesson(mid: str, why: str) -> str:
    import i18n
    title = module_title(mid)
    if title is None:
        return ""
    title = i18n.tr_data(title)
    label = i18n._("Отдельный урок")
    return (f'<a class="gc-callout lesson-card" data-state="ok" href="../m/{mid}.html">'
            f'<span class="gc-label gc-muted">{html.escape(label)} →</span>'
            f'<strong class="lesson-card__title">{html.escape(title)}</strong>'
            f'<span class="lesson-card__why">{format_inline(why)}</span></a>')


TABLE_SEP_RE = re.compile(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")


def _is_table_row(line: str) -> bool:
    t = line.strip()
    return t.startswith("|") and t.count("|") >= 2


def split_table_row(line: str) -> list[str]:
    """Split '| a | b |' into cells; '\\|' is a literal pipe."""
    t = line.strip()
    if t.startswith("|"):
        t = t[1:]
    if t.endswith("|") and not t.endswith("\\|"):
        t = t[:-1]
    cells, cur, i = [], "", 0
    while i < len(t):
        if t[i] == "\\" and i + 1 < len(t) and t[i + 1] == "|":
            cur += "|"; i += 2; continue
        if t[i] == "|":
            cells.append(cur.strip()); cur = ""
        else:
            cur += t[i]
        i += 1
    cells.append(cur.strip())
    return cells


def split_runs(lines: list[str]) -> list[tuple[str, list[str]]]:
    """Group the lines of one paragraph into runs: table (header + separator + rows), ul, ol, text.
    Lets a sentence introduce a list or a table without a blank line, as people write Markdown."""
    runs: list[tuple[str, list[str]]] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if _is_table_row(ln) and i + 1 < len(lines) and TABLE_SEP_RE.match(lines[i + 1].strip()):
            j = i + 2
            while j < len(lines) and _is_table_row(lines[j]):
                j += 1
            runs.append(("table", lines[i:j])); i = j; continue
        kind = "ul" if ln.strip().startswith("- ") else "ol" if re.match(r"^\d+\.\s", ln.strip()) else "text"
        if runs and runs[-1][0] == kind and kind != "table":
            runs[-1][1].append(ln)
        else:
            runs.append((kind, [ln]))
        i += 1
    return runs


def render_table(run: list[str]) -> str:
    head = split_table_row(run[0])
    aligns = []
    for c in split_table_row(run[1]):
        c = c.strip()
        aligns.append("center" if c.startswith(":") and c.endswith(":") else "right" if c.endswith(":") else "")
    def cell(tag, text, k):
        a = aligns[k] if k < len(aligns) and aligns[k] else ""
        style = f' style="text-align:{a}"' if a else ""
        label = f' data-label="{html.escape(re.sub(r"[`*]", "", head[k]), quote=True)}"' if tag == "td" and k < len(head) else ""
        return f"<{tag}{style}{label}>{format_inline(text)}</{tag}>"
    n = len(head)
    thead = "".join(cell("th", h, k) for k, h in enumerate(head))
    body = []
    for row in run[2:]:
        cells = split_table_row(row)
        cells = (cells + [""] * n)[:n]
        body.append("<tr>" + "".join(cell("td", c, k) for k, c in enumerate(cells)) + "</tr>")
    return (f'<div class="table-wrap md-table-wrap" tabindex="0"><table class="md-table">'
            f"<thead><tr>{thead}</tr></thead><tbody>{''.join(body)}</tbody></table></div>")


def block_to_paragraphs(block: str) -> str:
    block = block.strip()
    if not block:
        return ""
    chunks: list[str] = []

    def render_text_chunk(text: str) -> None:
        for para in re.split(r"\r?\n\r?\n+", text):
            para = para.strip()
            if not para:
                continue
            para_l = para.lstrip()
            wm = WIDGET_RE.match(para_l)
            if wm:
                name = wm.group(1)
                if name in WIDGETS:
                    chunks.append(f'<uav-{name} class="widget"></uav-{name}>')
                continue
            lm = LESSON_RE.match(para_l)
            if lm:
                chunks.append(render_lesson(lm.group(1), lm.group(2).strip()))
                continue
            dm = DIAGRAM_RE.match(para_l)
            if dm:
                chunks.append(render_diagram(dm.group(1), dm.group(2).strip()))
                continue
            # Fallback: если абзац начинается с ###, всегда рендерим как подзаголовок.
            # Это защищает от "сырых ###" в контенте с неидеальными переносами.
            if para_l.startswith("### "):
                first, *rest = para_l.splitlines()
                htxt = format_inline(first[4:].strip())
                chunks.append(f'<h4 class="md-subheading">{htxt}</h4>')
                if rest:
                    tail = "\n".join(rest).strip()
                    if tail:
                        render_text_chunk(tail)
                continue
            # Поддержка подзаголовков внутри секций (например, ### ...)
            heading_lines = [ln.strip() for ln in para.splitlines() if ln.strip()]
            if (
                len(heading_lines) == 1
                and heading_lines[0].startswith("### ")
                and len(heading_lines[0]) > 4
            ):
                htxt = format_inline(heading_lines[0][4:].strip())
                chunks.append(f'<h4 class="md-subheading">{htxt}</h4>')
                continue

            lines = [ln.rstrip() for ln in para.splitlines() if ln.strip()]
            for kind, run in split_runs(lines):
                if kind == "table":
                    chunks.append(render_table(run))
                elif kind == "ul":
                    items = "".join(f"<li>{format_inline(ln.strip()[2:].strip())}</li>" for ln in run)
                    chunks.append(f"<ul>{items}</ul>")
                elif kind == "ol":
                    items = "".join(f"<li>{format_inline(re.sub(r'^\d+\.\s+', '', ln.strip()))}</li>" for ln in run)
                    chunks.append(f"<ol>{items}</ol>")
                else:
                    chunks.append("<p>" + format_inline(" ".join(ln.strip() for ln in run)) + "</p>")

    # Поддержка fenced code blocks: ```lang ... ```
    # Если блоков нет, рендерим как раньше.
    fence_re = re.compile(r"```[^\r\n]*\r?\n(.*?)\r?\n```", re.DOTALL)
    pos = 0
    for m in fence_re.finditer(block):
        before = block[pos : m.start()]
        if before.strip():
            render_text_chunk(before)
        code = m.group(1).rstrip("\n")
        if code.strip():
            chunks.append(
                '<pre class="cli-block"><code>' + html.escape(code) + "</code></pre>"
            )
        pos = m.end()
    tail = block[pos:]
    if tail.strip():
        render_text_chunk(tail)

    if not chunks:
        render_text_chunk(block)
    return "\n".join(chunks)


def diagnostics_to_html(block: str) -> str:
    block = block.strip()
    if not block:
        return ""
    raw_lines = [ln.rstrip() for ln in block.splitlines() if ln.strip()]

    # Группировка "Симптом -> причина -> действие" в отдельные карточки диагностики.
    groups: list[tuple[str, list[str]]] = []
    i = 0
    while i < len(raw_lines):
        stripped = raw_lines[i].strip()
        is_symptom = (
            stripped.startswith("- ")
            and any(k in stripped for k in SYMPTOM_WORDS)
        )
        if not is_symptom:
            i += 1
            continue
        title = stripped[2:].strip()
        details: list[str] = []
        i += 1
        while i < len(raw_lines):
            cur = raw_lines[i]
            cur_stripped = cur.strip()
            # Следующий симптом — новая карточка.
            if cur_stripped.startswith("- ") and any(k in cur_stripped for k in SYMPTOM_WORDS):
                break
            # Дочерние пункты внутри симптома.
            if cur.startswith("  - ") or cur.startswith("\t- "):
                details.append(cur_stripped[2:].strip())
            # Плоский markdown-список без отступов: "- Возможная причина:", "- Что сделать:"
            elif cur_stripped.startswith("- "):
                details.append(cur_stripped[2:].strip())
            # Запасной вариант: обычные строки тоже прикрепляем к текущей карточке.
            elif cur_stripped:
                details.append(cur_stripped)
            i += 1
        groups.append((title, details))

    if groups:
        cards: list[str] = []
        for title, details in groups:
            if details:
                detail_items = "".join(
                    f"<li>{format_inline(item)}</li>" for item in details if item
                )
                details_html = f"<ul>{detail_items}</ul>"
            else:
                details_html = ""
            cards.append(
                '<article class="diag-item">'
                f"<h4>{format_inline(title)}</h4>"
                f"{details_html}"
                "</article>"
            )
        return '<div class="diag-groups">' + "".join(cards) + "</div>"

    lines = [ln.strip() for ln in raw_lines]
    if all(ln.startswith("- ") for ln in lines):
        items = "".join(f"<li>{format_inline(ln[2:])}</li>" for ln in lines)
        return f'<ul class="diag-list">{items}</ul>'
    return block_to_paragraphs(block)


def parse_pipe_references(body: str) -> list[tuple[str, str, str]]:
    """Строки `- title | url | tier` в теле ## references."""
    out: list[tuple[str, str, str]] = []
    for line in body.splitlines():
        rest = line.strip()
        if rest.startswith("- "):
            rest = rest[2:].strip()
        parts = [p.strip() for p in rest.split("|")]
        if len(parts) >= 3 and parts[1].startswith("http"):
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
                            url = sl.split(":", 1)[1].strip().strip("\"'")
                        elif sl.startswith("tier:"):
                            tier = sl.split(":", 1)[1].strip().strip("\"'")
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
