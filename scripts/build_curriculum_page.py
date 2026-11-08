#!/usr/bin/env python3
"""Generate curriculum/curriculum.html — the administration overview of the course.

The page is for maintainers and administration, not for students: what the course contains, how it
is assessed, which projects exist, how content is authored and checked, and the state of the plans.
Everything is computed from the repository (curriculum.json, manifest, projects, quizzes, tasks,
diagrams, examples, CI, docs), so the page cannot drift from the project again. Visual style is the
existing curriculum.css; the markup keeps its classes and the seven radio-button tabs.

  python scripts/build_curriculum_page.py      (also run by scripts/publish.py)
"""
from __future__ import annotations

import html
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "curriculum" / "curriculum.html"
SITE = "https://irreligious86.github.io/UAV-Education/"


def e(s) -> str:
    return html.escape(str(s), quote=True)


def load(p):
    return json.loads((ROOT / p).read_text(encoding="utf-8"))


def table(head: list[str], rows: list[list[str]]) -> str:
    th = "".join(f"<th>{e(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table>\n<thead><tr>{th}</tr></thead>\n<tbody>{body}</tbody>\n</table>"


def card(title: str, inner: str) -> str:
    return f'<article class="card">\n<h3>{e(title)}</h3>\n{inner}\n</article>'


def ul(items) -> str:
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def collect() -> dict:
    cur = load("data/curriculum.json")
    man = load("data/content-manifest.json")
    proj = load("data/projects.json")
    articles = {}
    for sec in man.get("sections", man.get("stacks", [])):
        for a in sec.get("articles", []):
            articles[a["id"]] = a
    quizzes = {p.stem: len(json.loads(p.read_text(encoding="utf-8"))["questions"]) for p in (ROOT / "content/quiz").glob("*.json")}
    tasks = {p.stem: len(json.loads(p.read_text(encoding="utf-8"))["tasks"]) for p in (ROOT / "content/tasks").glob("*.json")}
    diag_refs = Counter()
    for f in (ROOT / "content").rglob("*.md"):
        diag_refs[f.stem] = len(re.findall(r"\{\{diagram:", f.read_text(encoding="utf-8")))
    examples = []
    for d in sorted((ROOT / "examples").iterdir()):
        if d.is_dir():
            n = sum(len(re.findall(r"^def test_", f.read_text(encoding="utf-8", errors="ignore"), re.M))
                    for f in d.rglob("test_*.py"))
            examples.append((d.name, n))
    steps = re.search(r"STEPS = \((.*?)\)", (ROOT / "scripts/publish.py").read_text(encoding="utf-8"), re.S).group(1)
    ci = re.findall(r"^\s*- name: (.+)$", (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"), re.M)
    docs = []
    for f in sorted((ROOT / "docs").glob("*.md")):
        first = next((ln[2:].strip() for ln in f.read_text(encoding="utf-8").splitlines() if ln.startswith("# ")), f.stem)
        docs.append((f.name, first))
    plans = []
    for f in sorted((ROOT / "docs").glob("COURSE-PLAN-STAGE*.md")):
        for ln in f.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\| (\d+) (✅|🔄|⏸)? ?\| ([^|]+)\|", ln)
            if m and m.group(2):
                plans.append((f.stem.replace("COURSE-PLAN-", ""), m.group(1), m.group(2), m.group(3).strip()))
    return dict(cur=cur, articles=articles, proj=proj, quizzes=quizzes, tasks=tasks, diag=diag_refs,
                diagrams=len(list((ROOT / "assets/diagrams").glob("*.svg"))),
                widgets=sorted(p.stem for p in (ROOT / "assets/widgets").glob("*.js") if p.stem != "plot"),
                examples=examples, steps=[s.strip().strip('"') for s in steps.split(",") if s.strip()],
                ci=ci, docs=docs, plans=plans)


def mod_link(mid: str, title: str) -> str:
    return f'<a href="{SITE}m/{e(mid)}.html">{e(title)}</a>'


def render(d: dict) -> str:
    cur, proj = d["cur"], d["proj"]["projects"]
    tracks, electives = cur["tracks"], cur["electives"]
    all_mods = {m["id"]: m for g in tracks + electives for m in g["modules"]}
    n_mod = len(d["articles"])
    hours = int(round(sum(m.get("hours", 0) for m in all_mods.values())))
    levels = Counter(m["level"] for m in all_mods.values())
    n_q = sum(d["quizzes"].values())
    n_t = sum(v for k, v in d["tasks"].items() if k != "prereq-test")
    n_tm = sum(1 for k in d["tasks"] if k != "prereq-test")
    labs = sum(len(m["lab"]["criteria"]) for m in all_mods.values() if m.get("lab"))

    # ---------------- tab 1: overview
    status = table(["Показатель", "Значение"], [
        ["Модулей (все опубликованы)", str(n_mod)],
        ["Учебных часов по программе", f"{hours} ч (≈ {round(hours / 10)} недель при 10 ч/нед.)"],
        ["Треков / элективов / путей по прошивкам", f"{len(tracks)} / {len(electives)} / {len(cur['paths'])}"],
        ["Вопросов в квизах", f"{n_q} в {len(d['quizzes'])} квизах"],
        ["Числовых задач", f"{n_t} в {n_tm} модулях + входной тест"],
        ["Пунктов лабораторных", str(labs)],
        ["Диаграмм и графиков", f"{d['diagrams']} (в каждом модуле ≥ 1)"],
        ["Интерактивных виджетов", f"{len(d['widgets'])}: {', '.join(d['widgets'])}"],
        ["Проектов портфолио", f"{len(proj)}, у всех есть стартер с тестами"],
        ["Стартовых примеров кода", f"{len(d['examples'])} папок, {sum(n for _, n in d['examples'])} тестов в CI"],
    ])
    lvl_cards = "".join(card(f"{lv} — {name}", ul([f"{levels.get(lv, 0)} модулей", desc])) for lv, name, desc in [
        ("L1", "Оператор", "сборка, прошивка, режимы, безопасность, первый полёт"),
        ("L2", "Интегратор", "датчики, радио, питание, логи, настройка по данным"),
        ("L3", "Автоматизатор", "оценка состояния, миссии, Lua/IPF, companion, MAVLink"),
        ("L4", "Разработчик", "ROS 2, восприятие, ML на борту, системная инженерия"),
    ])
    track_cards = "".join(card(f"{i + 1}. {t['title']} ({t['level']})", ul([
        e(t.get("goal", "")), f"{len(t['modules'])} модулей, {round(sum(m.get('hours', 0) for m in t['modules']))} ч",
        f"Итоговый проект: {e(t['capstone']['title'])}" if t.get("capstone") else "Итоговый проект: —"]))
        for i, t in enumerate(tracks))
    tab1 = f"""
<section id="status">
<h2>Состояние курса</h2>
<p class="muted">Страница собирается из данных репозитория при каждой публикации (<code>scripts/build_curriculum_page.py</code>) и не может отстать от проекта.</p>
{status}
</section>
<section id="goals">
<h2>Уровни подготовки</h2>
<div class="grid">{lvl_cards}</div>
</section>
<section id="track-overview">
<h2>Треки</h2>
<p>Путь «с нуля до инженера»: восемь треков подряд; элективы и пути по конкретной прошивке собирают те же модули в другом порядке.</p>
<div class="grid">{track_cards}</div>
</section>"""

    # ---------------- tab 2: methodology
    tab2 = f"""
<section id="method">
<h2>Устройство модуля</h2>
{ul(["<strong>summary</strong> — зачем модуль и что будет на выходе;",
     "<strong>theory</strong> — механизм, формулы, параметры, разобранный пример с числами, диаграмма или график;",
     "<strong>practice</strong> — шаги лабораторной с ожидаемым результатом и кодом, который запускали;",
     "<strong>diagnostics</strong> — симптом → причина → что сделать;",
     "<strong>references</strong> — первичные источники (A) и вторичные (B/C) с пометкой уровня;",
     "<strong>checklist</strong> — что студент умеет после модуля."])}
<p>Правило безопасности: всё, что управляет аппаратом, сначала проходит тесты и SITL; реальный полёт — с проверенным failsafe и пилотом, готовым забрать управление.</p>
</section>
<section id="verification">
<h2>Проверка знаний и оценка</h2>
<div class="grid">
{card("Квиз", ul([f"{n_q} вопросов, в каждом модуле", "вопросы «найди ошибку» с фрагментами конфигов и кода",
                  "длина правильного ответа не подсказывает его (правило в валидаторе)", "порог «освоен» — 80 %"]))}
{card("Задачи", ul([f"{n_t} задач с числовым ответом в {n_tm} модулях", "8 вариантов чисел на задачу, решение после верного ответа",
                    "входной тест по математике перед курсом"]))}
{card("Лабораторная", ul([f"{labs} пунктов в лабораторных", "часть пунктов подтверждается грейдером (файл uav-lab-result/1, импорт на странице прогресса, отметка ⚙)",
                          "остальное — самопроверка по критериям"]))}
{card("Балл модуля", ul(["квиз 40 % + лаба 60 %, или квиз 30 % + задачи 30 % + лаба 40 %",
                         "«Освоен»: квиз ≥ 80 %, все задачи и все пункты лабы", "итоговые проекты треков и проекты портфолио — по критериям приёмки и шкале оценки"]))}
</div>
</section>
<section id="quality">
<h2>Контроль качества содержания</h2>
{ul(["Сверка фактов независимыми агентами по исходникам и документации прошивок: 2204 утверждения, 254 исправления (ноябрь 2026), отчёты — <code>docs/reviews/factcheck/</code>.",
     "Еженедельная проверка внешних ссылок (<code>.github/workflows/links.yml</code>), мёртвые ссылки — issue <code>broken-links</code>.",
     "Код в модулях запускается или компилируется перед публикацией; примеры в <code>examples/</code> покрыты тестами в CI.",
     "Новые имена параметров при смене версий прошивок даются вместе со старыми (Copter 4.7, Betaflight 2025.12, PX4 1.16/1.17)."])}
</section>"""

    # ---------------- tab 3: comparisons
    by_stack = Counter()
    for a in d["articles"].values():
        by_stack[a.get("stack") or a.get("sourceFile", "").split("/")[1]] += 1
    tab3 = f"""
<section id="comparison">
<h2>Прошивки в курсе</h2>
{table(["", "Betaflight", "INAV", "ArduPilot", "PX4"], [
    ["Версии в модулях", "4.5, отличия 2025.12", "7.x–9.x", "4.5–4.7 (новые имена 4.7)", "1.15–1.17"],
    ["Назначение", "FPV, ручной полёт", "навигация на F4/F7, крыло", "автопилот, миссии, тяжёлые платформы", "автопилот, модульная архитектура, ROS 2"],
    ["Оценка состояния", "только ориентация", "комплементарный оценщик", "EKF3", "EKF2"],
    ["Логика на борту", "CLI, пресеты", "Programming Framework", "Lua", "модули, ROS 2 через uXRCE-DDS"],
    ["Companion", "нет", "ограниченно (MSP/MAVLink)", "MAVLink, AP_DDS", "MAVLink, uXRCE-DDS"],
    ["Путь в курсе", "трек Оператор + путь Betaflight", "электив INAV + путь", "треки 3–8 + путь", "треки 5–8 + путь"],
])}
</section>
<section id="sections">
<h2>Модули по разделам</h2>
{table(["Раздел", "Модулей"], [[e(k), str(v)] for k, v in sorted(by_stack.items(), key=lambda x: -x[1])])}
</section>"""

    # ---------------- tab 4: tracks and map
    rows = []
    for i, t in enumerate(tracks + electives):
        for m in t["modules"]:
            a = d["articles"].get(m["id"], {})
            rows.append([e(t["title"]), mod_link(m["id"], a.get("title", m["title"])), e(m["level"]), str(m.get("hours", "")),
                         str(d["quizzes"].get(m["id"], 0)), str(d["tasks"].get(m["id"], 0)), str(d["diag"].get(m["id"], 0)),
                         str(len(m["lab"]["criteria"])) if m.get("lab") else "—"])
    paths = "".join(card(p["title"], f"<p>{e(p.get('subtitle', ''))}</p>" + ul(
        [f"{e(st['title'])}: {len(st['modules'])} модулей" for st in p["stages"]])) for p in cur["paths"])
    backlog = ul([e(x) for x in cur.get("backlogTopics", [])])
    tab4 = f"""
<section id="paths">
<h2>Пути по прошивкам</h2>
<div class="grid">{paths}</div>
</section>
<section id="map">
<h2>Карта модулей</h2>
<p class="muted">Квиз — вопросов, задачи — числовых задач, схемы — диаграмм и графиков, лаба — пунктов критериев.</p>
{table(["Трек", "Модуль", "Ур.", "Ч", "Квиз", "Зад.", "Сх.", "Лаба"], rows)}
</section>
<section id="backlog">
<h2>Темы в резерве</h2>
{backlog}
</section>"""

    # ---------------- tab 5: projects and stack
    prow = [[str(p["num"]), f'<a href="{SITE}projects/{e(p["id"])}.html">{e(p["title"])}</a>', e(p.get("level", "")), f"{p.get('hours', '?')} ч",
             f"<code>{e(p['starter'])}</code>" if p.get("starter") else "—", str(len(p.get("milestones", []))),
             str(sum(1 for c in p.get("checks") or [] if c))] for p in proj]
    caps = [[e(t["title"]), e(t["capstone"]["title"]), e(t["capstone"].get("result", ""))] for t in tracks if t.get("capstone")]
    ex = [[f"<code>examples/{e(n)}</code>", str(t)] for n, t in d["examples"]]
    tab5 = f"""
<section id="capstones">
<h2>Итоговые проекты треков</h2>
{table(["Трек", "Проект", "Результат"], caps)}
</section>
<section id="projects">
<h2>Проекты портфолио</h2>
<p class="muted">Этапы — шаги проекта; проверяемых — этапов с командой автопроверки. Общая шкала: функциональность, проверяемость, инженерный отчёт, код и документация × засчитано/хорошо/отлично.</p>
{table(["№", "Проект", "Уровень", "Объём", "Стартер", "Этапов", "Проверяемых"], prow)}
</section>
<section id="examples">
<h2>Стартовый код и грейдеры</h2>
{table(["Папка", "Тестов"], ex)}
</section>
<section id="tools">
<h2>Стек инструментов студента</h2>
{ul(["Betaflight App, INAV Configurator, Mission Planner, QGroundControl", "ArduPilot SITL, PX4 SITL (Gazebo), MAVProxy",
     "Python 3 (pymavlink, numpy, scipy, pandas), Blackbox Explorer, PlotJuggler", "Git, VS Code, Linux/WSL2",
     "Raspberry Pi / Jetson Orin как companion, ROS 2 (Jazzy или Humble), MAVSDK, MAVROS, uXRCE-DDS"])}
</section>"""

    # ---------------- tab 6: course standard
    tab6 = f"""
<section id="standard">
<h2>Стандарт модуля</h2>
<div class="grid">
{card("Файл", ul(["<code>content/&lt;раздел&gt;/&lt;id&gt;.md</code>, YAML front matter: id, title, level, readingTime, firmware, status, tags, related, next",
                  "запись в <code>data/content-manifest.json</code> и в треке <code>data/curriculum.json</code> (часы, цели, критерии лабы)",
                  "квиз <code>content/quiz/&lt;id&gt;.json</code>, задачи <code>content/tasks/&lt;id&gt;.json</code> — по необходимости"]))}
{card("Текст", ul(["курс — на русском, код и документация репозитория — на английском",
                   "таблицы Markdown (на телефоне — карточки), списки, блоки кода, <code>{{{{diagram:id|подпись}}}}</code>, <code>{{{{widget:имя}}}}</code>",
                   "источники: <code>- Название | URL | primary|secondary | A|B|C</code>, не меньше двух",
                   "параметры прошивок — с версией, если имя менялось"]))}
{card("Графика", ul(["структурные схемы — <code>scripts/diagrams/</code> (build_diagrams.py, wave2.py)",
                     "количественные графики из формул модуля — <code>plot.py</code> + <code>wave3.py</code>",
                     "подписи у кривых, а не цветная легенда; проверка на ширине телефона"]))}
{card("Квизы и задачи", ul(["правильный ответ не длиннее остальных систематически (доля «самый длинный» ≤ 34 %)",
                            "вопросы «найди ошибку» с фрагментом", "задачи: параметры диапазоном или списком, ответ — выражение Python, допуск"]))}
</div>
</section>
<section id="checks">
<h2>Автоматические проверки</h2>
<p>Публикация одной командой <code>python scripts/publish.py</code> выполняет по порядку:</p>
{ul([f"<code>{e(s)}</code>" for s in d["steps"]])}
<p>CI на каждый push (<code>.github/workflows/ci.yml</code>):</p>
{ul([e(s) for s in d["ci"]])}
</section>"""

    # ---------------- tab 7: documentation
    tree = """index.html, m/, ref/, pages/, cap/, path/, projects/, quiz/, tasks/, api/   generated site (GitHub Pages)
content/            module sources (Markdown), quizzes, tasks, static pages
data/               curriculum.json, content-manifest.json, projects.json, glossary and other data
scripts/            build, validation and checks; scripts/diagrams/ — diagrams and charts
assets/             site JS/CSS, widgets, generated diagrams
examples/           starter code, graders and their tests
docs/               plans, standards, reviews
curriculum/         this administration page (generated)
lib/ground-control-ui   design system (pinned release)"""
    plans = table(["Этап", "№", "", "Содержание"],
                  [[e(a), e(b), e(c), e(t[:160] + ("…" if len(t) > 160 else ""))] for a, b, c, t in d["plans"]])
    tab7 = f"""
<section id="repo">
<h2>Структура репозитория</h2>
<pre class="guide-block"><code>{e(tree)}</code></pre>
</section>
<section id="docs">
<h2>Документы</h2>
{table(["Файл", "О чём"], [[f"<code>docs/{e(n)}</code>", e(t)] for n, t in d["docs"]] + [
    ["<code>README.md</code>", "вход в проект, команды"], ["<code>ARCHITECTURE.md</code>", "слои сайта и путь к собственному серверу"],
    ["<code>content/README.md</code>", "как писать модули, таблицы, проверки"],
    ["<code>PROJECT-DIRECTIVES.md</code>, <code>archive/</code>", "исторические директивы первого этапа; при расхождении действует docs/"]])}
</section>
<section id="plans">
<h2>Планы развития: статус итераций</h2>
{plans}
<p class="footer tz-footer">Сгенерировано из репозитория. Не править руками: изменения вносить в данные и <code>scripts/build_curriculum_page.py</code>.</p>
</section>"""

    tabs = [("Обзор", tab1), ("Методология", tab2), ("Сравнения", tab3), ("Треки и карта", tab4),
            ("Проекты и стек", tab5), ("Стандарт курса", tab6), ("Документация", tab7)]
    inputs = "\n".join(f'      <input class="tab-input" type="radio" name="cur-tab" id="cur-tab-{i}"{" checked" if i == 1 else ""}>' for i in range(1, 8))
    nav = "\n".join(f'        <label class="tab-btn" for="cur-tab-{i}" role="tab">{e(n)}</label>' for i, (n, _) in enumerate(tabs, 1))
    panels = "\n".join(f'      <section class="tab-panel tab-{i}" role="tabpanel" aria-label="{e(n)}">{body}\n      </section>' for i, (n, body) in enumerate(tabs, 1))
    script = (Path(__file__).with_name("curriculum_page_script.html")).read_text(encoding="utf-8")
    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>UAV Student — Учебная программа</title>
  <link rel="stylesheet" href="curriculum.css">
</head>
<body>
  <div class="wrap">
    <header class="hero">
      <h1>UAV Student — Учебная программа</h1>
      <p class="muted">Обзор курса для администрации и разработчиков: состав, оценивание, проекты, стандарты и состояние планов. Для студентов — <a href="{SITE}">сайт курса</a>.</p>
      <p>
        <span class="tag">{n_mod} модулей</span>
        <span class="tag">{hours} учебных часов</span>
        <span class="tag">{len(tracks)} треков · {len(cur['paths'])} пути по прошивкам</span>
        <span class="tag">{len(proj)} проектов портфолио</span>
      </p>
    </header>

    <div class="tabs">
{inputs}

      <nav class="tab-nav" role="tablist" aria-label="Разделы программы">
{nav}
      </nav>
{panels}
    </div>
  </div>

{script}"""


def main() -> None:
    OUT.write_text(render(collect()), encoding="utf-8")
    print(f"curriculum page: {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
