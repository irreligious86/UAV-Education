#!/usr/bin/env python3
"""Fail the build when Markdown leaks into the published HTML as raw text.

A table that the renderer did not recognise shows up as one long paragraph of pipes and dashes;
an unclosed ** or a stray ### shows up literally. Readers see garbage, CI stays green — unless this
check runs. It scans the text of generated pages (outside <pre>, <code>, <script>, <style>, <svg>)
for Markdown syntax that should never survive rendering.
"""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRS = ("m", "ref", "pages", "cap", "path", "projects", "quiz")
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


def main() -> int:
    errors = []
    pages = 0
    for d in DIRS:
        for f in sorted((ROOT / d).glob("*.html")) if (ROOT / d).is_dir() else []:
            pages += 1
            p = Text()
            p.feed(f.read_text(encoding="utf-8"))
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
