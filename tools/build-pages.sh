#!/usr/bin/env bash
# Сборка статики для GitHub Pages + синхронизация в docs/ (ветка gh-pages).
#
# Сайт публикуется по адресу https://handylinux.github.io/fallout-2d20-site/,
# поэтому все внутренние абсолютные пути получают префикс /fallout-2d20-site.
set -euo pipefail
cd "$(dirname "$0")/.."

BASE_PATH="/fallout-2d20-site"

# 1) обычная сборка (нужна как основа для страницы перков)
python3 tools/sitegen/build.py
cp public/perki/index.html public/perki/template.html
python3 tools/sitegen/perks.py

# 2) пересборка с префиксом пути
BASE="$BASE_PATH" python3 tools/sitegen/build.py
BASE="$BASE_PATH" python3 tools/sitegen/perks.py

rm -f public/perki/template.html

# 3) то же в docs/ — именно этот каталог уходит в ветку gh-pages
rm -rf docs
mkdir -p docs
cp -a public/. docs/
touch docs/.nojekyll

echo "готово: public/ и docs/ (BASE=$BASE_PATH)"
