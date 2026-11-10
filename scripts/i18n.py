"""Site languages and translation catalogs (gettext style: the Russian source string is the key).

Layout (docs/I18N.md):
  i18n/languages.json                       languages; the first one is the source language, built at the site root
  i18n/<lang>/ui.json                       {"<ru string>": "<translation>"} for the interface (build scripts, JS, diagrams)
  i18n/<lang>/data.json                     the same for text values in data/*.json and the curriculum
  i18n/<lang>/content/<path>.md             a translated module; front matter `source_hash` = hash of the ru source
  i18n/<lang>/content/quiz|tasks/<id>.json  translated quiz / task banks (same shape as the source)
  i18n/<lang>/content/pages/<name>.html     translated hand-written pages

Anything without a translation falls back to the source text, so a partly translated language always builds.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "i18n"

LANGS: list[dict] = json.loads((I18N / "languages.json").read_text(encoding="utf-8"))["languages"]
SOURCE = LANGS[0]["code"]
BY_CODE = {l["code"]: l for l in LANGS}

_lang = SOURCE
_catalogs: dict[str, dict[str, str]] = {}
missing: dict[str, set[str]] = {}          # lang -> source strings looked up without a translation
PLACEHOLDER = re.compile(r"\{[a-z_][a-z0-9_]*\}")


def _load(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if isinstance(v, str) and v.strip() and not k.startswith("@")}


def chain(lang: str) -> list[str]:
    """The language and its fallbacks, nearest first, without the source: ["uk-galych", "uk"]."""
    out = []
    while lang and lang != SOURCE and lang not in out:
        out.append(lang)
        lang = BY_CODE[lang].get("fallback")
    return out


def own_catalog(lang: str, name: str = "ui") -> dict[str, str]:
    return {} if lang == SOURCE else _load(I18N / lang / f"{name}.json")


def catalog(lang: str, name: str = "ui") -> dict[str, str]:
    """Translations of `lang` merged over its fallback languages' (a dialect inherits its standard language)."""
    key = f"{lang}/{name}"
    if key not in _catalogs:
        merged: dict[str, str] = {}
        for code in reversed(chain(lang)):
            merged.update(own_catalog(code, name))
        _catalogs[key] = merged
    return _catalogs[key]


def set_lang(code: str) -> None:
    global _lang
    if code not in BY_CODE:
        raise SystemExit(f"unknown language {code}")
    _lang = code


def lang() -> str:
    return _lang


def lang_dir(code: str | None = None) -> str:
    """'' for the source language, 'uk' for Ukrainian, ... (the URL prefix of the language tree)."""
    return BY_CODE[code or _lang]["dir"]


def up() -> str:
    """Extra '../' from a page of the current language tree to the repository root (shared assets)."""
    d = lang_dir()
    return "../" * (d.count("/") + 1) if d else ""


used: set[str] = set()                      # every interface string looked up by the build (any language)


def _(s: str, **kw) -> str:
    """Translate an interface string; {name} placeholders are filled from kw after translating."""
    used.add(s)
    out = s
    if _lang != SOURCE:
        t = catalog(_lang).get(s)
        if t is None:
            missing.setdefault(_lang, set()).add(s)
        else:
            out = t
    return out.format(**kw) if kw else out


def tr(s: str, name: str) -> str:
    """Translate one string through the catalog `name` (diagrams, data); records it as used."""
    used_by.setdefault(name, set()).add(s)
    return s if _lang == SOURCE else catalog(_lang, name).get(s, s)


used_by: dict[str, set[str]] = {}


def tr_data(value, name: str = "data"):
    """Translate every string inside a JSON value through the data catalog (keys and ids are untouched)."""
    if _lang == SOURCE:
        return value
    cat = catalog(_lang, name)
    def walk(v, key=None):
        if isinstance(v, str):
            if key in NON_TEXT_KEYS:
                return v
            return cat.get(v, v)
        if isinstance(v, list):
            return [walk(x, key) for x in v]
        if isinstance(v, dict):
            return {k: walk(x, k) for k, x in v.items()}
        return v
    return walk(value)


# JSON keys whose string values are identifiers, paths or code, never prose
NON_TEXT_KEYS = {"id", "module", "modules", "prerequisites", "sourceFile", "stack", "stacks", "status", "level", "url",
                 "diagram", "starter", "capstoneFor", "sectionKey", "key", "related", "expr", "answer", "checks",
                 "firmware", "tags", "readingTime", "kind", "group", "ids", "capstones", "autotest_cmd"}


def source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


import os as _os

# UAV_I18N_ALLOW=<file with repo-relative paths>: only those translation files count (used to commit a
# consistent snapshot while other translations are still being written). Unset: every file counts.
_ALLOW = None
if _os.environ.get("UAV_I18N_ALLOW"):
    _ALLOW = {ln.strip() for ln in Path(_os.environ["UAV_I18N_ALLOW"]).read_text(encoding="utf-8").splitlines() if ln.strip()}


def own_translated_path(src: Path, code: str | None = None) -> Path:
    """i18n/<lang>/content/... counterpart of content/... for exactly this language (no fallback)."""
    p = I18N / (code or _lang) / src.resolve().relative_to(ROOT)
    if _ALLOW is not None and p.relative_to(ROOT).as_posix() not in _ALLOW:
        return I18N / "_not_in_snapshot" / p.relative_to(I18N)
    return p


def translated_path(src: Path, code: str | None = None) -> Path:
    """The nearest existing translation along the fallback chain; the language's own path if there is none."""
    for c in chain(code or _lang):
        p = own_translated_path(src, c)
        if p.is_file():
            return p
    return own_translated_path(src, code)


def placeholders(s: str) -> set[str]:
    return set(PLACEHOLDER.findall(s))


# ------------------------------------------------------------------ static HTML fragments
_TEXT_RE = re.compile(r">([^<>]*[^\s<>][^<>]*)<")
_ATTR_RE = re.compile(r'\b(placeholder|aria-label|title|alt|data-done-label|data-done-past)="([^"]*)"')


def tr_html(fragment: str) -> str:
    """Translate the text nodes and the human-readable attributes of a static HTML fragment.
    Each text node (whitespace-trimmed) is one catalog key, e.g. ">Почта <" -> "Почта"."""
    if _lang == SOURCE:
        return fragment

    def node(m):
        raw = m.group(1)
        s = raw.strip()
        if not re.search(r"[А-Яа-яЁёІіЇїЄєҐґ]", s):
            return m.group(0)
        lead = raw[: len(raw) - len(raw.lstrip())]
        trail = raw[len(raw.rstrip()):]
        return ">" + lead + _(s) + trail + "<"

    def attr(m):
        v = m.group(2)
        if not re.search(r"[А-Яа-яЁё]", v):
            return m.group(0)
        return f'{m.group(1)}="{_(v)}"'

    return _ATTR_RE.sub(attr, _TEXT_RE.sub(node, fragment))


if __name__ == "__main__":
    # `python scripts/i18n.py --dirs` prints the language tree directories (used by CI's freshness check)
    import sys
    if "--dirs" in sys.argv:
        print(" ".join([l["dir"] for l in LANGS if l["dir"]] + [o for l in LANGS for o in l.get("oldDirs", [])]))
