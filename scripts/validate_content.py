#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка манифеста и .md. Запуск: python scripts/validate_content.py"""
from __future__ import annotations

import json
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
PRACTICE_MIN_WORDS = 150


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


VALID_STATUSES = ("published", "planned", "draft")

# Fragments of the stub template. A published article containing any of them
# is a placeholder pretending to be content — fail the build.
PLACEHOLDER_MARKERS = (
    "example.com",
    "(черновик)",
    "Заглушка",
    "заменить конкретной ссылкой",
)

# A published article must have at least this many non-empty body lines.
MIN_PUBLISHED_LINES = 25


def validate_statuses(manifest):
    errors = []
    for sec in manifest.get("sections", []):
        for art in sec.get("articles", []):
            st = art.get("status")
            if st not in VALID_STATUSES:
                errors.append(
                    f"{art.get('id')}: неизвестный status «{st}» (допустимо: {', '.join(VALID_STATUSES)})"
                )
    return errors


def validate_front_matter_status(md_path, manifest_status):
    """Front matter status must match the manifest (manifest is the source of truth)."""
    if manifest_status is None:
        return []
    fm = _parse_front_matter(md_path.read_text(encoding="utf-8"))
    if not fm:
        return []
    m = re.search(r"^status:\s*(\S+)", fm, re.MULTILINE)
    if m and m.group(1) != manifest_status:
        rel = md_path.relative_to(ROOT)
        return [f"{rel}: status в front matter «{m.group(1)}» ≠ манифест «{manifest_status}»"]
    return []


WIDGET_LINE = re.compile(r"^\{\{widget:([a-z0-9-]+)\}\}$", re.MULTILINE)


