#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 scripts/publish.py
echo "Готово. При необходимости: git add / commit / push вручную."
