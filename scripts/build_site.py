#!/usr/bin/env python3
"""Build the static site from content/*.md, data/content-manifest.json and data/curriculum.json.

Output (committed, served by GitHub Pages from the repo root):
  index.html            course map (tracks -> modules)
  m/<id>.html           one page per module
  ref/index.html        reference hub; ref/<stack>.html per firmware/stack
  pages/<name>.html     hand-written pages from content/pages/*.html
  api/v1/*.json         static "API": the same JSON a future server will return

Usage:
  python scripts/build_site.py
"""
from __future__ import annotations

import html
import json
import shutil
import sys
from pathlib import Path

_scripts = Path(__file__).resolve().parent
if str(_scripts) not in sys.path:
    sys.path.insert(0, str(_scripts))

from content_pipeline import (  # noqa: E402
    LEVEL_LABELS,
    ROADMAP_URL,
    block_to_paragraphs,
    diagnostics_to_html,
    extract_section,
    format_inline,
    load_manifest,
    parse_front_matter,
    parse_pipe_references,
    parse_yaml_references,
    strip_front_matter,
)

ROOT = _scripts.parent
CURRICULUM_PATH = ROOT / "data" / "curriculum.json"
GC = "lib/ground-control-ui/dist"
REPO_URL = "https://github.com/irreligious86/UAV-Education"
SITE_TITLE = "UAV Student"

PAGES = {
    "glossary": "Глоссарий",
    "fails": "Журнал ошибок и фейлов",
    "checklists": "Быстрые чек-листы",
    "compare": "Сравнение прошивок",
    "resources": "Ресурсы и сообщества",
}

GENERATED_DIRS = ("m", "ref", "pages", "api")

esc = html.escape


# ---------------------------------------------------------------- data model


def load_curriculum() -> dict:
    return json.loads(CURRICULUM_PATH.read_text(encoding="utf-8"))


def build_model() -> dict:
    """Join manifest (articles by stack) and curriculum (tracks) into one module table."""
    manifest = load_manifest()
    curriculum = load_curriculum()

    stacks = []
    articles: dict[str, dict] = {}
    for sec in manifest["sections"]:
        stacks.append({"key": sec["sectionKey"], "title": sec["title"], "ids": [a["id"] for a in sec["articles"]]})
        for a in sec["articles"]:
            articles[a["id"]] = {**a, "stack": sec["sectionKey"], "stackTitle": sec["title"]}

    modules: dict[str, dict] = {}
    groups = []  # tracks + electives, in display order
    for kind, items in (("track", curriculum["tracks"]), ("elective", curriculum["electives"])):
        for t_index, t in enumerate(items):
            group = {**t, "kind": kind, "index": t_index, "moduleIds": []}
            for m in t["modules"]:
                art = articles.get(m["id"])
                status = art["status"] if art else "planned"
                if status == "draft":
                    continue
                modules[m["id"]] = {
                    **m,
                    "title": art["title"] if art else m["title"],
                    "status": status,
                    "group": t["id"],
                    "groupTitle": t["title"],
                    "groupKind": kind,
                    "articleMeta": art,
                }
                group["moduleIds"].append(m["id"])
            groups.append(group)

    # Articles that exist in the manifest but are not placed in the curriculum still get a page.
    for aid, art in articles.items():
        if aid not in modules and art["status"] != "draft":
            modules[aid] = {
                "id": aid, "title": art["title"], "level": art["level"], "hours": None,
                "prerequisites": [], "objectives": [], "lab": None, "stacks": [art["stack"]],
                "status": art["status"], "group": None, "groupTitle": None, "groupKind": None,
                "articleMeta": art,
            }
    return {"stacks": stacks, "modules": modules, "groups": groups, "curriculum": curriculum}


# ---------------------------------------------------------------- layout


