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
import re
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
    render_diagram,
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
    "formulas": "Формулы и команды",
    "checklists": "Быстрые чек-листы",
    "compare": "Сравнение прошивок",
    "resources": "Ресурсы и сообщества",
    "prerequisites": "Входные требования и тест",
}

GENERATED_DIRS = ("m", "ref", "pages", "api", "quiz", "cap", "path", "tasks", "projects")
PROJECTS_SRC = ROOT / "data" / "projects.json"
QUIZ_SRC = ROOT / "content" / "quiz"
TASKS_SRC = ROOT / "content" / "tasks"
TASK_VARIANTS = 8

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
    paths = []
    for p in curriculum.get("paths", []):
        ordered = [mid for st in p["stages"] for mid in st["modules"] if mid in modules]
        paths.append({**p, "moduleIds": ordered})
    pdata = json.loads(PROJECTS_SRC.read_text(encoding="utf-8")) if PROJECTS_SRC.is_file() else {}
    projects = pdata.get("projects", [])
    return {"stacks": stacks, "modules": modules, "groups": groups, "curriculum": curriculum, "paths": paths,
            "projects": projects, "project_rubric": pdata.get("rubric", [])}


# ---------------------------------------------------------------- layout


def layout(*, title: str, base: str, body: str, active: str, description: str = "", extra_head: str = "") -> str:
    nav_items = [
        ("course", f"{base}index.html", "Курс"),
        ("ref", f"{base}ref/index.html", "Справочник"),
        ("glossary", f"{base}pages/glossary.html", "Глоссарий"),
        ("fails", f"{base}pages/fails.html", "Фейлы"),
        ("search", f"{base}pages/search.html", "Поиск"),
        ("progress", f"{base}pages/progress.html", "Мой прогресс"),
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
  <link rel="icon" href="{base}assets/favicon.svg" type="image/svg+xml">
  <link rel="manifest" href="{base}manifest.webmanifest">
  <meta name="theme-color" content="#0b0f14">
  <link rel="stylesheet" href="{base}{GC}/ground-control.css">
  <link rel="stylesheet" href="{base}assets/site.css">
  <script src="{base}{GC}/ground-control.js" defer></script>
  <script src="{base}assets/progress-store.js" defer></script>
  <script src="{base}assets/grading.js" defer></script>
  <script src="{base}assets/app.js" defer></script>
  <script src="{base}assets/uav-quiz.js" defer></script>
  <script src="{base}assets/uav-tasks.js" defer></script>
  <script src="{base}assets/offline.js" defer></script>{extra_head}
</head>
<body class="gc-root" data-base="{base}">
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


def module_row(m: dict, n: int, base: str, path_id: str | None = None, shared: bool = False) -> str:
    planned = m["status"] == "planned"
    tags = [level_tag(m["level"])]
    if shared:
        tags.append('<span class="gc-tag" title="Общий модуль: засчитывается во всех путях, где он есть">общий</span>')
    q = f"?path={esc(path_id)}" if path_id else ""
    if m.get("hours"):
        tags.append(f'<span class="gc-tag">{hours_text(m["hours"])}</span>')
    if planned:
        tags.append(status_tag("planned"))
    tags.append('<span class="gc-tag" data-state="ok" data-done-badge hidden>ПРОЙДЕН</span>')
    return f"""          <li class="track-module{' track-module--planned' if planned else ''}" data-module-id="{esc(m['id'])}">
            <span class="track-module__num">{n:02d}</span>
            <a class="track-module__title" href="{base}m/{esc(m['id'])}.html{q}">{esc(m['title'])}</a>
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
        <a class="gc-card capstone-card" href="{base}cap/{esc(c['id'])}.html" data-module-id="{esc(c['id'])}">
          <p class="gc-label gc-muted">Итоговый проект</p>
          <strong>{esc(c['title'])}</strong>
          <div class="gc-muted">Результат: {esc(c['result'])}</div>
          <div class="gc-card__meta"><span class="gc-tag" data-state="ok" data-done-badge hidden>СДАН</span></div>
        </a>"""
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


def path_steps_attr(p: dict, model: dict) -> str:
    """id|title pairs of published steps, in path order — read by app.js for «Продолжить»."""
    return esc(";;".join(f"{m['id']}|{m['title']}" for m in (model["modules"][i] for i in p["moduleIds"]) if m["status"] == "published"))


def render_path_card(p: dict, model: dict, base: str) -> str:
    mods = [model["modules"][i] for i in p["moduleIds"]]
    pub = [m["id"] for m in mods if m["status"] == "published"]
    return f"""        <a class="gc-card path-card" href="{base}path/{esc(p['id'])}.html" data-path-card="{esc(p['id'])}">
          <p class="gc-label gc-muted">По прошивке</p>
          <strong>{esc(p['title'])}</strong>
          <div class="gc-muted">{esc(p['subtitle'])}</div>
          <div class="path-card__continue gc-muted" data-path-continue="{esc(p['id'])}" data-path-steps="{path_steps_attr(p, model)}" hidden></div>
          <div class="gc-card__meta"><span class="gc-tag">{len(mods)} шагов</span><span class="gc-tag" data-state="ok">написано {len(pub)}</span><span class="gc-tag" data-progress-label="{esc(','.join(pub))}"></span></div>
          <div class="gc-progress" role="progressbar" aria-label="Прогресс по пути {esc(p['title'])}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" data-progress-of="{esc(','.join(pub))}" style="--gc-value: 0%"></div>
        </a>"""


def shared_module_ids(model: dict) -> set:
    """Modules that appear in more than one firmware path."""
    seen, shared = set(), set()
    for p in model["paths"]:
        for mid in p["moduleIds"]:
            (shared if mid in seen else seen).add(mid)
    return shared


def render_path(p: dict, model: dict) -> str:
    base = "../"
    mods = [model["modules"][i] for i in p["moduleIds"]]
    pub = [m["id"] for m in mods if m["status"] == "published"]
    shared = shared_module_ids(model)
    n = 0
    stages = []
    for st in p["stages"]:
        rows = []
        for mid in st["modules"]:
            if mid not in model["modules"]:
                continue
            n += 1
            m = model["modules"][mid]
            rows.append(module_row(m, n, base, path_id=p["id"], shared=mid in shared))
        stages.append(f"""      <section class="track gc-panel">
        <p class="gc-label gc-muted">Этап</p>
        <h2 class="gc-title">{esc(st['title'])}</h2>
        <ol class="track__modules">
{chr(10).join(rows)}
        </ol>
      </section>""")
    caps = []
    for cid in p.get("capstones", []):
        g = next((g for g in model["groups"] if g.get("capstone", {}).get("id") == cid), None)
        if g:
            c = g["capstone"]
            caps.append(f'<a class="gc-card capstone-card" href="{base}cap/{esc(cid)}.html" data-module-id="{esc(cid)}"><p class="gc-label gc-muted">Итоговый проект</p><strong>{esc(c["title"])}</strong><div class="gc-muted">{esc(c["result"])}</div><div class="gc-card__meta"><span class="gc-tag" data-state="ok" data-done-badge hidden>СДАН</span></div></a>')
    caps_html = f'<h2 class="gc-title section-title">Итоговые проекты</h2>{"".join(caps)}' if caps else ""
    body = f"""    <p class="gc-breadcrumb"><a href="{base}index.html">Курс</a><span>Путь: {esc(p['title'])}</span></p>
    <section class="home-hero">
      <h1 class="gc-display">{esc(p['title'])}</h1>
      <p class="home-hero__lead">{esc(p['goal'])}</p>
      <div class="home-hero__stats"><span class="gc-tag">{len(mods)} шагов</span><span class="gc-tag" data-state="ok">написано {len(pub)}</span><span class="gc-tag" data-state="caution">в работе {len(mods) - len(pub)}</span></div>
      <p class="gc-label gc-muted">Твой прогресс <span data-progress-label="{esc(','.join(pub))}"></span></p>
      <div class="gc-progress" role="progressbar" aria-label="Прогресс по пути" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" data-progress-of="{esc(','.join(pub))}" style="--gc-value: 0%"></div>
      <p class="ready-filter"><label class="gc-muted"><input type="checkbox" data-ready-only> Показывать только готовые модули</label></p>
      <p class="path-continue"><a class="gc-card" data-path-continue="{esc(p['id'])}" data-path-steps="{path_steps_attr(p, model)}" hidden></a></p>
      <p class="gc-muted home-hero__note">Иди по порядку: каждый шаг опирается на предыдущие. Модули с тегом «общий» входят и в другие пути — пройденный один раз, такой модуль засчитан везде. Открывай уроки отсюда: тогда кнопки «назад/дальше» ведут по шагам именно этого пути.</p>
    </section>
{chr(10).join(stages)}
    {caps_html}"""
    return layout(title=f"Путь {p['title']}", base=base, body=body, active="course", description=p["goal"])


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
      Выбери прошивку и иди по шагам от простого к сложному — или пройди инженерный путь по трекам. Нужна конкретная тема — <a href="pages/search.html">поиск</a> или <a href="ref/index.html">справочник</a>.</p>
      <div class="home-hero__stats">
        <span class="gc-tag">{len(core)} модулей в ядре</span>
        <span class="gc-tag" data-state="ok">написано {core_written}</span>
        <span class="gc-tag" data-state="caution">в работе {len(core) - core_written}</span>
      </div>
      <p class="gc-label gc-muted">Твой прогресс <span data-progress-label="{esc(','.join(all_published))}"></span></p>
      <div class="gc-progress" role="progressbar" aria-label="Твой прогресс по курсу" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" data-progress-of="{esc(','.join(all_published))}" style="--gc-value: 0%"></div>
      <p class="gc-muted home-hero__note">Прогресс хранится в этом браузере · <a href="pages/progress.html">подробная ведомость</a></p>
      <p class="ready-filter"><label class="gc-muted"><input type="checkbox" data-ready-only> Показывать только готовые модули</label></p>
    </section>

    <section class="choose" aria-labelledby="choose-title">
      <h2 class="gc-title" id="choose-title">Как учиться</h2>
      <p class="gc-muted">Пути по прошивкам независимы: можно идти по нескольким параллельно в своём темпе — у каждого свой прогресс и своя кнопка «Продолжить». Общие модули засчитываются во всех путях сразу.</p>
      <div class="gc-grid ref-grid">
{chr(10).join(render_path_card(p, model, base) for p in model["paths"])}
      </div>
      <a class="gc-card choose__tracks" href="#tracks">
        <p class="gc-label gc-muted">По навыкам</p>
        <strong>Инженерный путь: 5 треков от физики до своего кода</strong>
        <div class="gc-muted">Все прошивки вперемешку, по росту сложности. Для тех, кто хочет понимать, а не только настраивать.</div>
      </a>
      <a class="gc-card choose__tracks" href="projects/index.html">
        <p class="gc-label gc-muted">Практика в коде</p>
        <strong>Проекты: ПО для БАС — {len(model.get("projects", []))} программных проектов</strong>
        <div class="gc-muted">Веб-GCS, сервис логов, CI для флота, компоненты MAVLink, зрение в симуляторе. Каждый может заменить итоговый проект трека.</div>
      </a>
    </section>

    <h2 class="gc-title section-title" id="tracks">По навыкам: треки</h2>
    <nav class="home-toc" aria-label="Треки">
{toc}
    </nav>

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


def widget_scripts(content_html: str, base: str) -> str:
    """Script tags for widgets actually present in the rendered content."""
    names = sorted(set(re.findall(r"<uav-([a-z0-9-]+) class=\"widget\"", content_html)))
    if not names:
        return ""
    tags = [f'\n  <script src="{base}assets/widgets/plot.js" defer></script>']
    tags += [f'\n  <script src="{base}assets/widgets/{n}.js" defer></script>' for n in names]
    return "".join(tags)


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
    lab = m.get("lab")
    if isinstance(lab, dict):
        items = "".join(
            f'<li><label><input type="checkbox" data-check-id="{esc(m["id"])}:lab:{i}"><span>{esc(c)}</span></label></li>'
            for i, c in enumerate(lab.get("criteria", []))
        )
        blocks.append(
            f'<div class="gc-callout lab"><p class="gc-label gc-muted">Лабораторная</p><strong>{esc(lab["title"])}</strong>'
            f'<p class="gc-muted lab__hint">Сдано, когда отмечены все пункты:</p><ul class="gc-checklist">{items}</ul></div>'
        )
    elif lab:
        blocks.append(f'<div class="gc-callout"><strong>Лабораторная</strong><div>{esc(lab)}</div></div>')

    if planned:
        summary_html = ""
        content = (
            '<div class="gc-callout" data-state="caution"><strong>Модуль в разработке.</strong> '
            f'Цели и связи уже определены, текст пишется. План — в <a href="{ROADMAP_URL}">ROADMAP</a>.</div>'
        )
        done_toggle = ""
    else:
        summary_html, content = article_sections(m)
        if (TASKS_SRC / f"{m['id']}.json").is_file():
            content += (
                f'\n<h2>Задачи с числовым ответом</h2>\n<uav-tasks src="{base}tasks/{esc(m["id"])}.json" module="{esc(m["id"])}"></uav-tasks>'
            )
        if (QUIZ_SRC / f"{m['id']}.json").is_file():
            content += (
                f'\n<h2>Проверь себя</h2>\n<uav-quiz src="{base}quiz/{esc(m["id"])}.json" module="{esc(m["id"])}"></uav-quiz>'
            )
        done_toggle = (
            f'<div class="module-done"><gc-button variant="secondary" data-done-toggle="{esc(m["id"])}">'
            "Отметить как пройденный</gc-button></div>"
        )

    path_nav = []
    path_pagers = []
    for p in model["paths"]:
        if m["id"] in p["moduleIds"]:
            i = p["moduleIds"].index(m["id"])
            nxt_id = p["moduleIds"][i + 1] if i + 1 < len(p["moduleIds"]) else None
            prev_id = p["moduleIds"][i - 1] if i > 0 else None
            q = f"?path={esc(p['id'])}"
            nxt_html = f' → <a href="{esc(nxt_id)}.html{q}">{esc(model["modules"][nxt_id]["title"])}</a>' if nxt_id else " · последний шаг"
            path_nav.append(f'<li data-path-pos="{esc(p["id"])}"><a href="{base}path/{esc(p["id"])}.html">{esc(p["title"])}</a>: шаг {i + 1} из {len(p["moduleIds"])}{nxt_html}</li>')
            pg = []
            if prev_id:
                pg.append(f'<a class="gc-card pager__prev" href="{esc(prev_id)}.html{q}"><span class="gc-label gc-muted">Назад · путь {esc(p["title"])}</span><br>{esc(model["modules"][prev_id]["title"])}</a>')
            if nxt_id:
                pg.append(f'<a class="gc-card pager__next" href="{esc(nxt_id)}.html{q}"><span class="gc-label gc-muted">Дальше · шаг {i + 2} из {len(p["moduleIds"])}</span><br>{esc(model["modules"][nxt_id]["title"])}</a>')
            else:
                pg.append(f'<a class="gc-card pager__next" href="{base}path/{esc(p["id"])}.html"><span class="gc-label gc-muted">Путь пройден</span><br>К итоговым проектам пути {esc(p["title"])}</a>')
            path_pagers.append(f'<nav class="pager" aria-label="Соседние шаги пути {esc(p["title"])}" data-path-pager="{esc(p["id"])}" hidden>{"".join(pg)}</nav>')
    if path_nav:
        blocks.append(f'<div class="path-pos gc-muted"><span class="gc-label">В пути</span><ul>{"".join(path_nav)}</ul></div>')

    prev, nxt = neighbours(m, model)
    pager = []
    if prev:
        pager.append(f'<a class="gc-card pager__prev" href="{esc(prev["id"])}.html"><span class="gc-label gc-muted">Назад · трек</span><br>{esc(prev["title"])}</a>')
    if nxt:
        pager.append(f'<a class="gc-card pager__next" href="{esc(nxt["id"])}.html"><span class="gc-label gc-muted">Дальше · трек</span><br>{esc(nxt["title"])}</a>')
    pager_html = (f'<nav class="pager" aria-label="Соседние модули" data-track-pager>{"".join(pager)}</nav>' if pager else "") + "".join(path_pagers)
    related_html = render_related(m, model)

    lead = f'<p class="module-lead">{summary_html}</p>' if summary_html else ""
    body = f"""    <article class="module" data-module-page="{esc(m['id'])}">
      <p class="gc-breadcrumb">{''.join(crumbs)}</p>
      <h1 class="module-title">{esc(m['title'])}</h1>
      <div class="module-tags">{''.join(tags)}<span class="gc-tag" data-state="ok" data-done-badge hidden>ОСВОЕН</span></div>
      <p class="gc-muted module-score" data-module-score></p>
      {lead}
      {''.join(blocks)}
      <div class="gc-prose module-body">
{content}
      </div>
      {done_toggle}
      {related_html}
      {pager_html}
    </article>"""
    return layout(title=m["title"], base=base, body=body, active="course", description=" ".join(m.get("objectives", [])),
                  extra_head=widget_scripts(content if not planned else "", base))


# ---------------------------------------------------------------- capstone


def render_capstone(g: dict, model: dict) -> str:
    base = "../"
    c = g["capstone"]
    mods = [model["modules"][i] for i in g["moduleIds"]]
    prereq = "".join(
        f'<li><a href="{base}m/{esc(m["id"])}.html">{esc(m["title"])}</a>{" " + status_tag(m["status"]) if m["status"] == "planned" else ""}</li>'
        for m in mods
    )
    deliver = "".join(f"<li>{esc(d)}</li>" for d in c.get("deliverables", []))
    crit = "".join(
        f'<li><label><input type="checkbox" data-check-id="{esc(c["id"])}:cap:{i}"><span>{esc(x)}</span></label></li>'
        for i, x in enumerate(c.get("criteria", []))
    )
    rubric_rows = "".join(
        f'<tr><th scope="row">{esc(r["criterion"])}</th><td class="rubric__bad">{esc(r["bad"])}</td><td class="rubric__good">{esc(r["good"])}</td></tr>'
        for r in c.get("rubric", [])
    )
    rubric_html = (
        f'<h2>Рубрика: как отличить сделанное от сданного</h2>'
        f'<p class="gc-muted">Проверь свою работу по каждой строке. Если она ближе к левой колонке — проект ещё не готов.</p>'
        f'<div class="widget__table-wrap"><table class="rubric"><thead><tr><th>Критерий</th><th>Плохо</th><th>Хорошо</th></tr></thead><tbody>{rubric_rows}</tbody></table></div>'
        if rubric_rows else ""
    )
    body = f"""    <article class="module" data-module-page="{esc(c['id'])}">
      <p class="gc-breadcrumb"><a href="{base}index.html">Курс</a><a href="{base}index.html#track-{esc(g['id'])}">{esc(g['title'])}</a><span>Итоговый проект</span></p>
      <h1 class="module-title">{esc(c['title'])}</h1>
      <div class="module-tags"><span class="gc-tag">Итоговый проект трека {g['index']}</span><span class="gc-tag" data-state="ok" data-done-badge hidden>СДАН</span></div>
      <p class="module-lead">Результат: {esc(c['result'])}</p>
      <div class="gc-prose module-body">
        <h2>Что сдать</h2>
        <ul>{deliver}</ul>
        <h2>Критерии приёмки</h2>
        <p class="gc-muted">Проект сдан, когда выполнены все пункты. Отмечай по мере готовности:</p>
        <ul class="gc-checklist">{crit}</ul>
        {rubric_html}
        {project_alternatives(g, model, base)}
        <h2>Модули трека</h2>
        <ol>{prereq}</ol>
        <div class="gc-callout" data-state="caution"><strong>Безопасность.</strong> Всё, что можно сделать в SITL или без пропов, делается там. Реальный полёт — только после наземных тестов, с проверенным failsafe.</div>
      </div>
      <div class="module-done"><gc-button variant="secondary" data-done-toggle="{esc(c['id'])}" data-done-label="сданный" data-done-past="Сдан">Отметить как сданный</gc-button></div>
    </article>"""
    return layout(title=c["title"], base=base, body=body, active="course", description=c.get("result", ""))


# ---------------------------------------------------------------- project catalogue

PROJECT_STATUS = {"starter": ("есть стартер", "ok"), "planned": ("описание", "")}


def project_alternatives(g: dict, model: dict, base: str) -> str:
    alts = [p for p in model.get("projects", []) if p.get("capstoneFor") == g["id"]]
    if not alts:
        return ""
    items = "".join(f'<li><a href="{base}projects/{esc(p["id"])}.html">Проект {p["num"]}: {esc(p["title"])}</a></li>' for p in alts)
    return (f'<h2>Программная альтернатива</h2><p class="gc-muted">Итоговый проект трека можно заменить проектом '
            f'из каталога «ПО для БАС» — с теми же требованиями к сдаче: критерии, автотесты, README.</p><ul>{items}</ul>')


def project_card(p: dict, base: str) -> str:
    label, state = PROJECT_STATUS.get(p.get("status", "planned"), ("", ""))
    stack = " · ".join(p.get("stack", [])[:3])
    return (f'<a class="gc-card capstone-card" href="{base}projects/{esc(p["id"])}.html" data-module-id="{esc(p["id"])}">'
            f'<p class="gc-label gc-muted">Проект {p["num"]} · {esc(p.get("level", ""))} · ~{p.get("hours", "?")} ч</p>'
            f'<strong>{esc(p["title"])}</strong><div class="gc-muted">{esc(stack)}</div>'
            f'<div class="gc-card__meta"><span class="gc-tag" data-state="{state}">{esc(label)}</span>'
            f'<span class="gc-tag" data-state="ok" data-done-badge hidden>СДАН</span></div></a>')


def render_projects_index(model: dict) -> str:
    base = "../"
    groups = {g["id"]: g for g in model["groups"]}
    cards = "".join(project_card(p, base) for p in sorted(model["projects"], key=lambda p: p["num"]))
    body = f"""    <p class="gc-breadcrumb"><a href="{base}index.html">Курс</a><span>Проекты</span></p>
    <h1 class="gc-display">Проекты: ПО для БАС</h1>
    <p class="module-lead">Двенадцать программных проектов от веб-GCS до точной посадки по маркеру. Каждый — с архитектурной схемой, этапами, критериями приёмки и автотестом; там, где написан стартер, он лежит в <code>examples/</code> репозитория. Проект может заменить итоговый проект своего трека.</p>
    <div class="gc-prose module-body">
      <p class="gc-muted">Как работать: возьмите проект, пройдите модули из его списка, сделайте этапы по порядку, сдайте по критериям. Код — в собственном репозитории с README и тестами; «работает у меня» не засчитывается.</p>
    </div>
    <div class="gc-grid ref-grid">{cards}</div>"""
    return layout(title="Проекты", base=base, body=body, active="course",
                  description="Каталог программных проектов курса: веб-GCS, сервис логов, CI для флота, компоненты MAVLink, компьютерное зрение.")


def render_project(p: dict, model: dict) -> str:
    base = "../"
    g = next((g for g in model["groups"] if g["id"] == p.get("capstoneFor")), None)
    label, state = PROJECT_STATUS.get(p.get("status", "planned"), ("", ""))
    mods = "".join(f'<li><a href="{base}m/{esc(i)}.html">{esc(model["modules"][i]["title"])}</a></li>'
                   for i in p.get("modules", []) if i in model["modules"])
    stack = "".join(f"<li>{esc(x)}</li>" for x in p.get("stack", []))
    checks = p.get("checks") or []
    miles = "".join(f"<li>{esc(x)}" + (f'<br><span class="gc-muted">Проверка:</span> <code>{esc(checks[i])}</code>' if i < len(checks) and checks[i]
                    else ('<br><span class="gc-muted">Проверка: демонстрация в отчёте</span>' if checks else "")) + "</li>"
                    for i, x in enumerate(p.get("milestones", [])))
    rubric = model.get("project_rubric") or []
    rub_html = ""
    if rubric:
        names = ("Засчитано", "Хорошо", "Отлично")
        items = "".join(f"<li><strong>{esc(r['criterion'])}</strong><ul>" +
                        "".join(f"<li><em>{names[k]}:</em> {esc(l)}</li>" for k, l in enumerate(r["levels"])) + "</ul></li>" for r in rubric)
        rub_html = ('<h2>Оценка</h2><p class="gc-muted">Сдан — когда выполнены все критерии приёмки. Уровень работы — по критериям ниже; каждый уровень включает предыдущий.</p>'
                    f"<ul>{items}</ul>")
    stretch = "".join(f"<li>{esc(x)}</li>" for x in p.get("stretch", []))
    stretch_html = f"<h2>Задания «на отлично»</h2><ul>{stretch}</ul>" if stretch else ""
    deliver = "".join(f"<li>{esc(x)}</li>" for x in p.get("deliverables", []))
    crit = "".join(f'<li><label><input type="checkbox" data-check-id="{esc(p["id"])}:cap:{i}"><span>{esc(x)}</span></label></li>'
                   for i, x in enumerate(p.get("acceptance", [])))
    repo = "https://github.com/irreligious86/UAV-Education/tree/main/"
    starter = (f'<p>Стартер: <a href="{repo}{esc(p["starter"])}" target="_blank" rel="noopener noreferrer"><code>{esc(p["starter"])}</code></a> — '
               f'клонируйте и начинайте с его README.</p>' if p.get("starter") else
               '<p class="gc-muted">Стартера пока нет: проект начинается с пустого репозитория по этапам ниже.</p>')
    replaces = (f'<p>Может заменить итоговый проект трека «<a href="{base}cap/{esc(g["capstone"]["id"])}.html">{esc(g["title"])}</a>».</p>'
                if g and g.get("capstone") else "")
    diagram = render_diagram(p["diagram"], f"Архитектура проекта {p['num']}.") if p.get("diagram") else ""
    body = f"""    <article class="module" data-module-page="{esc(p['id'])}">
      <p class="gc-breadcrumb"><a href="{base}index.html">Курс</a><a href="index.html">Проекты</a><span>Проект {p['num']}</span></p>
      <h1 class="module-title">{esc(p['title'])}</h1>
      <div class="module-tags"><span class="gc-tag">Проект {p['num']}</span><span class="gc-tag">{esc(p.get('level', ''))}</span><span class="gc-tag">~{p.get('hours', '?')} ч</span><span class="gc-tag" data-state="{state}">{esc(label)}</span><span class="gc-tag" data-state="ok" data-done-badge hidden>СДАН</span></div>
      <p class="module-lead">{esc(p['summary'])}</p>
      <div class="gc-prose module-body">
        {diagram}
        <h2>Стек</h2>
        <ul>{stack}</ul>
        {starter}
        {replaces}
        <h2>Этапы</h2>
        <ol>{miles}</ol>
        <h2>Критерии приёмки</h2>
        <p class="gc-muted">Проект сдан, когда выполнены все пункты. Отмечайте по мере готовности:</p>
        <ul class="gc-checklist">{crit}</ul>
        <h2>Автопроверка</h2>
        <p>{esc(p.get('autotest', ''))}</p>
        {rub_html}
        {stretch_html}
        <h2>Что сдать</h2>
        <ul>{deliver}</ul>
        <h2>Нужные модули</h2>
        <ol>{mods}</ol>
        <div class="gc-callout" data-state="caution"><strong>Безопасность.</strong> Всё, что управляет аппаратом, сначала проходит тесты и SITL. Реальный полёт — только с проверенным failsafe и пилотом, готовым забрать управление.</div>
      </div>
      <div class="module-done"><gc-button variant="secondary" data-done-toggle="{esc(p['id'])}" data-done-label="сданный" data-done-past="Сдан">Отметить как сданный</gc-button></div>
    </article>"""
    return layout(title=p["title"], base=base, body=body, active="course", description=p["summary"][:200])


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
    if model.get("projects"):
        pages = f'<a class="gc-card" href="../projects/index.html"><strong>Проекты: ПО для БАС</strong></a>' + pages
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


def parse_diagnostics(block: str) -> list[tuple[str, list[str]]]:
    """Return [(symptom, [detail lines])] from a ## diagnostics block."""
    out: list[tuple[str, list[str]]] = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line.startswith("- "):
            continue
        text = line[2:].strip()
        if text.startswith("**Симптом:**"):
            out.append((text.replace("**Симптом:**", "").strip(), []))
        elif out:
            out[-1][1].append(text)
    return out


def render_fails(model: dict) -> str:
    """Journal of failures: every diagnostics entry from every published module, grouped by track."""
    base = "../"
    sections = []
    toc_ids = []
    total = 0
    for g in model["groups"]:
        rows = []
        for mid in g["moduleIds"]:
            m = model["modules"][mid]
            if m["status"] != "published":
                continue
            raw = (ROOT / m["articleMeta"]["sourceFile"]).read_text(encoding="utf-8")
            entries = parse_diagnostics(extract_section(strip_front_matter(raw), "diagnostics"))
            for symptom, details in entries:
                cause = next((d for d in details if d.lower().startswith("возможная причина")), "")
                fix = next((d for d in details if d.lower().startswith("что сделать")), "")
                evidence = next((d for d in details if d.lower().startswith("в логе") or d.lower().startswith("что видно")), "")
                consequence = next((d for d in details if d.lower().startswith("последствия")), "")
                cause = cause.split(":", 1)[1].strip() if ":" in cause else cause
                fix = fix.split(":", 1)[1].strip() if ":" in fix else fix
                evidence = evidence.split(":", 1)[1].strip() if ":" in evidence else evidence
                consequence = consequence.split(":", 1)[1].strip() if ":" in consequence else consequence
                sym = format_inline(symptom[:1].upper() + symptom[1:])
                extra = ""
                if evidence:
                    extra += f'<p><span class="gc-muted">Что видно в логе/приборе:</span> {format_inline(evidence)}</p>'
                if consequence:
                    extra += f'<p><span class="gc-muted">Последствия:</span> {format_inline(consequence)}</p>'
                rows.append(
                    f'<div class="gc-card fail"><strong class="fail__symptom">{sym}</strong>'
                    f'<p><span class="gc-muted">Причина:</span> {format_inline(cause)}</p>{extra}'
                    f'<p><span class="gc-muted">Исправление:</span> {format_inline(fix)}</p>'
                    f'<a class="gc-tag" href="{base}m/{esc(mid)}.html">{esc(m["title"])}</a></div>'
                )
                total += 1
        if rows:
            toc_ids.append(g)
            sections.append(
                f'<h2 id="fails-{esc(g["id"])}">{esc(g["title"])}</h2>'
                f'<div class="fails__list">{"".join(rows)}</div>'
            )
    toc = "".join(f'<a class="gc-tag" href="#fails-{esc(g["id"])}">{esc(g["title"])}</a>' for g in toc_ids)
    body = f"""    <p class="gc-breadcrumb"><a href="../ref/index.html">Справочник</a><span>Журнал ошибок и фейлов</span></p>
    <h1 class="gc-display">Журнал ошибок и фейлов</h1>
    <p class="gc-muted">{total} случаев из разделов «Диагностика» всех написанных модулей, по схеме симптом → причина → что видно в логе или приборе → последствия → исправление. Собирается автоматически при сборке сайта; чтобы добавить кейс — допиши диагностику в модуль. Разборы реальных инцидентов — в модуле <a href="../m/ops-case-studies.html">«Разбор реальных аварий»</a>.</p>
    <div class="home-toc">{toc}</div>
    <div class="fails">{"".join(sections)}</div>"""
    return layout(title="Журнал фейлов", base=base, body=body, active="fails")


def render_formulas(model: dict) -> str:
    """Reference of formulas and CLI commands from data/formulas.json, grouped by section."""
    base = "../"
    data = json.loads((ROOT / "data" / "formulas.json").read_text(encoding="utf-8"))
    sections = []
    toc = []
    for s in data["sections"]:
        rows = []
        for item in s["items"]:
            mod = model["modules"].get(item.get("module"))
            link = f'<a class="gc-tag" href="{base}m/{esc(mod["id"])}.html">{esc(mod["title"])}</a>' if mod else ""
            rows.append(
                f'<div class="gc-card formula"><strong>{esc(item["name"])}</strong>'
                f'<pre class="formula__expr"><code>{esc(item["expr"])}</code></pre>'
                f'<p class="gc-muted">{format_inline(item["note"])}</p>{link}</div>'
            )
        sid = s["id"]
        toc.append(f'<a class="gc-tag" href="#f-{esc(sid)}">{esc(s["title"])}</a>')
        sections.append(f'<h2 id="f-{esc(sid)}">{esc(s["title"])}</h2><div class="fails__list">{"".join(rows)}</div>')
    body = f"""    <p class="gc-breadcrumb"><a href="../ref/index.html">Справочник</a><span>Формулы и команды</span></p>
    <h1 class="gc-display">Формулы и команды</h1>
    <p class="gc-muted">Шпаргалка инженера: формулы с единицами и CLI-команды прошивок, каждая со ссылкой на модуль, где она объясняется. Источник — <code>data/formulas.json</code>.</p>
    <div class="home-toc">{"".join(toc)}</div>
    <div class="fails">{"".join(sections)}</div>"""
    return layout(title="Формулы и команды", base=base, body=body, active="ref")


def render_glossary(model: dict) -> str:
    base = "../"
    data = json.loads((ROOT / "data" / "glossary.json").read_text(encoding="utf-8"))
    terms = sorted(data["terms"], key=lambda t: t["term"].lower())
    cards = []
    for t in terms:
        mod = model["modules"].get(t.get("module"))
        link = f'<a class="gc-tag" href="{base}m/{esc(mod["id"])}.html">{esc(mod["title"])}</a>' if mod else ""
        cards.append(f'<div class="gc-card glossary-entry"><h3>{esc(t["term"])}</h3><p>{format_inline(t["def"])}</p>{link}</div>')
    body = f"""    <p class="gc-breadcrumb"><a href="../ref/index.html">Справочник</a><span>Глоссарий</span></p>
    <h1 class="gc-display">Глоссарий</h1>
    <p class="gc-muted">{len(terms)} терминов. Каждый ведёт к модулю, где объясняется подробно.</p>
    <div class="gc-grid ref-grid glossary">{"".join(cards)}</div>"""
    return layout(title="Глоссарий", base=base, body=body, active="glossary")


def render_page(name: str, title: str) -> str:
    base = "../"
    inner = (ROOT / "content" / "pages" / f"{name}.html").read_text(encoding="utf-8")
    active = name if name in ("glossary", "fails") else "ref"
    body = f"""    <p class="gc-breadcrumb"><a href="../ref/index.html">Справочник</a><span>{esc(title)}</span></p>
    <div class="gc-prose legacy-page">
{inner}
    </div>"""
    return layout(title=title, base=base, body=body, active=active)


# ---------------------------------------------------------------- search index


def strip_md(text: str) -> str:
    """Plain text for the search index: keep code and identifiers (rpm_filter_min_hz), drop markup."""
    text = re.sub(r"[#*`>|\[\]()]", " ", text)
    return " ".join(text.split())


def search_index(model: dict) -> list[dict]:
    docs = []
    for m in model["modules"].values():
        if m["status"] != "published":
            continue
        raw = (ROOT / m["articleMeta"]["sourceFile"]).read_text(encoding="utf-8")
        body = strip_front_matter(raw)
        summary = " ".join(extract_section(body, "summary").split())
        headings = " ".join(h.strip() for h in re.findall(r"^###\s+(.+)$", body, flags=re.M))
        docs.append({
            "id": m["id"], "type": "module", "title": m["title"], "url": f"m/{m['id']}.html",
            "group": m.get("groupTitle") or "", "level": m["level"],
            "summary": summary[:300], "headings": headings,
            "text": strip_md(body)[:6000],
            "tags": " ".join(str(t) for t in (m["articleMeta"].get("tags") or [])),
        })
    gl = json.loads((ROOT / "data" / "glossary.json").read_text(encoding="utf-8"))
    for t in gl["terms"]:
        docs.append({"id": "g:" + t["term"], "type": "term", "title": t["term"], "url": "pages/glossary.html",
                     "group": "Глоссарий", "level": "", "summary": t["def"], "headings": "", "text": "", "tags": ""})
    for g in model["groups"]:
        c = g.get("capstone")
        if c:
            docs.append({"id": c["id"], "type": "capstone", "title": c["title"], "url": f"cap/{c['id']}.html",
                         "group": g["title"], "level": "", "summary": c.get("result", ""), "headings": "",
                         "text": " ".join(c.get("deliverables", []) + c.get("criteria", [])), "tags": ""})
    for p in model.get("projects", []):
        docs.append({"id": p["id"], "type": "capstone", "title": f"Проект {p['num']}: {p['title']}", "url": f"projects/{p['id']}.html",
                     "group": "Проекты", "level": p.get("level", ""), "summary": p["summary"], "headings": "",
                     "text": " ".join(p.get("stack", []) + p.get("milestones", []) + p.get("acceptance", [])), "tags": ""})
    return docs


def render_search() -> str:
    base = "../"
    body = """    <h1 class="gc-display">Поиск</h1>
    <form class="search-form" role="search" onsubmit="return false">
      <label class="gc-label gc-muted" for="q">Модули, термины, симптомы</label>
      <input id="q" class="search-input" type="search" autocomplete="off" placeholder="например: rpm_filter_min_hz, failsafe, инверсия">
    </form>
    <p class="gc-muted" id="search-status">Начни вводить запрос.</p>
    <div id="search-results" class="search-results" aria-live="polite"></div>"""
    return layout(title="Поиск", base=base, body=body, active="search",
                  extra_head=f'\n  <script src="{base}assets/search.js" defer></script>')


# ---------------------------------------------------------------- grading


def grading_meta(model: dict) -> dict:
    mods = []
    for m in model["modules"].values():
        if m["status"] != "published":
            continue
        lab = m.get("lab")
        mods.append({"id": m["id"], "quiz": (QUIZ_SRC / f"{m['id']}.json").is_file(),
                     "tasks": task_count(m["id"]),
                     "lab": len(lab.get("criteria", [])) if isinstance(lab, dict) else 0})
    caps = [{"id": g["capstone"]["id"], "criteria": len(g["capstone"].get("criteria", [])), "group": g["id"]}
            for g in model["groups"] if g.get("capstone")]
    caps += [{"id": p["id"], "criteria": len(p.get("acceptance", [])), "group": p.get("capstoneFor"), "project": True}
             for p in model.get("projects", [])]
    return {"version": 2, "pass": 80, "weights": {"quiz": 40, "lab": 60, "withTasks": {"quiz": 30, "tasks": 30, "lab": 40}},
            "modules": mods, "capstones": caps}


# ---------------------------------------------------------------- numeric tasks


def task_count(module_id: str) -> int:
    p = TASKS_SRC / f"{module_id}.json"
    if not p.is_file():
        return 0
    return len(json.loads(p.read_text(encoding="utf-8")).get("tasks", []))


def _fmt_num(v) -> str:
    if isinstance(v, str):
        return v
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.4g}".rstrip("0").rstrip(".")


