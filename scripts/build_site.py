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

import i18n  # noqa: E402
from i18n import _, tr_html, up  # noqa: E402
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

PAGES = {  # titles are translated with _() where used
    "glossary": "Глоссарий",
    "fails": "Журнал ошибок и фейлов",
    "formulas": "Формулы и команды",
    "checklists": "Быстрые чек-листы",
    "setup-cards": "Карточки настройки с нуля",
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


# ---------------------------------------------------------------- languages (scripts/i18n.py, docs/I18N.md)

# Field names of the diagnostics blocks in every course language (translated modules keep the structure).
SYMPTOM_KEYS = ("**Симптом:**", "**Symptom:**", "Симптом:", "Symptom:")
FIELD_KEYS = {
    "cause": ("возможная причина", "можлива причина", "possible cause"),
    "fix": ("что сделать", "что проверить", "що зробити", "що перевірити", "what to do", "what to check", "fix"),
    "evidence": ("в логе", "что видно", "у лозі", "у логу", "в логу", "у журналі", "що видно", "in the log", "what you see", "evidence"),
    "consequence": ("последствия", "наслідки", "consequences"),
}
TRANSLATION_STATE: dict[str, dict[str, str]] = {}   # lang -> module id -> "ok" | "stale" | "missing"


def localized_text(src: Path) -> str:
    """The current language's translation of a source file if it exists, else the source."""
    if i18n.lang() != i18n.SOURCE:
        t = i18n.translated_path(src)
        if t.is_file():
            return t.read_text(encoding="utf-8")
    return src.read_text(encoding="utf-8")


def module_source(m: dict) -> str:
    """Markdown of a module in the current language; untranslated modules fall back to the source."""
    src = ROOT / m["articleMeta"]["sourceFile"]
    raw = src.read_text(encoding="utf-8")
    if i18n.lang() == i18n.SOURCE:
        return raw
    t = i18n.translated_path(src)
    state = TRANSLATION_STATE.setdefault(i18n.lang(), {})
    if not t.is_file():
        state[m["id"]] = "missing"
        return raw
    text = t.read_text(encoding="utf-8")
    fm = parse_front_matter(text) or ""
    h = re.search(r"^source_hash:\s*([0-9a-f]+)", fm, flags=re.M)
    state[m["id"]] = "ok" if h and h.group(1) == i18n.source_hash(raw) else "stale"
    return text


def translation_notice(m: dict) -> str:
    st = TRANSLATION_STATE.get(i18n.lang(), {}).get(m["id"])
    if st == "missing":
        src = i18n.BY_CODE[i18n.SOURCE]["name"]
        return (f'<div class="gc-callout" data-state="caution" data-untranslated><strong>{_("Модуль ещё не переведён.")}</strong> '
                f'{_("Ниже — оригинал ({lang}). Прогресс и оценки общие для всех языков.", lang=src)}</div>\n')
    if st == "stale":
        return (f'<div class="gc-callout" data-state="info" data-stale-translation>{_("Оригинал модуля обновлялся после перевода — часть текста может отставать.")}</div>\n')
    return ""


def load_glossary() -> dict:
    """Glossary in the current language (terms and definitions go through the data catalog)."""
    return i18n.tr_data(json.loads((ROOT / "data" / "glossary.json").read_text(encoding="utf-8")))


def lang_head(a: str) -> str:
    """Placeholder for the hreflang alternates and the early redirect; filled by write(), which knows the page path."""
    return "\n  <!--LANG-ALTERNATES-->"


LANG_REDIRECT = ("<script>/* go to the visitor's chosen language before anything paints (assets/i18n.js) */"
                 "(function(){try{var c=localStorage.getItem('uav-lang'),h=document.documentElement.getAttribute('data-lang');"
                 "if(!c||c===h||/[?&]lang=keep\\b/.test(location.search))return;"
                 "var l=document.querySelector('link[rel=alternate][hreflang=\"'+c+'\"]');"
                 "if(l)location.replace(l.href+location.search+location.hash)}catch(e){}})();</script>")


def alternates_for(rel: str) -> dict[str, str]:
    """Relative URL of the same page in every language, as seen from the current language's page `rel`."""
    depth = rel.count("/")
    to_root = "../" * depth + up()
    return {l["code"]: to_root + (l["dir"] + "/" if l["dir"] else "") + rel for l in i18n.LANGS}


def i18n_script(a: str) -> str:
    cat = "" if i18n.lang() == i18n.SOURCE else f'\n  <script src="{a}assets/i18n/{i18n.lang()}.js"></script>'
    return f'{cat}\n  <script src="{a}assets/i18n.js"></script>'


def lang_switch() -> str:
    """Language picker in the header; hrefs are filled by write(). assets/i18n.js remembers the choice."""
    links = "".join(
        f'<a class="gc-tag" href="#lang-{l["code"]}" data-lang-to="{l["code"]}" hreflang="{l["htmlLang"]}" lang="{l["htmlLang"]}" title="{esc(l["name"])}"'
        + (' aria-current="true" data-state="ok"' if l["code"] == i18n.lang() else "") + f'>{esc(l["short"])}</a>'
        for l in i18n.LANGS)
    return f'\n      <nav class="lang-switch" aria-label="{_("Язык")}">{links}</nav>'


# ---------------------------------------------------------------- data model


def load_curriculum() -> dict:
    return json.loads(CURRICULUM_PATH.read_text(encoding="utf-8"))


def build_model() -> dict:
    """Join manifest (articles by stack) and curriculum (tracks) into one module table."""
    manifest = i18n.tr_data(load_manifest())
    curriculum = i18n.tr_data(load_curriculum())

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
    pdata = i18n.tr_data(json.loads(PROJECTS_SRC.read_text(encoding="utf-8"))) if PROJECTS_SRC.is_file() else {}
    projects = pdata.get("projects", [])
    return {"stacks": stacks, "modules": modules, "groups": groups, "curriculum": curriculum, "paths": paths,
            "projects": projects, "project_rubric": pdata.get("rubric", [])}


# ---------------------------------------------------------------- layout


def layout(*, title: str, base: str, body: str, active: str, description: str = "", extra_head: str = "") -> str:
    nav_items = [
        ("course", f"{base}index.html", _("Курс")),
        ("ref", f"{base}ref/index.html", _("Справочник")),
        ("glossary", f"{base}pages/glossary.html", _("Глоссарий")),
        ("fails", f"{base}pages/fails.html", _("Фейлы")),
        ("search", f"{base}pages/search.html", _("Поиск")),
        ("progress", f"{base}pages/progress.html", _("Мой прогресс")),
    ]
    current = ' aria-current="page"'
    nav = "\n".join(
        f'        <a href="{href}"{current if key == active else ""}>{label}</a>'
        for key, href, label in nav_items
    )
    full_title = SITE_TITLE if title == SITE_TITLE else f"{title} — {SITE_TITLE}"
    a = base + up()   # shared assets live at the repository root, above the language tree
    L = i18n.BY_CODE[i18n.lang()]
    return f"""<!doctype html>
<html lang="{L['htmlLang']}" data-theme="dark" data-lang="{L['code']}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(full_title)}</title>
  <meta name="description" content="{esc(description or _('Инженерный курс по БПЛА: от физики полёта до своих прошивок и бортовых компьютеров.'))}">
  <link rel="icon" href="{a}assets/favicon.svg" type="image/svg+xml">
  <link rel="manifest" href="{a}manifest.webmanifest">
  <meta name="theme-color" content="#0b0f14">{lang_head(a)}
  <link rel="stylesheet" href="{a}{GC}/ground-control.css">
  <link rel="stylesheet" href="{a}assets/site.css">
  <script src="{a}{GC}/ground-control.js" defer></script>{i18n_script(a)}
  <script src="{a}assets/progress-store.js" defer></script>
  <script src="{a}assets/backend-config.js" defer></script>
  <script src="{a}assets/account.js" defer></script>
  <script src="{a}assets/grading.js" defer></script>
  <script src="{a}assets/app.js" defer></script>
  <script src="{a}assets/uav-quiz.js" defer></script>
  <script src="{a}assets/uav-tasks.js" defer></script>
  <script src="{a}assets/offline.js" defer></script>{extra_head}
</head>
<body class="gc-root" data-base="{base}" data-root="{a}">
  <header class="site-header">
    <div class="gc-container site-header__inner">
      <a class="site-brand" href="{base}index.html"><span class="site-brand__mark" aria-hidden="true">◆</span> {SITE_TITLE}</a>
      <nav class="gc-nav" aria-label="{_('Разделы сайта')}">
{nav}
      </nav>{lang_switch()}
    </div>
  </header>
  <main class="gc-container site-main">
{body}
  </main>
  <footer class="gc-container site-footer gc-muted">
    <p>{_('Открытый курс')} · <a href="{REPO_URL}">{_('исходники на GitHub')}</a> · <a href="{ROADMAP_URL}">{_('план развития')}</a> · <a href="{a}curriculum/curriculum.html">{_('для разработчика')}</a> · CC BY-NC-SA 4.0</p>
  </footer>
</body>
</html>
"""


def level_tag(level: str) -> str:
    label = LEVEL_LABELS.get(level, level)
    return f'<span class="gc-tag" title="{esc(label)}">{esc(level)}</span>'


def status_tag(status: str) -> str:
    if status == "planned":
        return f'<span class="gc-tag" data-state="caution">{_("СКОРО")}</span>'
    return ""


def hours_text(h) -> str:
    if h is None:
        return ""
    h = float(h)
    return _("~{h} ч", h=int(h) if h.is_integer() else h)


# ---------------------------------------------------------------- home: course map


def module_row(m: dict, n: int, base: str, path_id: str | None = None, shared: bool = False) -> str:
    planned = m["status"] == "planned"
    tags = [level_tag(m["level"])]
    if shared:
        tags.append(f'<span class="gc-tag" title="{_("Общий модуль: засчитывается во всех путях, где он есть")}">{_("общий")}</span>')
    q = f"?path={esc(path_id)}" if path_id else ""
    if m.get("hours"):
        tags.append(f'<span class="gc-tag">{hours_text(m["hours"])}</span>')
    if planned:
        tags.append(status_tag("planned"))
    tags.append(f'<span class="gc-tag" data-state="ok" data-done-badge hidden>{_("ПРОЙДЕН")}</span>')
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
        _("Трек {n}", n=g["index"]) + f' · {esc(g.get("level", ""))} · {esc(g.get("audience", ""))}'
        if g["kind"] == "track"
        else _("Электив")
    )
    rows = "\n".join(module_row(m, i, base) for i, m in enumerate(mods, start=1))
    capstone = ""
    if g.get("capstone"):
        c = g["capstone"]
        capstone = f"""
        <a class="gc-card capstone-card" href="{base}cap/{esc(c['id'])}.html" data-module-id="{esc(c['id'])}">
          <p class="gc-label gc-muted">{_("Итоговый проект")}</p>
          <strong>{esc(c['title'])}</strong>
          <div class="gc-muted">{_("Результат:")} {esc(c['result'])}</div>
          <div class="gc-card__meta"><span class="gc-tag" data-state="ok" data-done-badge hidden>{_("СДАН")}</span></div>
        </a>"""
    goal = f'\n        <p class="track__goal">{esc(g["goal"])}</p>' if g.get("goal") else ""
    written = sum(1 for m in mods if m["status"] == "published")
    return f"""      <section class="track gc-panel" id="track-{esc(g['id'])}" aria-labelledby="track-{esc(g['id'])}-title">
        <p class="gc-label gc-muted">{kicker}</p>
        <h2 class="gc-title" id="track-{esc(g['id'])}-title">{esc(g['title'])}</h2>{goal}
        <div class="track__stats gc-muted">
          <span>{_("{n} модулей", n=len(mods))} · {hours_text(total_h)} · {_("написано {n}", n=written)}</span>
          <span data-progress-label="{esc(','.join(published_ids))}"></span>
        </div>
        <div class="gc-progress" role="progressbar" aria-label="{_("Пройдено в треке «{t}»", t=esc(g['title']))}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" data-progress-of="{esc(','.join(published_ids))}" style="--gc-value: 0%"></div>
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
          <p class="gc-label gc-muted">{_("По прошивке")}</p>
          <strong>{esc(p['title'])}</strong>
          <div class="gc-muted">{esc(p['subtitle'])}</div>
          <div class="path-card__continue gc-muted" data-path-continue="{esc(p['id'])}" data-path-steps="{path_steps_attr(p, model)}" hidden></div>
          <div class="gc-card__meta"><span class="gc-tag">{_("{n} шагов", n=len(mods))}</span><span class="gc-tag" data-state="ok">{_("написано {n}", n=len(pub))}</span><span class="gc-tag" data-progress-label="{esc(','.join(pub))}"></span></div>
          <div class="gc-progress" role="progressbar" aria-label="{_("Прогресс по пути {t}", t=esc(p['title']))}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" data-progress-of="{esc(','.join(pub))}" style="--gc-value: 0%"></div>
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
        <p class="gc-label gc-muted">{_("Этап")}</p>
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
            caps.append(f'<a class="gc-card capstone-card" href="{base}cap/{esc(cid)}.html" data-module-id="{esc(cid)}"><p class="gc-label gc-muted">{_("Итоговый проект")}</p><strong>{esc(c["title"])}</strong><div class="gc-muted">{esc(c["result"])}</div><div class="gc-card__meta"><span class="gc-tag" data-state="ok" data-done-badge hidden>{_("СДАН")}</span></div></a>')
    caps_html = f'<h2 class="gc-title section-title">{_("Итоговые проекты")}</h2>{"".join(caps)}' if caps else ""
    body = f"""    <p class="gc-breadcrumb"><a href="{base}index.html">{_("Курс")}</a><span>{_("Путь: {t}", t=esc(p['title']))}</span></p>
    <section class="home-hero">
      <h1 class="gc-display">{esc(p['title'])}</h1>
      <p class="home-hero__lead">{esc(p['goal'])}</p>
      <div class="home-hero__stats"><span class="gc-tag">{_("{n} шагов", n=len(mods))}</span><span class="gc-tag" data-state="ok">{_("написано {n}", n=len(pub))}</span><span class="gc-tag" data-state="caution">{_("в работе {n}", n=len(mods) - len(pub))}</span></div>
      <p class="gc-label gc-muted">{_("Твой прогресс")} <span data-progress-label="{esc(','.join(pub))}"></span></p>
      <div class="gc-progress" role="progressbar" aria-label="{_("Прогресс по пути")}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" data-progress-of="{esc(','.join(pub))}" style="--gc-value: 0%"></div>
      <p class="ready-filter"><label class="gc-muted"><input type="checkbox" data-ready-only> {_("Показывать только готовые модули")}</label></p>
      <p class="path-continue"><a class="gc-card" data-path-continue="{esc(p['id'])}" data-path-steps="{path_steps_attr(p, model)}" hidden></a></p>
      <p class="gc-muted home-hero__note">{_("Иди по порядку: каждый шаг опирается на предыдущие. Модули с тегом «общий» входят и в другие пути — пройденный один раз, такой модуль засчитан везде. Открывай уроки отсюда: тогда кнопки «назад/дальше» ведут по шагам именно этого пути.")}</p>
    </section>
{chr(10).join(stages)}
    {caps_html}"""
    return layout(title=_("Путь {t}", t=p['title']), base=base, body=body, active="course", description=p["goal"])


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
      <h1 class="gc-display">{_("Инженерный курс по БПЛА")}</h1>
      <p class="home-hero__lead">{_("От «почему он летает» до настройки по логам, автономных миссий и своего кода на борту.")}
      {_('Выбери прошивку и иди по шагам от простого к сложному — или пройди инженерный путь по трекам. Нужна конкретная тема — <a href="pages/search.html">поиск</a> или <a href="ref/index.html">справочник</a>.')}</p>
      <div class="home-hero__stats">
        <span class="gc-tag">{_("{n} модулей в ядре", n=len(core))}</span>
        <span class="gc-tag" data-state="ok">{_("написано {n}", n=core_written)}</span>
        <span class="gc-tag" data-state="caution">{_("в работе {n}", n=len(core) - core_written)}</span>
      </div>
      <p class="gc-label gc-muted">{_("Твой прогресс")} <span data-progress-label="{esc(','.join(all_published))}"></span></p>
      <div class="gc-progress" role="progressbar" aria-label="{_("Твой прогресс по курсу")}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" data-progress-of="{esc(','.join(all_published))}" style="--gc-value: 0%"></div>
      <p class="gc-muted home-hero__note">{_("Прогресс хранится в этом браузере")} · <a href="pages/progress.html">{_("подробная ведомость")}</a></p>
      <p class="ready-filter"><label class="gc-muted"><input type="checkbox" data-ready-only> {_("Показывать только готовые модули")}</label></p>
    </section>

    <section class="choose" aria-labelledby="choose-title">
      <h2 class="gc-title" id="choose-title">{_("Как учиться")}</h2>
      <p class="gc-muted">{_("Пути по прошивкам независимы: можно идти по нескольким параллельно в своём темпе — у каждого свой прогресс и своя кнопка «Продолжить». Общие модули засчитываются во всех путях сразу.")}</p>
      <div class="gc-grid ref-grid">
{chr(10).join(render_path_card(p, model, base) for p in model["paths"])}
      </div>
      <a class="gc-card choose__tracks" href="#tracks">
        <p class="gc-label gc-muted">{_("По навыкам")}</p>
        <strong>{_("Инженерный путь: 5 треков от физики до своего кода")}</strong>
        <div class="gc-muted">{_("Все прошивки вперемешку, по росту сложности. Для тех, кто хочет понимать, а не только настраивать.")}</div>
      </a>
      <a class="gc-card choose__tracks" href="projects/index.html">
        <p class="gc-label gc-muted">{_("Практика в коде")}</p>
        <strong>{_("Проекты: ПО для БАС — {n} программных проектов", n=len(model.get("projects", [])))}</strong>
        <div class="gc-muted">{_("Веб-GCS, сервис логов, CI для флота, компоненты MAVLink, зрение в симуляторе. Каждый может заменить итоговый проект трека.")}</div>
      </a>
    </section>

    <h2 class="gc-title section-title" id="tracks">{_("По навыкам: треки")}</h2>
    <nav class="home-toc" aria-label="{_("Треки")}">
{toc}
    </nav>

{chr(10).join(render_group(g, model, base) for g in tracks)}

    <h2 class="gc-title section-title">{_("Элективы")}</h2>
    <p class="gc-muted">{_("Необязательные ветки: другие прошивки на тех же принципах.")}</p>
{chr(10).join(render_group(g, model, base) for g in electives)}

    <section class="gc-panel">
      <p class="gc-label gc-muted">{_("Дальше")}</p>
      <p>{_("Итоговый проект-электив:")} <strong>{esc(cap['title'] if cap else '')}</strong>.</p>
      <p class="gc-muted">{_("Темы в бэклоге:")} {esc(backlog)}.</p>
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
    return f'<section class="related" aria-label="{_("Смежные модули")}"><p class="gc-label gc-muted">{_("Смежные модули")}</p><div class="gc-grid ref-grid">{links}</div></section>'


def article_sections(m: dict) -> tuple[str, str]:
    """Return (summary_html, body_html) for a published article."""
    art = m["articleMeta"]
    raw = module_source(m)
    fm = parse_front_matter(raw)
    body = strip_front_matter(raw)
    summary = extract_section(body, "summary")
    parts = []
    for key, heading in (("theory", _("Теория")), ("practice", _("Практика"))):
        block = extract_section(body, key)
        if block:
            parts.append(f"<h2>{heading}</h2>\n{block_to_paragraphs(block)}")
    diag = extract_section(body, "diagnostics")
    if diag:
        parts.append(f"<h2>{_('Диагностика')}</h2>\n{diagnostics_to_html(diag)}")
    notes = extract_section(body, "notes")
    if notes:
        parts.append(f"<h2>{_('Заметки')}</h2>\n{block_to_paragraphs(notes)}")
    checklist = render_checklist(extract_section(body, "checklist"), m["id"])
    if checklist:
        parts.append(f"<h2>{_('Чек-лист')}</h2>\n{checklist}")
    refs = render_references(extract_section(body, "references"), fm)
    if refs:
        parts.append(f"<h2>{_('Источники')}</h2>\n{refs}")
    summary_html = format_inline(" ".join(summary.split())) if summary else ""
    return summary_html, "\n\n".join(parts)


def widget_scripts(content_html: str, base: str) -> str:
    """Script tags for widgets actually present in the rendered content."""
    names = sorted(set(re.findall(r"<uav-([a-z0-9-]+) class=\"widget\"", content_html)))
    if not names:
        return ""
    tags = [f'\n  <script src="{base}{up()}assets/widgets/plot.js" defer></script>']
    tags += [f'\n  <script src="{base}{up()}assets/widgets/{n}.js" defer></script>' for n in names]
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

    crumbs = [f'<a href="{base}index.html">{_("Курс")}</a>']
    if m["group"]:
        crumbs.append(f'<a href="{base}index.html#track-{esc(m["group"])}">{esc(m["groupTitle"])}</a>')
    elif art:
        crumbs.append(f'<a href="{base}ref/{esc(art["stack"])}.html">{esc(art["stackTitle"])}</a>')
    crumbs.append(f"<span>{esc(m['title'])}</span>")

    tags = [f'<span class="gc-tag" title="{_("Уровень")}">{esc(_(LEVEL_LABELS.get(m["level"], m["level"])))}</span>']
    if art.get("readingTime") and not planned:
        tags.append(f'<span class="gc-tag">{_("чтение {t}", t=esc(_(str(art["readingTime"]))))}</span>')
    if m.get("hours"):
        tags.append(f'<span class="gc-tag">{_("учёба {t}", t=hours_text(m["hours"]))}</span>')
    if art.get("firmware"):
        tags.append(f'<span class="gc-tag">{esc(str(art["firmware"]))}</span>')
    if planned:
        tags.append(status_tag("planned"))

    blocks = []
    if m.get("objectives"):
        lis = "".join(f"<li>{esc(o)}</li>" for o in m["objectives"])
        blocks.append(f'<div class="gc-callout" data-state="ok"><strong>{_("После модуля ты умеешь")}</strong><ul>{lis}</ul></div>')
    prereq = [model["modules"][p] for p in m.get("prerequisites", []) if p in model["modules"]]
    if prereq:
        links = ", ".join(f'<a href="{esc(p["id"])}.html">{esc(p["title"])}</a>' for p in prereq)
        blocks.append(f'<p class="gc-muted">{_("Перед этим модулем:")} {links}</p>')
    lab = m.get("lab")
    if isinstance(lab, dict):
        items = "".join(
            f'<li><label><input type="checkbox" data-check-id="{esc(m["id"])}:lab:{i}"><span>{esc(c)}</span></label></li>'
            for i, c in enumerate(lab.get("criteria", []))
        )
        blocks.append(
            f'<div class="gc-callout lab"><p class="gc-label gc-muted">{_("Лабораторная")}</p><strong>{esc(lab["title"])}</strong>'
            f'<p class="gc-muted lab__hint">{_("Сдано, когда отмечены все пункты:")}</p><ul class="gc-checklist">{items}</ul></div>'
        )
    elif lab:
        blocks.append(f'<div class="gc-callout"><strong>{_("Лабораторная")}</strong><div>{esc(lab)}</div></div>')

    if planned:
        summary_html = ""
        content = (
            f'<div class="gc-callout" data-state="caution"><strong>{_("Модуль в разработке.")}</strong> '
            + _('Цели и связи уже определены, текст пишется. План — в <a href="{url}">ROADMAP</a>.', url=ROADMAP_URL) + '</div>'
        )
        done_toggle = ""
    else:
        summary_html, content = article_sections(m)
        content = translation_notice(m) + content
        if (TASKS_SRC / f"{m['id']}.json").is_file():
            content += (
                f'\n<h2>{_("Задачи с числовым ответом")}</h2>\n<uav-tasks src="{base}tasks/{esc(m["id"])}.json" module="{esc(m["id"])}"></uav-tasks>'
            )
        if (QUIZ_SRC / f"{m['id']}.json").is_file():
            content += (
                f'\n<h2>{_("Проверь себя")}</h2>\n<uav-quiz src="{base}quiz/{esc(m["id"])}.json" module="{esc(m["id"])}"></uav-quiz>'
            )
        done_toggle = (
            f'<div class="module-done"><gc-button variant="secondary" data-done-toggle="{esc(m["id"])}">'
            f'{_("Отметить как пройденный")}</gc-button></div>'
        )

    path_nav = []
    path_pagers = []
    for p in model["paths"]:
        if m["id"] in p["moduleIds"]:
            i = p["moduleIds"].index(m["id"])
            nxt_id = p["moduleIds"][i + 1] if i + 1 < len(p["moduleIds"]) else None
            prev_id = p["moduleIds"][i - 1] if i > 0 else None
            q = f"?path={esc(p['id'])}"
            nxt_html = f' → <a href="{esc(nxt_id)}.html{q}">{esc(model["modules"][nxt_id]["title"])}</a>' if nxt_id else " · " + _("последний шаг")
            path_nav.append(f'<li data-path-pos="{esc(p["id"])}"><a href="{base}path/{esc(p["id"])}.html">{esc(p["title"])}</a>: {_("шаг {i} из {n}", i=i + 1, n=len(p["moduleIds"]))}{nxt_html}</li>')
            pg = []
            if prev_id:
                pg.append(f'<a class="gc-card pager__prev" href="{esc(prev_id)}.html{q}"><span class="gc-label gc-muted">{_("Назад · путь {t}", t=esc(p["title"]))}</span><br>{esc(model["modules"][prev_id]["title"])}</a>')
            if nxt_id:
                pg.append(f'<a class="gc-card pager__next" href="{esc(nxt_id)}.html{q}"><span class="gc-label gc-muted">{_("Дальше · шаг {i} из {n}", i=i + 2, n=len(p["moduleIds"]))}</span><br>{esc(model["modules"][nxt_id]["title"])}</a>')
            else:
                pg.append(f'<a class="gc-card pager__next" href="{base}path/{esc(p["id"])}.html"><span class="gc-label gc-muted">{_("Путь пройден")}</span><br>{_("К итоговым проектам пути {t}", t=esc(p["title"]))}</a>')
            path_pagers.append(f'<nav class="pager" aria-label="{_("Соседние шаги пути {t}", t=esc(p["title"]))}" data-path-pager="{esc(p["id"])}" hidden>{"".join(pg)}</nav>')
    if path_nav:
        blocks.append(f'<div class="path-pos gc-muted"><span class="gc-label">{_("В пути")}</span><ul>{"".join(path_nav)}</ul></div>')

    prev, nxt = neighbours(m, model)
    pager = []
    if prev:
        pager.append(f'<a class="gc-card pager__prev" href="{esc(prev["id"])}.html"><span class="gc-label gc-muted">{_("Назад · трек")}</span><br>{esc(prev["title"])}</a>')
    if nxt:
        pager.append(f'<a class="gc-card pager__next" href="{esc(nxt["id"])}.html"><span class="gc-label gc-muted">{_("Дальше · трек")}</span><br>{esc(nxt["title"])}</a>')
    pager_html = (f'<nav class="pager" aria-label="{_("Соседние модули")}" data-track-pager>{"".join(pager)}</nav>' if pager else "") + "".join(path_pagers)
    related_html = render_related(m, model)

    lead = f'<p class="module-lead">{summary_html}</p>' if summary_html else ""
    body = f"""    <article class="module" data-module-page="{esc(m['id'])}">
      <p class="gc-breadcrumb">{''.join(crumbs)}</p>
      <h1 class="module-title">{esc(m['title'])}</h1>
      <div class="module-tags">{''.join(tags)}<span class="gc-tag" data-state="ok" data-done-badge hidden>{_("ОСВОЕН")}</span></div>
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
        f'<h2>{_("Рубрика: как отличить сделанное от сданного")}</h2>'
        f'<p class="gc-muted">{_("Проверь свою работу по каждой строке. Если она ближе к левой колонке — проект ещё не готов.")}</p>'
        f'<div class="widget__table-wrap"><table class="rubric"><thead><tr><th>{_("Критерий")}</th><th>{_("Плохо")}</th><th>{_("Хорошо")}</th></tr></thead><tbody>{rubric_rows}</tbody></table></div>'
        if rubric_rows else ""
    )
    body = f"""    <article class="module" data-module-page="{esc(c['id'])}">
      <p class="gc-breadcrumb"><a href="{base}index.html">{_("Курс")}</a><a href="{base}index.html#track-{esc(g['id'])}">{esc(g['title'])}</a><span>{_("Итоговый проект")}</span></p>
      <h1 class="module-title">{esc(c['title'])}</h1>
      <div class="module-tags"><span class="gc-tag">{_("Итоговый проект трека {n}", n=g['index'])}</span><span class="gc-tag" data-state="ok" data-done-badge hidden>{_("СДАН")}</span></div>
      <p class="module-lead">{_("Результат:")} {esc(c['result'])}</p>
      <div class="gc-prose module-body">
        <h2>{_("Что сдать")}</h2>
        <ul>{deliver}</ul>
        <h2>{_("Критерии приёмки")}</h2>
        <p class="gc-muted">{_("Проект сдан, когда выполнены все пункты. Отмечай по мере готовности:")}</p>
        <ul class="gc-checklist">{crit}</ul>
        {rubric_html}
        {project_alternatives(g, model, base)}
        <h2>{_("Модули трека")}</h2>
        <ol>{prereq}</ol>
        <div class="gc-callout" data-state="caution"><strong>{_("Безопасность.")}</strong> {_("Всё, что можно сделать в SITL или без пропов, делается там. Реальный полёт — только после наземных тестов, с проверенным failsafe.")}</div>
      </div>
      <div class="module-done"><gc-button variant="secondary" data-done-toggle="{esc(c['id'])}" data-done-label="{_("сданный")}" data-done-past="{_("Сдан")}">{_("Отметить как сданный")}</gc-button></div>
    </article>"""
    return layout(title=c["title"], base=base, body=body, active="course", description=c.get("result", ""))


