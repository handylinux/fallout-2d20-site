#!/usr/bin/env bash
# Обновить data/companion из локального клона Fallout-2d20-companion.
#
#   git clone https://github.com/rpg-companios/Fallout-2d20-companion.git /tmp/companion
#   tools/sync_companion_data.sh /tmp/companion
set -euo pipefail

src=${1:?укажите путь к клонированному Fallout-2d20-companion}
root=$(cd "$(dirname "$0")/.." && pwd)
dst="$root/data/companion"

mkdir -p "$dst/equipment" "$dst/i18n/ru-RU/data/equipment/armor"

for file in armor.json powerArmor.json armor_mods.json uniq_armor_mods.json armor_effects.json categories.json; do
  cp "$src/modules/fallout/data/equipment/$file" "$dst/equipment/$file"
done

for file in armor.json powerArmor.json armor_mods.json uniq_armor_mods.json armor_effects.json; do
  cp "$src/modules/fallout/i18n/ru-RU/data/equipment/armor/$file" \
     "$dst/i18n/ru-RU/data/equipment/armor/$file"
done

echo "обновлено: $dst"