def validate_widgets(md_path):
    if str(Path(__file__).resolve().parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
    from content_pipeline import WIDGETS

    text = md_path.read_text(encoding="utf-8")
    rel = md_path.relative_to(ROOT)
    return [f"{rel}: неизвестный виджет «{n}» (есть: {', '.join(sorted(WIDGETS))})" for n in WIDGET_LINE.findall(text) if n not in WIDGETS]


DIAGRAM_LINE = re.compile(r"^\{\{diagram:([^}]*)\}\}$", re.MULTILINE)
DIAGRAMS_DIR = ROOT / "assets" / "diagrams"


def validate_diagrams(md_path):
    errs = []
    text = md_path.read_text(encoding="utf-8")
    rel = md_path.relative_to(ROOT)
    for body in DIAGRAM_LINE.findall(text):
        if "|" not in body:
            errs.append(f"{rel}: диаграмма «{body}» без подписи (формат {{{{diagram:id|Подпись}}}})")
            continue
        name, caption = body.split("|", 1)
        if not re.fullmatch(r"[a-z0-9-]+", name):
            errs.append(f"{rel}: неверный id диаграммы «{name}»")
        elif not (DIAGRAMS_DIR / f"{name}.svg").is_file():
            errs.append(f"{rel}: нет файла assets/diagrams/{name}.svg")
        if not caption.strip():
            errs.append(f"{rel}: пустая подпись у диаграммы «{name}»")
    return errs


def validate_published_sections(md_path, published):
    if not published:
        return []
    text = md_path.read_text(encoding="utf-8")
    raw_body = _markdown_body(text)
    body = raw_body.lower()
    errors = []
    rel = md_path.relative_to(ROOT)
    for sec in REQUIRED_MD_HEADINGS:
        token = f"## {sec}"
        if token not in body:
            errors.append(f"{rel}: нет секции «{token}» (обязательно для published)")
    for marker in PLACEHOLDER_MARKERS:
        if marker.lower() in text.lower():
            errors.append(f"{rel}: published-статья содержит заглушку «{marker}» — допиши или поставь status: planned")
    # practice must teach, not just list steps: at least PRACTICE_MIN_WORDS of prose (code blocks excluded)
    pm = re.search(r"^## practice\n(.*?)(?=^## |\Z)", raw_body, re.M | re.S)
    if pm:
        prose = re.sub(r"```.*?```", "", pm.group(1), flags=re.S)
        n = len(prose.split())
        if n < PRACTICE_MIN_WORDS:
            errors.append(f"{rel}: в «## practice» {n} слов прозы без кода (< {PRACTICE_MIN_WORDS}); добавь ожидаемые результаты, что записать и критерии зачёта")
    m = re.search(r"^## references\n(.*?)(?=^## |\Z)", raw_body, re.M | re.S)
    if m:
        refs = [ln for ln in m.group(1).splitlines() if ln.strip()]
        bad = [ln for ln in refs if not re.match(r"- .+ \| https?://\S+ \| (primary|secondary) \| [ABC]$", ln.strip())]
        if bad:
            errors.append(f"{rel}: references must be '- Title | URL | primary|secondary | A|B|C' lines; bad: {bad[0][:80]}")
        if len(refs) < 2:
            errors.append(f"{rel}: fewer than 2 references")
    # tables: every row must have the header's number of cells, or the reader gets shifted columns
    from content_pipeline import TABLE_SEP_RE, split_table_row
    body_lines = raw_body.splitlines()
    for i in range(len(body_lines) - 1):
        hdr, sep = body_lines[i].strip(), body_lines[i + 1].strip()
        if hdr.startswith("|") and TABLE_SEP_RE.match(sep):
            n = len(split_table_row(hdr))
            if len(split_table_row(sep)) != n:
                errors.append(f"{rel}: table separator has {len(split_table_row(sep))} cells, header {n}: {hdr[:60]}")
            j = i + 2
            while j < len(body_lines) and body_lines[j].strip().startswith("|"):
                k = len(split_table_row(body_lines[j]))
                if k != n:
                    errors.append(f"{rel}: table row has {k} cells, header {n}: {body_lines[j].strip()[:60]}")
                j += 1
    lines = [ln for ln in raw_body.splitlines() if ln.strip()]
    if len(lines) < MIN_PUBLISHED_LINES:
        errors.append(
            f"{rel}: published-статья слишком короткая ({len(lines)} строк < {MIN_PUBLISHED_LINES})"
        )
    return errors


CURRICULUM_PATH = ROOT / "data" / "curriculum.json"


def validate_curriculum(manifest_ids):
    """curriculum.json must be consistent with itself and with the manifest."""
    import json

    if not CURRICULUM_PATH.is_file():
        return ["нет data/curriculum.json"]
    cur = json.loads(CURRICULUM_PATH.read_text(encoding="utf-8"))
    errors = []
    groups = cur.get("tracks", []) + cur.get("electives", [])
    ids = [m["id"] for g in groups for m in g.get("modules", [])]
    seen = set()
    for i in ids:
        if i in seen:
            errors.append(f"curriculum: модуль «{i}» встречается дважды")
        seen.add(i)
    for g in groups:
        for m in g.get("modules", []):
            for k in ("id", "title", "level"):
                if k not in m:
                    errors.append(f"curriculum: у модуля {m.get('id', '?')} нет «{k}»")
            for p in m.get("prerequisites", []):
                if p not in seen:
                    errors.append(f"curriculum: {m['id']} → prerequisite «{p}» не найден")
            if m.get("article") and m["article"] not in manifest_ids:
                errors.append(f"curriculum: {m['id']} ссылается на статью «{m['article']}», которой нет в манифесте")
            if not m.get("article") and m["id"] in manifest_ids:
                errors.append(f"curriculum: {m['id']} есть в манифесте — укажи \"article\": \"{m['id']}\"")
    # a prerequisite from the same track must come earlier in that track
    for g in groups:
        order = {m["id"]: k for k, m in enumerate(g.get("modules", []))}
        for m in g.get("modules", []):
            for p in m.get("prerequisites", []):
                if p in order and order[p] > order[m["id"]]:
                    errors.append(f"curriculum: {m['id']} стоит раньше своего prerequisite «{p}» в треке {g.get('id', '?')}")
    for g in cur.get("tracks", []):
        for m in g.get("modules", []):
            lab = m.get("lab")
            if lab is not None and (not isinstance(lab, dict) or not lab.get("title") or len(lab.get("criteria", [])) < 2):
                errors.append(f"curriculum: {m['id']} — lab должен иметь title и ≥2 criteria")
        cap = g.get("capstone")
        if cap:
            for k in ("id", "title", "result", "deliverables", "criteria"):
                if not cap.get(k):
                    errors.append(f"curriculum: capstone трека {g['id']} — нет «{k}»")
    for p in cur.get("paths", []):
        pseen = set()
        for st in p.get("stages", []):
            for mid in st.get("modules", []):
                if mid not in seen:
                    errors.append(f"curriculum: path {p['id']} → модуль «{mid}» не найден")
                if mid in pseen:
                    errors.append(f"curriculum: path {p['id']} → модуль «{mid}» дважды")
                pseen.add(mid)
    for mid in sorted(set(manifest_ids) - seen):
        errors.append(f"curriculum: статья «{mid}» из манифеста не размещена ни в одном треке/элективе")
    return errors


QUIZ_DIR = ROOT / "content" / "quiz"
QUIZ_MIN_QUESTIONS = 5


QUIZ_MAX_LONGEST_SHARE = 0.34


def validate_quizzes(manifest_ids, status_by_id):
    """Every quiz bank must be well-formed and belong to a published module."""
    import json

    errors = []
    if not QUIZ_DIR.is_dir():
        return errors
    for path in sorted(QUIZ_DIR.glob("*.json")):
        rel = path.relative_to(ROOT)
        try:
            bank = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"{rel}: невалидный JSON ({e})")
            continue
        mid = path.stem
        if bank.get("module") != mid:
            errors.append(f"{rel}: поле module «{bank.get('module')}» ≠ имени файла «{mid}»")
        if mid not in manifest_ids:
            errors.append(f"{rel}: модуля «{mid}» нет в манифесте")
        elif status_by_id.get(mid) != "published":
            errors.append(f"{rel}: квиз для неопубликованного модуля")
        qs = bank.get("questions", [])
        if len(qs) < QUIZ_MIN_QUESTIONS:
            errors.append(f"{rel}: {len(qs)} вопросов < {QUIZ_MIN_QUESTIONS}")
        for i, q in enumerate(qs, 1):
            opts = q.get("options", [])
            if not q.get("q") or len(opts) < 3:
                errors.append(f"{rel}: вопрос {i} — нет текста или меньше 3 вариантов")
                continue
            ans = q.get("answer")
            if not isinstance(ans, int) or not 0 <= ans < len(opts):
                errors.append(f"{rel}: вопрос {i} — answer вне диапазона")
            if not q.get("explain"):
                errors.append(f"{rel}: вопрос {i} — нет объяснения")
            if len(set(opts)) != len(opts):
                errors.append(f"{rel}: вопрос {i} — повторяющиеся варианты")
            if q.get("kind") not in (None, "apply"):
                errors.append(f"{rel}: вопрос {i} — неизвестный kind «{q.get('kind')}»")
            if q.get("kind") == "apply" and not q.get("fragment"):
                errors.append(f"{rel}: вопрос {i} — kind=apply без fragment")
            if q.get("fragment") is not None and (not isinstance(q["fragment"], str) or len(q["fragment"]) > 1500):
                errors.append(f"{rel}: вопрос {i} — fragment должен быть строкой ≤ 1500 символов")
        # "pick the longest answer" must not work: the correct option may be the unique longest one
        # in at most a third of a bank's questions (chance level for 4 options is ~25-28 %)
        longest = 0
        for q in qs:
            L = [len(o) for o in q.get("options", [])]
            a = q.get("answer")
            if L and isinstance(a, int) and 0 <= a < len(L) and L[a] == max(L) and L.count(max(L)) == 1:
                longest += 1
        if qs and longest / len(qs) > QUIZ_MAX_LONGEST_SHARE:
            errors.append(f"{rel}: верный вариант — самый длинный в {longest} из {len(qs)} вопросов "
                          f"(> {QUIZ_MAX_LONGEST_SHARE:.0%}); выровняйте дистракторы по длине и конкретике")
    return errors