def layout(*, title: str, base: str, body: str, active: str, description: str = "", extra_head: str = "") -> str:
    nav_items = [
        ("course", f"{base}index.html", "Курс"),
        ("ref", f"{base}ref/index.html", "Справочник"),
        ("glossary", f"{base}pages/glossary.html", "Глоссарий"),
        ("fails", f"{base}pages/fails.html", "Фейлы"),
    ]
    current = ' aria-current="page"'
    nav = "\n".join(
        f'        <a href="{href}"{current if key == active else ""}>{label}</a>'
        for key, href, label in nav_items
    )
    full_title = SITE_TITLE if title == SITE_TITLE else f"{title} — {SITE_TITLE}"
    return f"""<!doctype html>
<html lang="ru" data-theme="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(full_title)}</title>
  <meta name="description" content="{esc(description or 'Инженерный курс по БПЛА: от физики полёта до своих прошивок и бортовых компьютеров.')}">
  <link rel="stylesheet" href="{base}{GC}/ground-control.css">
  <link rel="stylesheet" href="{base}assets/site.css">
  <script src="{base}{GC}/ground-control.js" defer></script>
  <script src="{base}assets/progress-store.js" defer></script>
  <script src="{base}assets/app.js" defer></script>{extra_head}
</head>
<body class="gc-root">
  <header class="site-header">
    <div class="gc-container site-header__inner">
      <a class="site-brand" href="{base}index.html"><span class="site-brand__mark" aria-hidden="true">◆</span> {SITE_TITLE}</a>
      <nav class="gc-nav" aria-label="Разделы сайта">
{nav}
      </nav>
    </div>
  </header>
  <main class="gc-container site-main">
{body}
  </main>
  <footer class="gc-container site-footer gc-muted">
    <p>Открытый курс · <a href="{REPO_URL}">исходники на GitHub</a> · <a href="{ROADMAP_URL}">план развития</a> · <a href="{base}curriculum/curriculum.html">для разработчика</a> · CC BY-NC-SA 4.0</p>
  </footer>
</body>
</html>
"""


def level_tag(level: str) -> str:
    label = LEVEL_LABELS.get(level, level)
    return f'<span class="gc-tag" title="{esc(label)}">{esc(level)}</span>'


def status_tag(status: str) -> str:
    if status == "planned":
        return '<span class="gc-tag" data-state="caution">СКОРО</span>'
    return ""


def hours_text(h) -> str:
    if h is None:
        return ""
    h = float(h)
    return f"~{int(h) if h.is_integer() else h} ч"


# ---------------------------------------------------------------- home: course map


def module_row(m: dict, n: int, base: str) -> str:
    planned = m["status"] == "planned"
    tags = [level_tag(m["level"])]
    if m.get("hours"):
        tags.append(f'<span class="gc-tag">{hours_text(m["hours"])}</span>')
    if planned:
        tags.append(status_tag("planned"))
    tags.append('<span class="gc-tag" data-state="ok" data-done-badge hidden>ПРОЙДЕН</span>')
    return f"""          <li class="track-module{' track-module--planned' if planned else ''}" data-module-id="{esc(m['id'])}">
            <span class="track-module__num">{n:02d}</span>
            <a class="track-module__title" href="{base}m/{esc(m['id'])}.html">{esc(m['title'])}</a>
            <span class="track-module__tags">{''.join(tags)}</span>
          </li>"""


def render_group(g: dict, model: dict, base: str) -> str:
    mods = [model["modules"][i] for i in g["moduleIds"]]
    published_ids = [m["id"] for m in mods if m["status"] == "published"]
    total_h = sum(float(m.get("hours") or 0) for m in mods)
    kicker = (
        f'Трек {g["index"]} · {esc(g.get("level", ""))} · {esc(g.get("audience", ""))}'
        if g["kind"] == "track"
        else "Электив"
    )
    rows = "\n".join(module_row(m, i, base) for i, m in enumerate(mods, start=1))
    capstone = ""
    if g.get("capstone"):
        c = g["capstone"]
        capstone = f"""
        <div class="gc-callout" data-state="ok">
          <strong>Итоговый проект: {esc(c['title'])}</strong>
          <div class="gc-muted">Результат: {esc(c['result'])}</div>
        </div>"""
    goal = f'\n        <p class="track__goal">{esc(g["goal"])}</p>' if g.get("goal") else ""
    written = sum(1 for m in mods if m["status"] == "published")
    return f"""      <section class="track gc-panel" id="track-{esc(g['id'])}" aria-labelledby="track-{esc(g['id'])}-title">
        <p class="gc-label gc-muted">{kicker}</p>
        <h2 class="gc-title" id="track-{esc(g['id'])}-title">{esc(g['title'])}</h2>{goal}
        <div class="track__stats gc-muted">
          <span>{len(mods)} модулей · {hours_text(total_h)} · написано {written}</span>
          <span data-progress-label="{esc(','.join(published_ids))}"></span>
        </div>
        <div class="gc-progress" role="progressbar" aria-label="Пройдено в треке «{esc(g['title'])}»" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" data-progress-of="{esc(','.join(published_ids))}" style="--gc-value: 0%"></div>
        <ol class="track__modules">
{rows}
        </ol>{capstone}
      </section>"""


