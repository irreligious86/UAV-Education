#!/usr/bin/env python3
"""Fail the build when Markdown leaks into the published HTML as raw text.

A table that the renderer did not recognise shows up as one long paragraph of pipes and dashes;
an unclosed ** or a stray ### shows up literally. Readers see garbage, CI stays green — unless this
check runs. It scans the text of generated pages (outside <pre>, <code>, <script>, <style>, <svg>)
for Markdown syntax that should never survive rendering.

On lesson pages (<article data-module-page>) it also checks that every section heading carries a stable id from
the build (content_pipeline.assign_heading_ids): the anchor of notes, bookmarks, history and feedback.
"""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRS = ("m", "ref", "pages", "cap", "path", "projects", "quiz")
sys.path.insert(0, str(ROOT / "scripts"))
import i18n  # noqa: E402
DIRS = DIRS + tuple(f"{l['dir']}/{d}" for l in i18n.LANGS if l["dir"] for d in DIRS)   # every language tree
SKIP = {"pre", "code", "script", "style", "svg", "textarea", "template"}
PATTERNS = [
    (re.compile(r"\|\s*:?-{3,}:?\s*\|"), "table separator row rendered as text (|---|)"),
    (re.compile(r"\|\s[^|\n]{1,80}\s\|\s[^|\n]{1,80}\s\|\s[^|\n]{1,80}\s\|"), "pipe-delimited row rendered as text"),
    (re.compile(r"(?<![\w*])\*\*[^*\n]+\*\*(?![\w*])"), "unrendered **bold**"),
    (re.compile(r"(?:^|\s)#{2,4} \S"), "unrendered Markdown heading"),
    (re.compile(r"```"), "unrendered code fence"),
    (re.compile(r"\{\{(?:diagram|widget):"), "unrendered {{diagram/widget}} tag"),
]


class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self.depth += 1

    def handle_endtag(self, tag):
        if tag in SKIP and self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if not self.depth:
            self.chunks.append(data)


HEAD_ID = re.compile(r"^[a-z0-9-]{1,60}$")        # fits the server's anchor check (0007) with a "-copy-N" suffix


VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class Sections(HTMLParser):
    """Section headings as assets/history.js headings() selects them: h2, h3, h4.md-subheading that are descendants of
    .module-body (nested elements such as <article class="diag-item"> included). Parsed independently of the build's
    own region finder (content_pipeline.module_body_span), so a mistake there shows up here."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool]] = []   # open elements: (tag, is it or an ancestor .module-body)
        self.heads: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get("class") or "").split()
        inside = bool(self.stack and self.stack[-1][1])
        if inside and (tag in ("h2", "h3") or (tag == "h4" and "md-subheading" in cls)):
            self.heads.append((tag, a.get("id") or ""))
        if tag not in VOID:
            self.stack.append((tag, inside or "module-body" in cls))

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag in VOID or all(t != tag for t, _ in self.stack):
            return
        while self.stack and self.stack.pop()[0] != tag:   # an implicitly closed <p>/<li> closes with its parent
            pass


def heading_errors(html_text: str) -> list[str]:
    if "data-module-page" not in html_text:
        return []
    from content_pipeline import LEGACY_ANCHOR_RE
    p = Sections()
    p.feed(html_text)
    out, seen = [], set()
    for tag, hid in p.heads:
        if not hid or not HEAD_ID.match(hid) or LEGACY_ANCHOR_RE.match(hid):
            out.append(f"section heading <{tag}> without a stable build id ({hid or 'none'})")
        elif hid in seen:
            out.append(f"duplicate heading id {hid}")
        seen.add(hid)
    return out


def main() -> int:
    errors = []
    pages = 0
    for d in DIRS:
        for f in sorted((ROOT / d).glob("*.html")) if (ROOT / d).is_dir() else []:
            pages += 1
            p = Text()
            src = f.read_text(encoding="utf-8")
            p.feed(src)
            errors += [f"{f.relative_to(ROOT)}: {e}" for e in heading_errors(src)]
            text = " ".join(p.chunks)
            for rx, what in PATTERNS:
                m = rx.search(text)
                if m:
                    errors.append(f"{f.relative_to(ROOT)}: {what}: …{text[max(0, m.start() - 30):m.end() + 30].strip()}…")
    for e in errors:
        print(e, file=sys.stderr)
    print(f"check_rendering: {pages} pages, {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