def build_task_variants(bank: dict) -> dict:
    """Expand a parametrised bank into concrete variants with precomputed answers.
    Deterministic (seeded by module/task id) so the published JSON is stable between builds."""
    import math
    import random
    out = {"module": bank["module"], "tasks": []}
    for t in bank["tasks"]:
        rng = random.Random(f"{bank['module']}/{t['id']}")
        variants = []
        seen: set[tuple] = set()
        tries = 0
        while len(variants) < TASK_VARIANTS and tries < 200:
            tries += 1
            vals = {}
            for name, spec in t.get("params", {}).items():
                if isinstance(spec, list):
                    vals[name] = rng.choice(spec)
                else:
                    step = spec.get("step", 1)
                    n = int(round((spec["max"] - spec["min"]) / step))
                    vals[name] = round(spec["min"] + step * rng.randint(0, n), 6)
            key = tuple(sorted(vals.items()))
            if key in seen:
                continue
            seen.add(key)
            ans = eval(t["answer"], {"__builtins__": {"min": min, "max": max, "abs": abs, "round": round}, "math": math}, dict(vals))  # authored by us, not user input
            if not math.isfinite(ans):
                continue
            statement = re.sub(r"\{([a-z0-9_]+)\}", lambda mm: _fmt_num(vals[mm.group(1)]), t["statement"])
            variants.append({"values": vals, "statement": format_inline(statement), "answer": round(float(ans), 6)})
        if not variants:
            raise SystemExit(f"task {bank['module']}/{t['id']}: no finite variants")
        out["tasks"].append({"id": t["id"], "title": t["title"], "unit": t.get("unit", ""), "tol": t.get("tol", 0.03),
                             "abs": t.get("abs", 0), "solution": format_inline(t.get("solution", "")), "variants": variants})
    return out