def render_home(model: dict) -> str:
    base = ""
    tracks = [g for g in model["groups"] if g["kind"] == "track"]
    electives = [g for g in model["groups"] if g["kind"] == "elective"]
    all_published = [m["id"] for m in model["modules"].values() if m["status"] == "published"]
    core = [i for g in tracks for i in g["moduleIds"]]
    core_written = sum(1 for i in core if model["modules"][i]["status"] == "published")
    toc = "\n".join(
        f'          <a class="gc-tag" href="#track-{esc(g["id"])}">{g["index"]}. {esc(g["title"])}</a>' for g in tracks
    )
    cap = model["curriculum"].get("capstoneElective")
    backlog = ", ".join(model["curriculum"].get("backlogTopics", []))
    body = f"""    <section class="home-hero">
      <h1 class="gc-display">Инженерный курс по БПЛА</h1>
      <p class="home-hero__lead">От «почему он летает» до настройки по логам, автономных миссий и своего кода на борту.
      Учись по трекам по порядку: каждый следующий опирается на предыдущий. Нужна конкретная тема по прошивке — открой <a href="ref/index.html">справочник</a>.</p>
      <div class="home-hero__stats">
        <span class="gc-tag">{len(core)} модулей в ядре</span>
        <span class="gc-tag" data-state="ok">написано {core_written}</span>
        <span class="gc-tag" data-state="caution">в работе {len(core) - core_written}</span>
      </div>
      <p class="gc-label gc-muted">Твой прогресс <span data-progress-label="{esc(','.join(all_published))}"></span></p>
      <div class="gc-progress" role="progressbar" aria-label="Твой прогресс по курсу" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" data-progress-of="{esc(','.join(all_published))}" style="--gc-value: 0%"></div>
      <p class="gc-muted home-hero__note">Прогресс хранится только в этом браузере.</p>
      <nav class="home-toc" aria-label="Треки">
{toc}
      </nav>
    </section>

{chr(10).join(render_group(g, model, base) for g in tracks)}

    <h2 class="gc-title section-title">Элективы</h2>
    <p class="gc-muted">Необязательные ветки: другие прошивки на тех же принципах.</p>
{chr(10).join(render_group(g, model, base) for g in electives)}

    <section class="gc-panel">
      <p class="gc-label gc-muted">Дальше</p>
      <p>Итоговый проект-электив: <strong>{esc(cap['title'] if cap else '')}</strong>.</p>
      <p class="gc-muted">Темы в бэклоге: {esc(backlog)}.</p>
    </section>"""
    redirect = """
  <script>
    // Old single-page links (index.html#bf-filters) -> module pages.
    (function () {
      var ids = %s;
      var h = decodeURIComponent(location.hash.slice(1));
      if (h && ids.indexOf(h) !== -1) location.replace("m/" + h + ".html");
    })();
  </script>""" % json.dumps(sorted(model["modules"]))
    return layout(title=SITE_TITLE, base=base, body=body, active="course", extra_head=redirect)


# ---------------------------------------------------------------- module page


def render_references(refs_body: str, fm: str | None) -> str:
    items = parse_pipe_references(refs_body)
    if not items and fm:
        items = parse_yaml_references(fm)
    lis = []
    for title, url, tier in items:
        if not url:
            continue
        state = ' data-state="info"' if tier.lower().startswith("primary") else ""
        lis.append(
            f'<li><a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(title)}</a> '
            f'<span class="gc-tag"{state}>{esc(tier)}</span></li>'
        )
    return "<ul class=\"refs\">" + "".join(lis) + "</ul>" if lis else ""


