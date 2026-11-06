#!/usr/bin/env bash
# Validate content and rebuild index.html. Commit and push manually (CI re-checks on push).
set -euo pipefail
cd "$(dirname "$0")"
python3 scripts/publish.py
echo "OK: index.html rebuilt. Next: git add -A && git commit && git push"
