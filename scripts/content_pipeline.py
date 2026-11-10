# -*- coding: utf-8 -*-
"""Shared Markdown parsing and HTML fragment rendering used by build_site.py."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "data" / "content-manifest.json"

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
    svg = diagram_svg(name)
    if svg is None:
        return ""
    return (f'<figure class="diagram" data-diagram="{name}"><div class="diagram__svg">{svg}</div>'
            f'<figcaption class="gc-muted">{format_inline(caption)}</figcaption>'
            '<div class="diagram__hint">Схему можно прокрутить по горизонтали</div></figure>')


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
            and ("Симптом:" in stripped or "Symptom:" in stripped)
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
            if cur_stripped.startswith("- ") and (
                "Симптом:" in cur_stripped or "Symptom:" in cur_stripped
            ):
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
