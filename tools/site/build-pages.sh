#!/usr/bin/env bash
# Сборка нового каркаса и публикация в ветку gh-pages (docs/).
set -euo pipefail
cd "$(dirname "$0")/../.."

BASE_PATH="/fallout-2d20-site"

rm -rf site
BASE="$BASE_PATH" python3 tools/site/build_site.py

rm -rf docs
mkdir -p docs
cp -a site/. docs/
touch docs/.nojekyll

echo "готово: site/ + docs/ (BASE=$BASE_PATH)"