def render_progress(model: dict) -> str:
    """Student transcript: every path/track with module-level scores. Filled by progress.js."""
    base = "../"
    def table(title, ids, anchor):
        rows = "".join(
            f'<tr data-row="{esc(i)}"><td><a href="{base}m/{esc(i)}.html">{esc(model["modules"][i]["title"])}</a></td>'
            f'<td class="num" data-cell="quiz">—</td><td class="num" data-cell="lab">—</td><td class="num" data-cell="score">—</td><td data-cell="status"></td></tr>'
            for i in ids if model["modules"][i]["status"] == "published"
        )
        return f"""      <section class="gc-panel" id="{esc(anchor)}">
        <h2 class="gc-title">{esc(title)}</h2>
        <p class="gc-muted" data-group-summary="{esc(','.join(i for i in ids if model['modules'][i]['status'] == 'published'))}"></p>
        <div class="table-wrap"><table class="progress-table"><thead><tr><th>Модуль</th><th>Квиз</th><th>Лаба</th><th>Балл</th><th>Статус</th></tr></thead><tbody>{rows}</tbody></table></div>
      </section>"""
    paths = "".join(table(f"Путь: {p['title']}", p["moduleIds"], f"path-{p['id']}") for p in model["paths"])
    tracks = "".join(table(f"Трек {g['index']}: {g['title']}", g["moduleIds"], f"track-{g['id']}") for g in model["groups"] if g["kind"] == "track")
    caps = "".join(
        f'<li data-cap="{esc(g["capstone"]["id"])}"><a href="{base}cap/{esc(g["capstone"]["id"])}.html">{esc(g["capstone"]["title"])}</a> <span class="gc-tag" data-cap-status></span></li>'
        for g in model["groups"] if g.get("capstone")
    )
    projs = "".join(
        f'<li data-cap="{esc(pr["id"])}"><a href="{base}projects/{esc(pr["id"])}.html">Проект {pr["num"]}: {esc(pr["title"])}</a> <span class="gc-tag" data-cap-status></span></li>'
        for pr in sorted(model.get("projects", []), key=lambda x: x["num"])
    )
    projs_html = (f'<p class="gc-label gc-muted">Проекты «ПО для БАС»</p><ul class="progress-caps">{projs}</ul>' if projs else "")
    all_pub = [m["id"] for m in model["modules"].values() if m["status"] == "published"]
    body = f"""    <h1 class="gc-display">Мой прогресс</h1>
    <p class="gc-muted">Балл модуля = 40% квиз (лучшая попытка) + 60% лабораторная; в модулях с задачами — 30% квиз + 30% задачи + 40% лабораторная. «Освоен» — квиз ≥ 80%, все задачи решены и все пункты лабораторной. Ручная отметка видна как «отмечен», это честно другое.</p>
    <section class="gc-panel">
      <p class="gc-label gc-muted">Весь курс</p>
      <p class="progress-headline" data-group-summary="{esc(','.join(all_pub))}"></p>
      <div class="gc-progress" role="progressbar" aria-label="Общий балл" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" data-progress-of="{esc(','.join(all_pub))}" style="--gc-value: 0%"></div>
      <p class="gc-label gc-muted">Итоговые проекты</p>
      <ul class="progress-caps">{caps}</ul>
      {projs_html}
    </section>
    <h2 class="gc-title section-title">По прошивке</h2>
{paths}
    <h2 class="gc-title section-title">По навыкам</h2>
{tracks}
    <section class="gc-panel">
      <p class="gc-label gc-muted">Данные</p>
      <p class="gc-muted">Прогресс хранится в этом браузере. Экспортируй, чтобы перенести на другое устройство или показать наставнику.</p>
      <div class="progress-actions">
        <gc-button variant="secondary" data-export>Скачать JSON</gc-button>
        <label class="gc-tag" style="cursor:pointer">Импорт JSON <input type="file" accept="application/json" data-import hidden></label>
        <gc-button variant="secondary" data-reset>Сбросить всё</gc-button>
      </div>
    </section>
    <section class="gc-panel">
      <p class="gc-label gc-muted">Результаты грейдеров</p>
      <p class="gc-muted">Грейдеры курса (<code>examples/sitl-pymavlink/check_lab_log.py</code>, <code>examples/blackbox-grader/check_bf_log.py</code>) с флагом <code>--json result.json</code> пишут файл результата. Загрузи его — пункты лабораторных, которые грейдер действительно проверил и которые прошли, отметятся сами; в таблице они помечены «⚙». Это самопроверка: файл можно подделать, он показывает, что грейдер запускали, а не что кто-то принял работу.</p>
      <div class="progress-actions">
        <label class="gc-tag" style="cursor:pointer">Импорт результата грейдера <input type="file" accept="application/json" data-lab-import hidden></label>
        <span class="gc-muted" data-lab-msg aria-live="polite"></span>
      </div>
      <ul class="progress-labs" data-lab-results></ul>
    </section>"""
    return layout(title="Мой прогресс", base=base, body=body, active="progress",
                  extra_head=f'\n  <script src="{base}assets/progress-page.js" defer></script>')


