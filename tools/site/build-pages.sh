#!/usr/bin/env bash
# Сборка каркаса и публикация в ветку gh-pages (docs/).
set -euo pipefail
cd "$(dirname "$0")/../.."

BASE_PATH="/fallout-2d20-site"

rm -rf site
DEMO=1 BASE="$BASE_PATH" python3 tools/site/build_site.py

rm -rf docs
mkdir -p docs
cp -a site/. docs/
touch docs/.nojekyll

# предрендер сам очищает и создаёт docs/ — иначе остались бы старые заглушки
BASE="$BASE_PATH" python3 tools/site/build_data.py
BASE="$BASE_PATH" node tools/site/prerender.js

echo "готово: site/ + docs/ (BASE=$BASE_PATH)"