def render_checklist(block: str, mid: str) -> str:
    lines = [ln.strip()[2:].strip() for ln in block.splitlines() if ln.strip().startswith("- ")]
    if not lines:
        return ""
    items = "".join(
        f'<li><label><input type="checkbox" data-check-id="{esc(mid)}:{i}"><span>{format_inline(t)}</span></label></li>'
        for i, t in enumerate(lines)
    )
    return f'<ul class="gc-checklist">{items}</ul>'


def yaml_id_list(fm: str | None, key: str) -> list[str]:
    """Read a simple YAML list (inline [a, b] or '- a' lines) from front matter."""
    if not fm:
        return []
    out: list[str] = []
    collecting = False
    for line in fm.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{key}:"):
            inline = stripped[len(key) + 1 :].strip()
            if inline.startswith("[") and inline.endswith("]"):
                out += [x.strip().strip("'\"") for x in inline[1:-1].split(",") if x.strip()]
                break
            collecting = True
            continue
        if collecting:
            if stripped.startswith("- "):
                out.append(stripped[2:].strip().strip("'\""))
            elif stripped and not stripped.startswith("#"):
                break
    return out


def render_related(m: dict, model: dict) -> str:
    art = m.get("articleMeta")
    if not art:
        return ""
    fm = parse_front_matter((ROOT / art["sourceFile"]).read_text(encoding="utf-8"))
    ids = [i for i in yaml_id_list(fm, "related") if i in model["modules"] and i != m["id"]]
    if not ids:
        return ""
    links = "".join(
        f'<a class="gc-card" href="{esc(i)}.html"><strong>{esc(model["modules"][i]["title"])}</strong>'
        f'<div class="gc-card__meta">{level_tag(model["modules"][i]["level"])}{status_tag(model["modules"][i]["status"])}</div></a>'
        for i in ids
    )
    return f'<section class="related" aria-label="Смежные модули"><p class="gc-label gc-muted">Смежные модули</p><div class="gc-grid ref-grid">{links}</div></section>'


def article_sections(m: dict) -> tuple[str, str]:
    """Return (summary_html, body_html) for a published article."""
    art = m["articleMeta"]
    raw = (ROOT / art["sourceFile"]).read_text(encoding="utf-8")
    fm = parse_front_matter(raw)
    body = strip_front_matter(raw)
    summary = extract_section(body, "summary")
    parts = []
    for key, heading in (("theory", "Теория"), ("practice", "Практика")):
        block = extract_section(body, key)
        if block:
            parts.append(f"<h2>{heading}</h2>\n{block_to_paragraphs(block)}")
    diag = extract_section(body, "diagnostics")
    if diag:
        parts.append(f"<h2>Диагностика</h2>\n{diagnostics_to_html(diag)}")
    notes = extract_section(body, "notes")
    if notes:
        parts.append(f"<h2>Заметки</h2>\n{block_to_paragraphs(notes)}")
    checklist = render_checklist(extract_section(body, "checklist"), m["id"])
    if checklist:
        parts.append(f"<h2>Чек-лист</h2>\n{checklist}")
    refs = render_references(extract_section(body, "references"), fm)
    if refs:
        parts.append(f"<h2>Источники</h2>\n{refs}")
    summary_html = format_inline(" ".join(summary.split())) if summary else ""
    return summary_html, "\n\n".join(parts)


def neighbours(m: dict, model: dict) -> tuple[dict | None, dict | None]:
    if not m["group"]:
        return None, None
    g = next(g for g in model["groups"] if g["id"] == m["group"])
    ids = g["moduleIds"]
    i = ids.index(m["id"])
    prev = model["modules"][ids[i - 1]] if i > 0 else None
    nxt = model["modules"][ids[i + 1]] if i + 1 < len(ids) else None
    return prev, nxt