# ---------------------------------------------------------------- project catalogue

PROJECT_STATUS = {"starter": ("есть стартер", "ok"), "planned": ("описание", "")}   # labels go through _()


def project_alternatives(g: dict, model: dict, base: str) -> str:
    alts = [p for p in model.get("projects", []) if p.get("capstoneFor") == g["id"]]
    if not alts:
        return ""
    items = "".join(f'<li><a href="{base}projects/{esc(p["id"])}.html">{_("Проект {n}", n=p["num"])}: {esc(p["title"])}</a></li>' for p in alts)
    return (f'<h2>{_("Программная альтернатива")}</h2><p class="gc-muted">'
            + _("Итоговый проект трека можно заменить проектом из каталога «ПО для БАС» — с теми же требованиями к сдаче: критерии, автотесты, README.")
            + f'</p><ul>{items}</ul>')


def project_card(p: dict, base: str) -> str:
    label, state = PROJECT_STATUS.get(p.get("status", "planned"), ("", ""))
    label = _(label) if label else label
    stack = " · ".join(p.get("stack", [])[:3])
    return (f'<a class="gc-card capstone-card" href="{base}projects/{esc(p["id"])}.html" data-module-id="{esc(p["id"])}">'
            f'<p class="gc-label gc-muted">{_("Проект {n}", n=p["num"])} · {esc(p.get("level", ""))} · {_("~{h} ч", h=p.get("hours", "?"))}</p>'
            f'<strong>{esc(p["title"])}</strong><div class="gc-muted">{esc(stack)}</div>'
            f'<div class="gc-card__meta"><span class="gc-tag" data-state="{state}">{esc(label)}</span>'
            f'<span class="gc-tag" data-state="ok" data-done-badge hidden>{_("СДАН")}</span></div></a>')