# ---------------------------------------------------------------- static API


def api_payload(model: dict) -> dict:
    """Shape of GET /api/v1/curriculum. Keep stable: a future server returns the same JSON."""
    def mod(m):
        return {
            "id": m["id"], "title": m["title"], "level": m["level"], "hours": m.get("hours"),
            "status": m["status"], "prerequisites": m.get("prerequisites", []),
            "objectives": m.get("objectives", []), "lab": m.get("lab"), "url": f"m/{m['id']}.html",
        }
    return {
        "version": 1,
        "paths": [{"id": p["id"], "title": p["title"], "goal": p["goal"],
                   "stages": [{"title": st["title"], "modules": st["modules"]} for st in p["stages"]],
                   "url": f"path/{p['id']}.html"} for p in model["paths"]],
        "groups": [
            {"id": g["id"], "kind": g["kind"], "title": g["title"], "level": g.get("level"),
             "goal": g.get("goal"), "capstone": g.get("capstone"),
             "modules": [mod(model["modules"][i]) for i in g["moduleIds"]]}
            for g in model["groups"]
        ],
    }


# ---------------------------------------------------------------- main


def write_pwa() -> None:
    """Service worker with a versioned precache of the whole static site (~4 MB) and a web manifest.
    The version is a hash of the precached files' contents, so every publish that changes anything
    produces a new cache and old caches are dropped on activate."""
    import hashlib
    files: list[str] = ["index.html", "manifest.webmanifest"]
    for d in GENERATED_DIRS:
        for f in sorted((ROOT / d).rglob("*")):
            if f.is_file():
                files.append(f.relative_to(ROOT).as_posix())
    for f in sorted((ROOT / "assets").rglob("*")):
        if f.is_file():
            files.append(f.relative_to(ROOT).as_posix())
    for f in sorted((ROOT / GC).glob("*")):
        if f.is_file():
            files.append(f.relative_to(ROOT).as_posix())
    h = hashlib.sha1()
    for rel in files:
        fp = ROOT / rel
        if rel != "manifest.webmanifest" and fp.exists():
            h.update(rel.encode()); h.update(fp.read_bytes())
    version = h.hexdigest()[:12]
    sw = f"""/* Generated by scripts/build_site.py — do not edit. Cache version {version}. */
const VERSION = "uav-student-{version}";
const PRECACHE = {json.dumps(files, ensure_ascii=False)};
const scopeUrl = new URL(self.registration.scope);
const toUrl = (rel) => new URL(rel, scopeUrl).href;

self.addEventListener("install", (event) => {{
  event.waitUntil((async () => {{
    const cache = await caches.open(VERSION);
    // add in chunks and tolerate individual failures (a missing file must not block offline mode)
    const chunk = 25;
    for (let i = 0; i < PRECACHE.length; i += chunk) {{
      await Promise.all(PRECACHE.slice(i, i + chunk).map(async (rel) => {{
        try {{ await cache.add(new Request(toUrl(rel), {{ cache: "reload" }})); }} catch (e) {{ /* skip */ }}
      }}));
    }}
    await self.skipWaiting();
  }})());
}});

self.addEventListener("activate", (event) => {{
  event.waitUntil((async () => {{
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k.startsWith("uav-student-") && k !== VERSION).map((k) => caches.delete(k)));
    await self.clients.claim();
    const clients = await self.clients.matchAll({{ type: "window" }});
    clients.forEach((c) => c.postMessage({{ type: "offline-ready", version: VERSION, files: PRECACHE.length }}));
  }})());
}});

self.addEventListener("fetch", (event) => {{
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== scopeUrl.origin) return;              // CDN/external: leave to the network
  event.respondWith((async () => {{
    const cache = await caches.open(VERSION);
    const cached = await cache.match(req, {{ ignoreSearch: true }});
    if (cached) {{
      // stale-while-revalidate: serve cache, refresh in background
      event.waitUntil(fetch(req).then((res) => {{ if (res && res.ok) cache.put(req, res.clone()); }}).catch(() => {{}}));
      return cached;
    }}
    try {{
      const res = await fetch(req);
      if (res && res.ok && url.pathname.startsWith(scopeUrl.pathname)) cache.put(req, res.clone());
      return res;
    }} catch (e) {{
      const fallback = await cache.match(toUrl("index.html"));
      return fallback || new Response("Offline", {{ status: 503 }});
    }}
  }})());
}});
"""
    write(ROOT / "sw.js", sw)
    manifest = {
        "name": SITE_TITLE, "short_name": "UAV Student", "lang": "ru", "start_url": "./index.html",
        "scope": "./", "display": "standalone", "background_color": "#0b0f14", "theme_color": "#0b0f14",
        "description": "Инженерный курс по БПЛА: от физики полёта до своих прошивок и бортовых компьютеров.",
        "icons": [{"src": "assets/favicon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"}],
    }
    write(ROOT / "manifest.webmanifest", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


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
    for p in model["paths"]:
        write(ROOT / "path" / f"{p['id']}.html", render_path(p, model))
    for g in model["groups"]:
        if g.get("capstone"):
            write(ROOT / "cap" / f"{g['capstone']['id']}.html", render_capstone(g, model))
    if model.get("projects"):
        write(ROOT / "projects" / "index.html", render_projects_index(model))
        for pr in model["projects"]:
            write(ROOT / "projects" / f"{pr['id']}.html", render_project(pr, model))
    write(ROOT / "ref" / "index.html", render_ref_index(model))
    for s in model["stacks"]:
        write(ROOT / "ref" / f"{s['key']}.html", render_ref_stack(s, model))
    for name, title in PAGES.items():
        if name == "fails":
            write(ROOT / "pages" / "fails.html", render_fails(model))
        elif name == "formulas":
            write(ROOT / "pages" / "formulas.html", render_formulas(model))
        elif name == "glossary":
            write(ROOT / "pages" / "glossary.html", render_glossary(model))
        else:
            write(ROOT / "pages" / f"{name}.html", render_page(name, title))
    if QUIZ_SRC.is_dir():
        for q in QUIZ_SRC.glob("*.json"):
            write(ROOT / "quiz" / q.name, q.read_text(encoding="utf-8"))
    if TASKS_SRC.is_dir():
        for t in sorted(TASKS_SRC.glob("*.json")):
            bank = json.loads(t.read_text(encoding="utf-8"))
            write(ROOT / "tasks" / t.name, json.dumps(build_task_variants(bank), ensure_ascii=False) + "\n")
    write(ROOT / "pages" / "search.html", render_search())
    write(ROOT / "pages" / "progress.html", render_progress(model))
    write(ROOT / "api" / "v1" / "grading.json", json.dumps(grading_meta(model), ensure_ascii=False, indent=2) + "\n")
    write(ROOT / "api" / "v1" / "search.json", json.dumps(search_index(model), ensure_ascii=False) + "\n")
    write(ROOT / "api" / "v1" / "curriculum.json", json.dumps(api_payload(model), ensure_ascii=False, indent=2) + "\n")

    write_pwa()

    n_pub = sum(1 for m in model["modules"].values() if m["status"] == "published")
    n_quiz = len(list(QUIZ_SRC.glob("*.json"))) if QUIZ_SRC.is_dir() else 0
    n_tasks = sum(task_count(p.stem) for p in TASKS_SRC.glob("*.json")) if TASKS_SRC.is_dir() else 0
    print(f"built: {len(model['modules'])} module pages ({n_pub} written, {n_quiz} with quiz, {n_tasks} numeric tasks), {len(model['stacks'])} stacks, {len(PAGES)} pages")


if __name__ == "__main__":
    main()
