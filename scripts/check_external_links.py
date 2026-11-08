#!/usr/bin/env python3
"""Check every external URL the course cites (module references, resources, project data).

  python scripts/check_external_links.py [--out report.md] [--workers 8] [--timeout 20]

Not part of the per-push CI: external sites are slow, rate-limit and go down for an afternoon. A weekly
workflow runs it and opens an issue listing failures. Exit code is 0 unless --strict is given, so a
flaky site never blocks a content change.

Rules: HEAD first, GET on 403/405/501 (many servers refuse HEAD); a redirect chain that ends in 2xx is
OK; 429 and timeouts are reported as "flaky", not "dead"; a URL is "dead" on 404/410 or DNS failure.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL_RE = re.compile(r"https?://[^\s|)\"'<>`]+")
UA = "Mozilla/5.0 (compatible; uav-student-linkcheck/1.0)"


def collect() -> dict[str, set[str]]:
    """url -> set of files that cite it."""
    found: dict[str, set[str]] = {}

    def add(url: str, where: str) -> None:
        url = url.rstrip(".,;:")
        found.setdefault(url, set()).add(where)

    for f in sorted((ROOT / "content").rglob("*.md")):
        text = f.read_text(encoding="utf-8")
        m = re.search(r"^## references\n(.*?)(?=^## |\Z)", text, re.M | re.S)
        for url in URL_RE.findall(m.group(1) if m else ""):
            add(url, str(f.relative_to(ROOT)))
        for url in re.findall(r'^\s+url: "(https?://[^"]+)"', text, re.M):     # front-matter references
            add(url, str(f.relative_to(ROOT)))
    for f in sorted((ROOT / "content" / "pages").glob("*.html")):
        for url in URL_RE.findall(f.read_text(encoding="utf-8")):
            add(url, str(f.relative_to(ROOT)))
    for f in sorted((ROOT / "data").glob("*.json")):
        for url in URL_RE.findall(f.read_text(encoding="utf-8")):
            add(url, str(f.relative_to(ROOT)))
    return found


def probe(url: str, timeout: float) -> tuple[str, str]:
    """Return (verdict, detail): verdict in ok | dead | flaky."""
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return "ok", f"{r.status}"
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (400, 403, 405, 501):
                continue
            if e.code in (404, 410):
                return "dead", f"HTTP {e.code}"
            if e.code in (401, 403):
                return "flaky", f"HTTP {e.code} (blocks bots?)"
            return "flaky", f"HTTP {e.code}"
        except urllib.error.URLError as e:
            if isinstance(e.reason, socket.gaierror):
                return "dead", "DNS failure"
            return "flaky", f"{e.reason}"
        except (TimeoutError, socket.timeout):
            return "flaky", "timeout"
        except Exception as e:  # noqa: BLE001 — a link checker must never crash on one URL
            return "flaky", type(e).__name__
    return "flaky", "unreachable"


def report(results: dict[str, tuple[str, str]], cited: dict[str, set[str]]) -> str:
    dead = sorted(u for u, (v, _) in results.items() if v == "dead")
    flaky = sorted(u for u, (v, _) in results.items() if v == "flaky")
    out = [f"# External link check", "", f"{len(results)} URLs: {len(results) - len(dead) - len(flaky)} ok, "
           f"{len(dead)} dead, {len(flaky)} flaky.", ""]
    for title, urls in (("Dead (fix or replace)", dead), ("Flaky (check by hand)", flaky)):
        if urls:
            out += [f"## {title}", "", "| URL | Result | Cited in |", "|---|---|---|"]
            out += [f"| {u} | {results[u][1]} | {', '.join(sorted(cited[u]))} |" for u in urls]
            out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="")
    ap.add_argument("--json", default="", help="also write raw results as JSON")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--timeout", type=float, default=20)
    ap.add_argument("--list", action="store_true", help="only list collected URLs")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any URL is dead")
    a = ap.parse_args()
    cited = collect()
    if a.list:
        print("\n".join(sorted(cited)))
        print(f"{len(cited)} URLs", file=sys.stderr)
        return 0
    with cf.ThreadPoolExecutor(a.workers) as ex:
        results = dict(zip(cited, ex.map(lambda u: probe(u, a.timeout), cited)))
    text = report(results, cited)
    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8")
    if a.json:
        Path(a.json).write_text(json.dumps({u: list(v) for u, v in results.items()}, indent=1), encoding="utf-8")
    print(text.splitlines()[2])
    return 1 if a.strict and any(v == "dead" for v, _ in results.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