def render_projects_index(model: dict) -> str:
    base = "../"
    groups = {g["id"]: g for g in model["groups"]}
    cards = "".join(project_card(p, base) for p in sorted(model["projects"], key=lambda p: p["num"]))
    body = f"""    <p class="gc-breadcrumb"><a href="{base}index.html">{_("Курс")}</a><span>{_("Проекты")}</span></p>
    <h1 class="gc-display">{_("Проекты: ПО для БАС")}</h1>
    <p class="module-lead">{_("Двенадцать программных проектов от веб-GCS до точной посадки по маркеру. Каждый — с архитектурной схемой, этапами, критериями приёмки и автотестом; там, где написан стартер, он лежит в <code>examples/</code> репозитория. Проект может заменить итоговый проект своего трека.")}</p>
    <div class="gc-prose module-body">
      <p class="gc-muted">{_("Как работать: возьмите проект, пройдите модули из его списка, сделайте этапы по порядку, сдайте по критериям. Код — в собственном репозитории с README и тестами; «работает у меня» не засчитывается.")}</p>
    </div>
    <div class="gc-grid ref-grid">{cards}</div>"""
    return layout(title=_("Проекты"), base=base, body=body, active="course",
                  description=_("Каталог программных проектов курса: веб-GCS, сервис логов, CI для флота, компоненты MAVLink, компьютерное зрение."))


