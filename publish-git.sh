#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 scripts/publish.py

git add index.html data/content-manifest.json content data scripts curriculum curriculum/curriculum.html 2>/dev/null || true
if git commit -m "content: update generated site content" 2>/dev/null; then
  git push || echo "Внимание: push не выполнен — проверьте remote."
else
  echo "Внимание: коммит не выполнен (нет изменений или нет git репозитория)."
fi
