#!/usr/bin/env python3
"""One command for authors: build diagrams, validate content, rebuild the site, check links.

  python scripts/publish.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
STEPS = ("diagrams/build_diagrams.py", "check_diagrams.py", "validate_content.py", "build_site.py", "check_i18n.py", "build_curriculum_page.py", "check_links.py", "check_rendering.py", "check_js.py")


def main() -> None:
    for step in STEPS:
        r = subprocess.run([sys.executable, str(SCRIPTS / step)], cwd=SCRIPTS.parent)
        if r.returncode != 0:
            raise SystemExit(r.returncode)
    print("Done. Open index.html in a browser, then commit and push.")


if __name__ == "__main__":
    main()