def render_project(p: dict, model: dict) -> str:
    base = "../"
    g = next((g for g in model["groups"] if g["id"] == p.get("capstoneFor")), None)
    label, state = PROJECT_STATUS.get(p.get("status", "planned"), ("", ""))
    label = _(label) if label else label
    mods = "".join(f'<li><a href="{base}m/{esc(i)}.html">{esc(model["modules"][i]["title"])}</a></li>'
                   for i in p.get("modules", []) if i in model["modules"])
    stack = "".join(f"<li>{esc(x)}</li>" for x in p.get("stack", []))
    checks = p.get("checks") or []
    miles = "".join(f"<li>{esc(x)}" + (f'<br><span class="gc-muted">{_("Проверка:")}</span> <code>{esc(checks[i])}</code>' if i < len(checks) and checks[i]
                    else (f'<br><span class="gc-muted">{_("Проверка: демонстрация в отчёте")}</span>' if checks else "")) + "</li>"
                    for i, x in enumerate(p.get("milestones", [])))
    rubric = model.get("project_rubric") or []
    rub_html = ""
    if rubric:
        names = (_("Засчитано"), _("Хорошо"), _("Отлично"))
        items = "".join(f"<li><strong>{esc(r['criterion'])}</strong><ul>" +
                        "".join(f"<li><em>{names[k]}:</em> {esc(l)}</li>" for k, l in enumerate(r["levels"])) + "</ul></li>" for r in rubric)
        rub_html = (f'<h2>{_("Оценка")}</h2><p class="gc-muted">{_("Сдан — когда выполнены все критерии приёмки. Уровень работы — по критериям ниже; каждый уровень включает предыдущий.")}</p>'
                    f"<ul>{items}</ul>")
    stretch = "".join(f"<li>{esc(x)}</li>" for x in p.get("stretch", []))
    stretch_html = f"<h2>{_('Задания «на отлично»')}</h2><ul>{stretch}</ul>" if stretch else ""
    deliver = "".join(f"<li>{esc(x)}</li>" for x in p.get("deliverables", []))
    crit = "".join(f'<li><label><input type="checkbox" data-check-id="{esc(p["id"])}:cap:{i}"><span>{esc(x)}</span></label></li>'
                   for i, x in enumerate(p.get("acceptance", [])))
    repo = "https://github.com/irreligious86/UAV-Education/tree/main/"
    starter = (f'<p>{_("Стартер:")} <a href="{repo}{esc(p["starter"])}" target="_blank" rel="noopener noreferrer"><code>{esc(p["starter"])}</code></a> — '
               f'{_("клонируйте и начинайте с его README.")}</p>' if p.get("starter") else
               f'<p class="gc-muted">{_("Стартера пока нет: проект начинается с пустого репозитория по этапам ниже.")}</p>')
    replaces = (f'<p>{_("Может заменить итоговый проект трека «{link}».", link=f"""<a href="{base}cap/{esc(g["capstone"]["id"])}.html">{esc(g["title"])}</a>""")}</p>'
                if g and g.get("capstone") else "")
    diagram = render_diagram(p["diagram"], _("Архитектура проекта {n}.", n=p['num'])) if p.get("diagram") else ""
    body = f"""    <article class="module" data-module-page="{esc(p['id'])}">
      <p class="gc-breadcrumb"><a href="{base}index.html">{_("Курс")}</a><a href="index.html">{_("Проекты")}</a><span>{_("Проект {n}", n=p['num'])}</span></p>
      <h1 class="module-title">{esc(p['title'])}</h1>
      <div class="module-tags"><span class="gc-tag">{_("Проект {n}", n=p['num'])}</span><span class="gc-tag">{esc(p.get('level', ''))}</span><span class="gc-tag">{_("~{h} ч", h=p.get('hours', '?'))}</span><span class="gc-tag" data-state="{state}">{esc(label)}</span><span class="gc-tag" data-state="ok" data-done-badge hidden>{_("СДАН")}</span></div>
      <p class="module-lead">{esc(p['summary'])}</p>
      <div class="gc-prose module-body">
        {diagram}
        <h2>{_("Стек")}</h2>
        <ul>{stack}</ul>
        {starter}
        {replaces}
        <h2>{_("Этапы")}</h2>
        <ol>{miles}</ol>
        <h2>{_("Критерии приёмки")}</h2>
        <p class="gc-muted">{_("Проект сдан, когда выполнены все пункты. Отмечайте по мере готовности:")}</p>
        <ul class="gc-checklist">{crit}</ul>
        <h2>{_("Автопроверка")}</h2>
        <p>{esc(p.get('autotest', ''))}</p>
        {rub_html}
        {stretch_html}
        <h2>{_("Что сдать")}</h2>
        <ul>{deliver}</ul>
        <h2>{_("Нужные модули")}</h2>
        <ol>{mods}</ol>
        <div class="gc-callout" data-state="caution"><strong>{_("Безопасность.")}</strong> {_("Всё, что управляет аппаратом, сначала проходит тесты и SITL. Реальный полёт — только с проверенным failsafe и пилотом, готовым забрать управление.")}</div>
      </div>
      <div class="module-done"><gc-button variant="secondary" data-done-toggle="{esc(p['id'])}" data-done-label="{_("сданный")}" data-done-past="{_("Сдан")}">{_("Отметить как сданный")}</gc-button></div>
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
            f'<div class="gc-card__meta"><span class="gc-tag" data-state="ok">{_("написано {n}", n=done)}</span>'
            f'<span class="gc-tag">{_("всего {n}", n=len(mods))}</span></div></a>'
        )
    pages = "".join(f'<a class="gc-card" href="../pages/{k}.html"><strong>{esc(_(v))}</strong></a>' for k, v in PAGES.items())
    if model.get("projects"):
        pages = f'<a class="gc-card" href="../projects/index.html"><strong>{_("Проекты: ПО для БАС")}</strong></a>' + pages
    body = f"""    <h1 class="gc-display">{_("Справочник")}</h1>
    <p class="gc-muted">{_("Те же модули, что в курсе, но сгруппированные по прошивкам и стекам.")}</p>
    <div class="gc-grid ref-grid">{''.join(cards)}</div>
    <h2 class="gc-title section-title">{_("Материалы")}</h2>
    <div class="gc-grid ref-grid">{pages}</div>"""
    return layout(title=_("Справочник"), base=base, body=body, active="ref")


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
        where = f'<span class="gc-tag">{_("трек: {t}", t=esc(m["groupTitle"]))}</span>' if m["group"] else ""
        pending = ' data-state="pending"' if planned else ""
        cards.append(
            f'<a class="gc-card" href="../m/{esc(m["id"])}.html"{pending} data-module-id="{esc(m["id"])}">'
            f'<strong>{esc(m["title"])}</strong><div class="gc-card__meta">{level_tag(m["level"])}{status_tag(m["status"])}{where}'
            f'<span class="gc-tag" data-state="ok" data-done-badge hidden>{_("ПРОЙДЕН")}</span></div></a>'
        )
    body = f"""    <p class="gc-breadcrumb"><a href="index.html">{_("Справочник")}</a><span>{esc(stack['title'])}</span></p>
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
        sym = next((k for k in SYMPTOM_KEYS if text.startswith(k)), None)
        if sym:
            out.append((text.replace(sym, "", 1).strip(), []))
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
            raw = module_source(m)
            entries = parse_diagnostics(extract_section(strip_front_matter(raw), "diagnostics"))
            for symptom, details in entries:
                cause = next((d for d in details if d.lower().startswith(FIELD_KEYS["cause"])), "")
                fix = next((d for d in details if d.lower().startswith(FIELD_KEYS["fix"])), "")
                evidence = next((d for d in details if d.lower().startswith(FIELD_KEYS["evidence"])), "")
                consequence = next((d for d in details if d.lower().startswith(FIELD_KEYS["consequence"])), "")
                cause = cause.split(":", 1)[1].strip() if ":" in cause else cause
                fix = fix.split(":", 1)[1].strip() if ":" in fix else fix
                evidence = evidence.split(":", 1)[1].strip() if ":" in evidence else evidence
                consequence = consequence.split(":", 1)[1].strip() if ":" in consequence else consequence
                sym = format_inline(symptom[:1].upper() + symptom[1:])
                extra = ""
                if evidence:
                    extra += f'<p><span class="gc-muted">{_("Что видно в логе/приборе:")}</span> {format_inline(evidence)}</p>'
                if consequence:
                    extra += f'<p><span class="gc-muted">{_("Последствия:")}</span> {format_inline(consequence)}</p>'
                rows.append(
                    f'<div class="gc-card fail"><strong class="fail__symptom">{sym}</strong>'
                    f'<p><span class="gc-muted">{_("Причина:")}</span> {format_inline(cause)}</p>{extra}'
                    f'<p><span class="gc-muted">{_("Исправление:")}</span> {format_inline(fix)}</p>'
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
    body = f"""    <p class="gc-breadcrumb"><a href="../ref/index.html">{_("Справочник")}</a><span>{_("Журнал ошибок и фейлов")}</span></p>
    <h1 class="gc-display">{_("Журнал ошибок и фейлов")}</h1>
    <p class="gc-muted">{_('{n} случаев из разделов «Диагностика» всех написанных модулей, по схеме симптом → причина → что видно в логе или приборе → последствия → исправление. Собирается автоматически при сборке сайта; чтобы добавить кейс — допиши диагностику в модуль. Разборы реальных инцидентов — в модуле <a href="../m/ops-case-studies.html">«Разбор реальных аварий»</a>.', n=total)}</p>
    <div class="home-toc">{toc}</div>
    <div class="fails">{"".join(sections)}</div>"""
    return layout(title=_("Журнал фейлов"), base=base, body=body, active="fails")


def render_formulas(model: dict) -> str:
    """Reference of formulas and CLI commands from data/formulas.json, grouped by section."""
    base = "../"
    data = i18n.tr_data(json.loads((ROOT / "data" / "formulas.json").read_text(encoding="utf-8")))
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
    body = f"""    <p class="gc-breadcrumb"><a href="../ref/index.html">{_("Справочник")}</a><span>{_("Формулы и команды")}</span></p>
    <h1 class="gc-display">{_("Формулы и команды")}</h1>
    <p class="gc-muted">{_("Шпаргалка инженера: формулы с единицами и CLI-команды прошивок, каждая со ссылкой на модуль, где она объясняется. Источник — <code>data/formulas.json</code>.")}</p>
    <div class="home-toc">{"".join(toc)}</div>
    <div class="fails">{"".join(sections)}</div>"""
    return layout(title=_("Формулы и команды"), base=base, body=body, active="ref")


def render_glossary(model: dict) -> str:
    base = "../"
    data = load_glossary()
    terms = sorted(data["terms"], key=lambda t: t["term"].lower())
    cards = []
    for t in terms:
        mod = model["modules"].get(t.get("module"))
        link = f'<a class="gc-tag" href="{base}m/{esc(mod["id"])}.html">{esc(mod["title"])}</a>' if mod else ""
        cards.append(f'<div class="gc-card glossary-entry"><h3>{esc(t["term"])}</h3><p>{format_inline(t["def"])}</p>{link}</div>')
    body = f"""    <p class="gc-breadcrumb"><a href="../ref/index.html">{_("Справочник")}</a><span>{_("Глоссарий")}</span></p>
    <h1 class="gc-display">{_("Глоссарий")}</h1>
    <p class="gc-muted">{_("{n} терминов. Каждый ведёт к модулю, где объясняется подробно.", n=len(terms))}</p>
    <div class="gc-grid ref-grid glossary">{"".join(cards)}</div>"""
    return layout(title=_("Глоссарий"), base=base, body=body, active="glossary")


def render_account() -> str:
    base = "../"
    body = """    <h1 class="gc-display">Аккаунт</h1>
    <section class="gc-panel" data-acc="off">
      <p class="gc-muted">Аккаунты ещё не включены: прогресс хранится только в этом браузере — <a href="progress.html">моя ведомость</a>. Как включить — <code>docs/MULTIUSER-PLAN.md</code>.</p>
    </section>
    <section class="gc-panel" data-acc="loading" hidden><p class="gc-muted">Подключаюсь к серверу…</p></section>
    <section class="gc-panel acc-forms" data-acc="guest" hidden>
      <div class="widget__presets" role="tablist">
        <button type="button" class="gc-tag" data-tab="login" data-state="ok">Вход</button>
        <button type="button" class="gc-tag" data-tab="register">Регистрация</button>
        <button type="button" class="gc-tag" data-tab="forgot">Забыли пароль</button>
      </div>
      <form class="acc-form" data-form="login">
        <label>Почта <input type="email" name="email" autocomplete="email" required></label>
        <label>Пароль <input type="password" name="password" autocomplete="current-password" required></label>
        <gc-button type="submit">Войти</gc-button>
      </form>
      <form class="acc-form" data-form="register" hidden>
        <label>Почта <input type="email" name="email" autocomplete="email" required></label>
        <label>Имя пользователя <input type="text" name="username" autocomplete="username" pattern="[a-z0-9_]{3,32}" required>
          <small class="gc-muted">3–32 символа: a-z, 0-9, _ — его видит администрация</small></label>
        <label>Пароль <input type="password" name="password" autocomplete="new-password" minlength="10" required>
          <small class="gc-muted">минимум 10 символов</small></label>
        <gc-button type="submit">Зарегистрироваться</gc-button>
        <p class="gc-muted">Оценки видишь ты и администрация курса. Прогресс, накопленный в этом браузере, перейдёт в аккаунт.</p>
      </form>
      <form class="acc-form" data-form="forgot" hidden>
        <label>Почта <input type="email" name="email" autocomplete="email" required></label>
        <gc-button type="submit">Прислать ссылку</gc-button>
      </form>
    </section>
    <section class="gc-panel" data-acc="recovery" hidden>
      <form class="acc-form" data-form="newpass">
        <label>Новый пароль <input type="password" name="password" autocomplete="new-password" minlength="10" required></label>
        <gc-button type="submit">Сохранить пароль</gc-button>
      </form>
    </section>
    <section class="gc-panel" data-acc="user" hidden>
      <p class="progress-headline"><span data-acc-username></span> <span class="gc-tag" data-acc-role></span></p>
      <p class="gc-muted">Почта: <span data-acc-email></span> · синхронизация: <span class="gc-tag" data-acc-sync></span></p>
      <p class="gc-muted" data-acc-groups hidden>Группы: <span data-acc-group-names></span></p>
      <label class="acc-form acc-form--inline"><span>Язык интерфейса</span> LANG_SELECT</label>
      <form class="acc-form acc-form--inline" data-form="rename">
        <label>Сменить имя <input type="text" name="username" pattern="[a-z0-9_]{3,32}" required></label>
        <gc-button type="submit" variant="secondary">Сохранить</gc-button>
      </form>
      <div class="progress-actions">
        <a class="gc-tag" href="progress.html">Моя ведомость</a>
        <a class="gc-tag" href="admin.html" data-acc-admin hidden>Админка</a>
        <gc-button variant="secondary" data-acc-sync-now>Синхронизировать</gc-button>
        <gc-button variant="secondary" data-acc-logout>Выйти</gc-button>
      </div>
      <p class="gc-muted">При выходе копия прогресса в этом браузере стирается — на сервере он остаётся.</p>
    </section>
    <p class="acc-msg" data-acc-msg aria-live="polite"></p>"""
    options = "".join(f'<option value="{l["code"]}"' + (" selected" if l["code"] == i18n.lang() else "") + f'>{esc(l["name"])}</option>'
                      for l in i18n.LANGS)
    body = tr_html(body).replace("LANG_SELECT", f'<select data-acc-lang aria-describedby="acc-lang-note">{options}</select>'
                                  f'<small class="gc-muted" id="acc-lang-note">{_("Закреплён за аккаунтом: после входа курс откроется на этом языке на любом устройстве.")}</small>')
    return layout(title=_("Аккаунт"), base=base, body=body, active="progress",
                  extra_head=f'\n  <script src="{base}{up()}assets/account-page.js" defer></script>')


def render_exam() -> str:
    base = "../"
    body = """    <h1 class="gc-display">Экзамены</h1>
    <section class="gc-panel" data-ex="off">
      <p class="gc-muted">Экзамены работают, когда включены аккаунты. Квизы модулей — самопроверка: их ответы лежат в открытом репозитории. Экзамены — другое: вопросы и ответы хранятся только в базе, проверяет сервер.</p>
    </section>
    <section class="gc-panel" data-ex="guest" hidden><p class="gc-muted">Экзамены доступны после входа — <a href="account.html">аккаунт</a>.</p></section>
    <section data-ex="list" hidden><div data-ex-list></div></section>
    <section class="gc-panel" data-ex="run" hidden>
      <p class="progress-headline"><span data-ex-title></span> <span class="gc-tag" data-ex-timer></span></p>
      <p class="gc-muted">Ответы сохраняются в этом браузере — после перезагрузки страницы попытка продолжится. По истечении времени работа сдаётся сама.</p>
      <div data-ex-questions></div>
      <gc-button data-ex-submit>Сдать</gc-button>
    </section>
    <section class="gc-panel" data-ex="result" hidden>
      <p class="progress-headline" data-ex-score></p>
      <ol class="exam-review" data-ex-review></ol>
      <gc-button variant="secondary" data-ex-back>К списку экзаменов</gc-button>
    </section>
    <p class="acc-msg" data-acc-msg aria-live="polite"></p>"""
    return layout(title=_("Экзамены"), base=base, body=tr_html(body), active="progress",
                  extra_head=f'\n  <script src="{base}{up()}assets/exam-page.js" defer></script>')


def render_admin() -> str:
    base = "../"
    body = """    <h1 class="gc-display">Администрация</h1>
    <section class="gc-panel" data-adm="off">
      <p class="gc-muted">Страница для администрации курса. Нужен вход с ролью admin или superadmin — <a href="account.html">аккаунт</a>.</p>
    </section>
    <section data-adm="on" hidden>
      <div class="gc-panel">
        <p class="gc-label gc-muted">Студенты</p>
        <div class="progress-actions">
          <input type="search" class="adm-filter" placeholder="поиск по имени или почте" data-adm-filter>
          <select class="adm-filter adm-cohort" data-adm-cohort aria-label="Группа"><option value="">все группы</option></select>
          <gc-button variant="secondary" data-adm-csv>CSV</gc-button>
          <gc-button variant="secondary" data-adm-reload>Обновить</gc-button>
        </div>
        <div class="md-table-wrap"><table class="md-table adm-table">
          <thead><tr><th>Имя</th><th>Почта</th><th>Роль</th><th>Группы</th><th>Освоено</th><th>Балл</th><th>Активность</th></tr></thead>
          <tbody data-adm-rows></tbody>
        </table></div>
        <p class="gc-muted">Баллы считает браузер студента (квизы и задачи проверяются на его стороне): это видимость работы, а не экзамен — <code>docs/MULTIUSER-PLAN.md</code>, раздел 6.</p>
      </div>
      <div class="gc-panel" data-adm-detail hidden></div>
      <div class="gc-panel" data-adm-cohorts-panel>
        <p class="gc-label gc-muted">Группы</p>
        <p class="gc-muted">Группа — это фильтр для оценок и CSV. Студента добавляют в группу в таблице выше; сам студент видит только названия своих групп. Удаление группы не трогает оценки.</p>
        <form class="progress-actions acc-form" data-adm-cohort-form>
          <input name="name" class="adm-filter" placeholder="название, например «Весна-2027»" maxlength="100" required data-adm-cohort-name>
          <button type="submit" class="gc-tag">создать группу</button>
        </form>
        <ul class="progress-labs" data-adm-cohorts></ul>
      </div>
      <div class="gc-panel" data-adm-exams-panel>
        <p class="gc-label gc-muted">Экзамены</p>
        <p class="gc-muted">Банк вопросов — JSON: <code>{"title", "pass_pct", "questions_per_attempt", "time_limit_min", "attempts_allowed", "show_review", "questions": [{"q", "options", "answer", "explain"}]}</code>. Файл квиза модуля тоже подходит, но его ответы публичны — для настоящего экзамена готовь закрытый банк и не кладите его в репозиторий.</p>
        <div class="progress-actions">
          <label class="gc-tag" style="cursor:pointer">Загрузить банк JSON <input type="file" accept="application/json" data-adm-exam-file hidden></label>
          <gc-button variant="secondary" data-adm-exam-csv>CSV результатов</gc-button>
        </div>
        <ul class="progress-labs" data-adm-exams></ul>
        <div class="md-table-wrap"><table class="md-table">
          <thead><tr><th>Экзамен</th><th>Студент</th><th>Результат</th><th>Сдан</th><th>Когда</th></tr></thead>
          <tbody data-adm-exam-results></tbody>
        </table></div>
      </div>
      <div class="gc-panel" data-adm-audit-panel>
        <p class="gc-label gc-muted">Журнал смены ролей</p>
        <ul class="progress-labs" data-adm-audit></ul>
      </div>
    </section>
    <p class="acc-msg" data-acc-msg aria-live="polite"></p>"""
    return layout(title=_("Администрация"), base=base, body=tr_html(body), active="progress",
                  extra_head=f'\n  <script src="{base}{up()}assets/admin-page.js" defer></script>')


def render_page(name: str, title: str) -> str:
    base = "../"
    inner = localized_text(ROOT / "content" / "pages" / f"{name}.html")
    active = name if name in ("glossary", "fails") else "ref"
    title = _(title)
    body = f"""    <p class="gc-breadcrumb"><a href="../ref/index.html">{_("Справочник")}</a><span>{esc(title)}</span></p>
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
        raw = module_source(m)
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
    gl = load_glossary()
    for t in gl["terms"]:
        docs.append({"id": "g:" + t["term"], "type": "term", "title": t["term"], "url": "pages/glossary.html",
                     "group": _("Глоссарий"), "level": "", "summary": t["def"], "headings": "", "text": "", "tags": ""})
    for g in model["groups"]:
        c = g.get("capstone")
        if c:
            docs.append({"id": c["id"], "type": "capstone", "title": c["title"], "url": f"cap/{c['id']}.html",
                         "group": g["title"], "level": "", "summary": c.get("result", ""), "headings": "",
                         "text": " ".join(c.get("deliverables", []) + c.get("criteria", [])), "tags": ""})
    for p in model.get("projects", []):
        docs.append({"id": p["id"], "type": "capstone", "title": _("Проект {n}", n=p['num']) + f": {p['title']}", "url": f"projects/{p['id']}.html",
                     "group": _("Проекты"), "level": p.get("level", ""), "summary": p["summary"], "headings": "",
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
    return layout(title=_("Поиск"), base=base, body=tr_html(body), active="search",
                  extra_head=f'\n  <script src="{base}{up()}assets/search.js" defer></script>')


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
            # "labels": {"param": {"<value>": "<shown text>"}} lets a translation show a string parameter in its own
            # language while the answer formula keeps comparing the source value
            labels = t.get("labels", {})
            statement = re.sub(r"\{([a-z0-9_]+)\}",
                               lambda mm: labels.get(mm.group(1), {}).get(str(vals[mm.group(1)]), _fmt_num(vals[mm.group(1)])), t["statement"])
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
        <div class="table-wrap"><table class="progress-table"><thead><tr><th>{_("Модуль")}</th><th>{_("Квиз")}</th><th>{_("Лаба")}</th><th>{_("Балл")}</th><th>{_("Статус")}</th></tr></thead><tbody>{rows}</tbody></table></div>
      </section>"""
    paths = "".join(table(_("Путь: {t}", t=p['title']), p["moduleIds"], f"path-{p['id']}") for p in model["paths"])
    tracks = "".join(table(_("Трек {n}", n=g['index']) + f": {g['title']}", g["moduleIds"], f"track-{g['id']}") for g in model["groups"] if g["kind"] == "track")
    caps = "".join(
        f'<li data-cap="{esc(g["capstone"]["id"])}"><a href="{base}cap/{esc(g["capstone"]["id"])}.html">{esc(g["capstone"]["title"])}</a> <span class="gc-tag" data-cap-status></span></li>'
        for g in model["groups"] if g.get("capstone")
    )
    projs = "".join(
        f'<li data-cap="{esc(pr["id"])}"><a href="{base}projects/{esc(pr["id"])}.html">{_("Проект {n}", n=pr["num"])}: {esc(pr["title"])}</a> <span class="gc-tag" data-cap-status></span></li>'
        for pr in sorted(model.get("projects", []), key=lambda x: x["num"])
    )
    projs_html = (f'<p class="gc-label gc-muted">{_("Проекты «ПО для БАС»")}</p><ul class="progress-caps">{projs}</ul>' if projs else "")
    all_pub = [m["id"] for m in model["modules"].values() if m["status"] == "published"]
    body = f"""    <h1 class="gc-display">{_("Мой прогресс")}</h1>
    <p class="gc-muted">{_("Балл модуля = 40% квиз (лучшая попытка) + 60% лабораторная; в модулях с задачами — 30% квиз + 30% задачи + 40% лабораторная. «Освоен» — квиз ≥ 80%, все задачи решены и все пункты лабораторной. Ручная отметка видна как «отмечен», это честно другое.")}</p>
    <section class="gc-panel">
      <p class="gc-label gc-muted">{_("Весь курс")}</p>
      <p class="progress-headline" data-group-summary="{esc(','.join(all_pub))}"></p>
      <div class="gc-progress" role="progressbar" aria-label="{_("Общий балл")}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" data-progress-of="{esc(','.join(all_pub))}" style="--gc-value: 0%"></div>
      <p class="gc-label gc-muted">{_("Итоговые проекты")}</p>
      <ul class="progress-caps">{caps}</ul>
      {projs_html}
    </section>
    <h2 class="gc-title section-title">{_("По прошивке")}</h2>
{paths}
    <h2 class="gc-title section-title">{_("По навыкам")}</h2>
{tracks}
""" + tr_html("""    <section class="gc-panel">
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
    </section>""")
    return layout(title=_("Мой прогресс"), base=base, body=body, active="progress",
                  extra_head=f'\n  <script src="{base}{up()}assets/progress-page.js" defer></script>')


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
    # shared files plus one language tree: the worker is registered as sw.js?lang=<code> (assets/offline.js)
    # and precaches only the visitor's language
    files: list[str] = ["index.html", "manifest.webmanifest"]
    for d in GENERATED_DIRS:
        for f in sorted((ROOT / d).rglob("*")):
            if f.is_file():
                files.append(f.relative_to(ROOT).as_posix())
    trees = {i18n.SOURCE: []}
    for l in i18n.LANGS[1:]:
        trees[l["code"]] = sorted(f.relative_to(ROOT).as_posix() for f in (ROOT / l["dir"]).rglob("*") if f.is_file())
    for f in sorted((ROOT / "assets").rglob("*")):
        if f.is_file():
            files.append(f.relative_to(ROOT).as_posix())
    for f in sorted((ROOT / GC).glob("*")):
        if f.is_file():
            files.append(f.relative_to(ROOT).as_posix())
    h = hashlib.sha1()
    for rel in files + [x for t in trees.values() for x in t]:
        fp = ROOT / rel
        if rel != "manifest.webmanifest" and fp.exists():
            h.update(rel.encode()); h.update(fp.read_bytes())
    version = h.hexdigest()[:12]
    sw = f"""/* Generated by scripts/build_site.py — do not edit. Cache version {version}. */
const LANG = new URL(self.location.href).searchParams.get("lang") || "{i18n.SOURCE}";
const TREES = {json.dumps(trees, ensure_ascii=False)};
const VERSION = "uav-student-{version}-" + LANG;
// the source-language tree and shared assets, plus the tree of the visitor's language
const PRECACHE = {json.dumps(files, ensure_ascii=False)}.concat(TREES[LANG] || []);
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
    if path.suffix == ".html" and "<!--LANG-ALTERNATES-->" in text:
        tree = ROOT / i18n.lang_dir() if i18n.lang_dir() else ROOT
        alts = alternates_for(path.relative_to(tree).as_posix())
        head = "".join(f'\n  <link rel="alternate" hreflang="{i18n.BY_CODE[c]["htmlLang"]}" href="{u}">' for c, u in alts.items())
        text = text.replace("\n  <!--LANG-ALTERNATES-->", head + "\n  " + LANG_REDIRECT, 1)
        for c, u in alts.items():
            text = text.replace(f'href="#lang-{c}"', f'href="{u}"', 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_language(code: str) -> dict:
    """Build one language tree: the source language at the repository root, others under /<dir>/."""
    i18n.set_lang(code)
    out = ROOT / i18n.lang_dir() if i18n.lang_dir() else ROOT
    model = build_model()
    if out == ROOT:
        for d in GENERATED_DIRS:
            shutil.rmtree(ROOT / d, ignore_errors=True)
    else:
        shutil.rmtree(out, ignore_errors=True)

    write(out / "index.html", render_home(model))
    for m in model["modules"].values():
        write(out / "m" / f"{m['id']}.html", render_module(m, model))
    for p in model["paths"]:
        write(out / "path" / f"{p['id']}.html", render_path(p, model))
    for g in model["groups"]:
        if g.get("capstone"):
            write(out / "cap" / f"{g['capstone']['id']}.html", render_capstone(g, model))
    if model.get("projects"):
        write(out / "projects" / "index.html", render_projects_index(model))
        for pr in model["projects"]:
            write(out / "projects" / f"{pr['id']}.html", render_project(pr, model))
    write(out / "ref" / "index.html", render_ref_index(model))
    for s in model["stacks"]:
        write(out / "ref" / f"{s['key']}.html", render_ref_stack(s, model))
    for name, title in PAGES.items():
        if name == "fails":
            write(out / "pages" / "fails.html", render_fails(model))
        elif name == "formulas":
            write(out / "pages" / "formulas.html", render_formulas(model))
        elif name == "glossary":
            write(out / "pages" / "glossary.html", render_glossary(model))
        else:
            write(out / "pages" / f"{name}.html", render_page(name, title))
    if QUIZ_SRC.is_dir():
        for q in QUIZ_SRC.glob("*.json"):
            write(out / "quiz" / q.name, localized_text(q))
    if TASKS_SRC.is_dir():
        for t in sorted(TASKS_SRC.glob("*.json")):
            bank = json.loads(localized_text(t))
            write(out / "tasks" / t.name, json.dumps(build_task_variants(bank), ensure_ascii=False) + "\n")
    write(out / "pages" / "search.html", render_search())
    write(out / "pages" / "progress.html", render_progress(model))
    write(out / "pages" / "account.html", render_account())
    write(out / "pages" / "admin.html", render_admin())
    write(out / "pages" / "exam.html", render_exam())
    write(out / "api" / "v1" / "grading.json", json.dumps(grading_meta(model), ensure_ascii=False, indent=2) + "\n")
    write(out / "api" / "v1" / "search.json", json.dumps(search_index(model), ensure_ascii=False) + "\n")
    write(out / "api" / "v1" / "curriculum.json", json.dumps(api_payload(model), ensure_ascii=False, indent=2) + "\n")
    return model


def write_redirects(code: str) -> None:
    """Pages under a language's former URL directory ("oldDirs") that send visitors to the current one."""
    l = i18n.BY_CODE[code]
    new = ROOT / l["dir"]
    for old in l.get("oldDirs", []):
        shutil.rmtree(ROOT / old, ignore_errors=True)
        for f in sorted(new.rglob("*.html")):
            rel = f.relative_to(new).as_posix()
            target = "../" * (rel.count("/") + 1) + l["dir"] + "/" + rel
            write(ROOT / old / rel, f"""<!doctype html>
<html lang="{l['htmlLang']}"><head><meta charset="utf-8">
<title>{esc(l['name'])}</title>
<link rel="canonical" href="{target}">
<meta http-equiv="refresh" content="0; url={target}">
<script>location.replace("{target}" + location.search + location.hash)</script>
</head><body><p><a href="{target}">{esc(l['name'])}</a></p></body></html>
""")


def write_js_catalogs() -> None:
    """assets/i18n/<lang>.js: the interface catalog for the browser (window.UAV_I18N_CATALOG)."""
    d = ROOT / "assets" / "i18n"
    shutil.rmtree(d, ignore_errors=True)
    for l in i18n.LANGS[1:]:
        cat = i18n.catalog(l["code"])
        write(d / f"{l['code']}.js", "/* Generated by scripts/build_site.py from i18n/" + l["code"] + "/ui.json — do not edit. */\n"
              "window.UAV_I18N_CATALOG = " + json.dumps(cat, ensure_ascii=False, sort_keys=True) + ";\n")


def main() -> None:
    write_js_catalogs()
    stats = []
    for l in i18n.LANGS:
        model = build_language(l["code"])
        write_redirects(l["code"])
        st = TRANSLATION_STATE.get(l["code"], {})
        n_pub = sum(1 for m in model["modules"].values() if m["status"] == "published")
        if l["code"] == i18n.SOURCE:
            n_quiz = len(list(QUIZ_SRC.glob("*.json"))) if QUIZ_SRC.is_dir() else 0
            n_tasks = sum(task_count(p.stem) for p in TASKS_SRC.glob("*.json")) if TASKS_SRC.is_dir() else 0
            stats.append(f"built: {len(model['modules'])} module pages ({n_pub} written, {n_quiz} with quiz, {n_tasks} numeric tasks), "
                         f"{len(model['stacks'])} stacks, {len(PAGES)} pages")
        else:
            ok = sum(1 for v in st.values() if v == "ok")
            stale = sum(1 for v in st.values() if v == "stale")
            miss = len(i18n.missing.get(l["code"], ()))
            own = sum(1 for m in model["modules"].values() if m["status"] == "published"
                      and i18n.own_translated_path(ROOT / m["articleMeta"]["sourceFile"], l["code"]).is_file())
            via = f" ({own} own, the rest from {l['fallback']})" if l.get("fallback") else ""
            stats.append(f"  /{l['dir']}/: modules translated {ok}/{n_pub}{via}" + (f" ({stale} stale)" if stale else "")
                         + f", interface strings missing {miss}")
    i18n.set_lang(i18n.SOURCE)
    write_pwa()
    print("\n".join(stats))
    # interface strings the build looked up, for scripts/i18n_extract.py
    used = ROOT / "i18n" / ".build-keys.json"
    used.write_text(json.dumps(sorted(i18n.used), ensure_ascii=False, indent=0) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