GLOSSARY_PATH = ROOT / "data" / "glossary.json"


def validate_glossary(manifest_ids):
    import json

    if not GLOSSARY_PATH.is_file():
        return []
    data = json.loads(GLOSSARY_PATH.read_text(encoding="utf-8"))
    errors, seen = [], set()
    for t in data.get("terms", []):
        if not t.get("term") or not t.get("def"):
            errors.append(f"glossary: запись без term/def: {t}")
        key = t.get("term", "").lower()
        if key in seen:
            errors.append(f"glossary: термин «{t['term']}» дублируется")
        seen.add(key)
        if t.get("module") and t["module"] not in manifest_ids:
            errors.append(f"glossary: «{t['term']}» ссылается на несуществующий модуль {t['module']}")
    # every module contributes at least one term, so the glossary keeps up with the course
    covered = {t.get("module") for t in data.get("terms", [])}
    for mid in sorted(set(manifest_ids) - covered):
        errors.append(f"glossary: у модуля {mid} нет ни одного термина")
    return errors


def validate_projects(manifest_ids, track_ids):
    """data/projects.json: ids, numbering, capstone target, diagram file, starter path, linked modules."""
    path = ROOT / "data" / "projects.json"
    if not path.is_file():
        return []
    errs = []
    data = json.loads(path.read_text(encoding="utf-8"))
    seen, nums = set(), set()
    for p in data.get("projects", []):
        pid = p.get("id", "?")
        where = f"projects.json:{pid}"
        if not re.fullmatch(r"proj-[a-z0-9-]+", pid):
            errs.append(f"{where}: id must match proj-[a-z0-9-]+")
        if pid in seen or pid in manifest_ids:
            errs.append(f"{where}: duplicate id")
        seen.add(pid)
        if p.get("num") in nums:
            errs.append(f"{where}: duplicate num {p.get('num')}")
        nums.add(p.get("num"))
        for k in ("title", "summary", "stack", "milestones", "acceptance", "deliverables", "autotest", "diagram"):
            if not p.get(k):
                errs.append(f"{where}: missing {k}")
        if p.get("capstoneFor") and p["capstoneFor"] not in track_ids:
            errs.append(f"{where}: capstoneFor '{p['capstoneFor']}' is not a track id")
        if p.get("diagram") and not (DIAGRAMS_DIR / f"{p['diagram']}.svg").is_file():
            errs.append(f"{where}: diagram assets/diagrams/{p['diagram']}.svg not found")
        if p.get("starter") and not (ROOT / p["starter"]).is_dir():
            errs.append(f"{where}: starter {p['starter']} does not exist")
        if p.get("status") == "starter" and not p.get("starter"):
            errs.append(f"{where}: status 'starter' without a starter path")
        for mid in p.get("modules", []):
            if mid not in manifest_ids:
                errs.append(f"{where}: unknown module {mid}")
        checks = p.get("checks")
        if checks is not None:
            if len(checks) != len(p.get("milestones", [])):
                errs.append(f"{where}: checks must have one entry (command or null) per milestone")
            for c in checks:
                m = re.match(r"(?:pytest|python) (examples/[\w./-]+)", c or "")
                if c and not (m and (ROOT / m.group(1)).exists()):
                    errs.append(f"{where}: check '{c}' does not point to an existing examples/ path")
        if p.get("stretch") is not None and not all(isinstance(x, str) and x for x in p["stretch"]):
            errs.append(f"{where}: stretch must be a list of non-empty strings")
    for i, r in enumerate(data.get("rubric", [])):
        if not r.get("criterion") or len(r.get("levels", [])) != 3:
            errs.append(f"projects.json: rubric[{i}] needs a criterion and exactly 3 levels")
    return errs


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

    errs.extend(validate_statuses(manifest))
    errs.extend(validate_curriculum(all_ids_set))
    status_by_id = {a["id"]: a.get("status") for sec in manifest.get("sections", []) for a in sec.get("articles", [])}
    errs.extend(validate_quizzes(all_ids_set, status_by_id))
    errs.extend(validate_glossary(all_ids_set))
    track_ids = {t["id"] for t in json.loads((ROOT / "data" / "curriculum.json").read_text(encoding="utf-8")).get("tracks", [])}
    errs.extend(validate_projects(all_ids_set, track_ids))

    status_by_file = {}
    for sec in manifest.get("sections", []):
        for art in sec.get("articles", []):
            rel = art.get("sourceFile")
            if not rel:
                continue
            status_by_file[ROOT / rel] = art.get("status")

    for p in (ROOT / "content").rglob("*.md"):
        if p.name.upper() == "README.MD" or p.name == "article-template.md":
            continue
        errs.extend(validate_related_in_frontmatter(p, all_ids_set))
        errs.extend(validate_widgets(p))
        errs.extend(validate_diagrams(p))
        st = status_by_file.get(p)
        errs.extend(validate_front_matter_status(p, st))
        errs.extend(validate_published_sections(p, st == "published"))

    if errs:
        print("Ошибки валидации:\n", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    counts = {}
    for st in status_by_file.values():
        counts[st] = counts.get(st, 0) + 1
    print("validate_content: OK")
    print(f"  статей в манифесте: {len(ids)}")
    print("  " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
    if QUIZ_DIR.is_dir():
        print(f"  квизов: {len(list(QUIZ_DIR.glob('*.json')))}")


if __name__ == "__main__":
    main()