def render_module(m: dict, model: dict) -> str:
    base = "../"
    planned = m["status"] == "planned"
    art = m.get("articleMeta") or {}

    crumbs = [f'<a href="{base}index.html">Курс</a>']
    if m["group"]:
        crumbs.append(f'<a href="{base}index.html#track-{esc(m["group"])}">{esc(m["groupTitle"])}</a>')
    elif art:
        crumbs.append(f'<a href="{base}ref/{esc(art["stack"])}.html">{esc(art["stackTitle"])}</a>')
    crumbs.append(f"<span>{esc(m['title'])}</span>")

    tags = [f'<span class="gc-tag" title="Уровень">{esc(LEVEL_LABELS.get(m["level"], m["level"]))}</span>']
    if art.get("readingTime") and not planned:
        tags.append(f'<span class="gc-tag">чтение {esc(str(art["readingTime"]))}</span>')
    if m.get("hours"):
        tags.append(f'<span class="gc-tag">учёба {hours_text(m["hours"])}</span>')
    if art.get("firmware"):
        tags.append(f'<span class="gc-tag">{esc(str(art["firmware"]))}</span>')
    if planned:
        tags.append(status_tag("planned"))

    blocks = []
    if m.get("objectives"):
        lis = "".join(f"<li>{esc(o)}</li>" for o in m["objectives"])
        blocks.append(f'<div class="gc-callout" data-state="ok"><strong>После модуля ты умеешь</strong><ul>{lis}</ul></div>')
    prereq = [model["modules"][p] for p in m.get("prerequisites", []) if p in model["modules"]]
    if prereq:
        links = ", ".join(f'<a href="{esc(p["id"])}.html">{esc(p["title"])}</a>' for p in prereq)
        blocks.append(f'<p class="gc-muted">Перед этим модулем: {links}</p>')
    if m.get("lab"):
        blocks.append(f'<div class="gc-callout"><strong>Лабораторная</strong><div>{esc(m["lab"])}</div></div>')

    if planned:
        summary_html = ""
        content = (
            '<div class="gc-callout" data-state="caution"><strong>Модуль в разработке.</strong> '
            f'Цели и связи уже определены, текст пишется. План — в <a href="{ROADMAP_URL}">ROADMAP</a>.</div>'
        )
        done_toggle = ""
    else:
        summary_html, content = article_sections(m)
        done_toggle = (
            f'<div class="module-done"><gc-button variant="secondary" data-done-toggle="{esc(m["id"])}">'
            "Отметить как пройденный</gc-button></div>"
        )

    prev, nxt = neighbours(m, model)
    pager = []
    if prev:
        pager.append(f'<a class="gc-card pager__prev" href="{esc(prev["id"])}.html"><span class="gc-label gc-muted">Назад</span><br>{esc(prev["title"])}</a>')
    if nxt:
        pager.append(f'<a class="gc-card pager__next" href="{esc(nxt["id"])}.html"><span class="gc-label gc-muted">Дальше</span><br>{esc(nxt["title"])}</a>')
    pager_html = f'<nav class="pager" aria-label="Соседние модули">{"".join(pager)}</nav>' if pager else ""
    related_html = render_related(m, model)

    lead = f'<p class="module-lead">{summary_html}</p>' if summary_html else ""
    body = f"""    <article class="module" data-module-page="{esc(m['id'])}">
      <p class="gc-breadcrumb">{''.join(crumbs)}</p>
      <h1 class="module-title">{esc(m['title'])}</h1>
      <div class="module-tags">{''.join(tags)}<span class="gc-tag" data-state="ok" data-done-badge hidden>ПРОЙДЕН</span></div>
      {lead}
      {''.join(blocks)}
      <div class="gc-prose module-body">
{content}
      </div>
      {done_toggle}
      {related_html}
      {pager_html}
    </article>"""
    return layout(title=m["title"], base=base, body=body, active="course", description=" ".join(m.get("objectives", [])))


# ---------------------------------------------------------------- reference


def render_ref_index(model: dict) -> str:
    base = "../"
    cards = []
    for s in model["stacks"]:
        mods = [model["modules"][i] for i in s["ids"] if i in model["modules"]]
        done = sum(1 for m in mods if m["status"] == "published")
        cards.append(
            f'<a class="gc-card" href="{esc(s["key"])}.html"><strong>{esc(s["title"])}</strong>'
            f'<div class="gc-card__meta"><span class="gc-tag" data-state="ok">написано {done}</span>'
            f'<span class="gc-tag">всего {len(mods)}</span></div></a>'
        )
    pages = "".join(f'<a class="gc-card" href="../pages/{k}.html"><strong>{esc(v)}</strong></a>' for k, v in PAGES.items())
    body = f"""    <h1 class="gc-display">Справочник</h1>
    <p class="gc-muted">Те же модули, что в курсе, но сгруппированные по прошивкам и стекам.</p>
    <div class="gc-grid ref-grid">{''.join(cards)}</div>
    <h2 class="gc-title section-title">Материалы</h2>
    <div class="gc-grid ref-grid">{pages}</div>"""
    return layout(title="Справочник", base=base, body=body, active="ref")


def render_ref_stack(stack: dict, model: dict) -> str:
    base = "../"
    order = {"L1": 1, "L2": 2, "L3": 3, "L4": 4}
    mods = sorted(
        (model["modules"][i] for i in stack["ids"] if i in model["modules"]),
        key=lambda m: (order.get(m["level"], 9), m["status"] != "published", m["title"]),
    )
    cards = []
    for m in mods:
        planned = m["status"] == "planned"
        where = f'<span class="gc-tag">трек: {esc(m["groupTitle"])}</span>' if m["group"] else ""
        pending = ' data-state="pending"' if planned else ""
        cards.append(
            f'<a class="gc-card" href="../m/{esc(m["id"])}.html"{pending} data-module-id="{esc(m["id"])}">'
            f'<strong>{esc(m["title"])}</strong><div class="gc-card__meta">{level_tag(m["level"])}{status_tag(m["status"])}{where}'
            '<span class="gc-tag" data-state="ok" data-done-badge hidden>ПРОЙДЕН</span></div></a>'
        )
    body = f"""    <p class="gc-breadcrumb"><a href="index.html">Справочник</a><span>{esc(stack['title'])}</span></p>
    <h1 class="gc-display">{esc(stack['title'])}</h1>
    <div class="gc-grid ref-grid">{''.join(cards)}</div>"""
    return layout(title=stack["title"], base=base, body=body, active="ref")


def render_page(name: str, title: str) -> str:
    base = "../"
    inner = (ROOT / "content" / "pages" / f"{name}.html").read_text(encoding="utf-8")
    active = name if name in ("glossary", "fails") else "ref"
    body = f"""    <p class="gc-breadcrumb"><a href="../ref/index.html">Справочник</a><span>{esc(title)}</span></p>
    <div class="gc-prose legacy-page">
{inner}
    </div>"""
    return layout(title=title, base=base, body=body, active=active)


# ---------------------------------------------------------------- static API


def api_payload(model: dict) -> dict:
    """Shape of GET /api/v1/curriculum. Keep stable: a future server returns the same JSON."""
    def mod(m):
        return {
            "id": m["id"], "title": m["title"], "level": m["level"], "hours": m.get("hours"),
            "status": m["status"], "prerequisites": m.get("prerequisites", []),
            "objectives": m.get("objectives", []), "url": f"m/{m['id']}.html",
        }
    return {
        "version": 1,
        "groups": [
            {"id": g["id"], "kind": g["kind"], "title": g["title"], "level": g.get("level"),
             "goal": g.get("goal"), "capstone": g.get("capstone"),
             "modules": [mod(model["modules"][i]) for i in g["moduleIds"]]}
            for g in model["groups"]
        ],
    }


# ---------------------------------------------------------------- main


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    model = build_model()
    for d in GENERATED_DIRS:
        shutil.rmtree(ROOT / d, ignore_errors=True)

    write(ROOT / "index.html", render_home(model))
    for m in model["modules"].values():
        write(ROOT / "m" / f"{m['id']}.html", render_module(m, model))
    write(ROOT / "ref" / "index.html", render_ref_index(model))
    for s in model["stacks"]:
        write(ROOT / "ref" / f"{s['key']}.html", render_ref_stack(s, model))
    for name, title in PAGES.items():
        write(ROOT / "pages" / f"{name}.html", render_page(name, title))
    write(ROOT / "api" / "v1" / "curriculum.json", json.dumps(api_payload(model), ensure_ascii=False, indent=2) + "\n")

    n_pub = sum(1 for m in model["modules"].values() if m["status"] == "published")
    print(f"built: {len(model['modules'])} module pages ({n_pub} written), {len(model['stacks'])} stacks, {len(PAGES)} pages")


if __name__ == "__main__":
    main()
