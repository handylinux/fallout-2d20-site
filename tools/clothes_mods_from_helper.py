#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clothes_mods_from_helper — какие модификации поддерживает одежда.

В Companion у одежды (`clothes.json`) есть только `specialEffects`, списка
модов нет. Совместимость одежды с модами описана в helper —
`back/src/db/seed/data/itemModCompatibility.ts`, `CLOTHING_COMPATIBILITY`:
какие вещи поддерживают «Tissu balistique» (баллистическое плетение) и
подкладки комбинезона Убежища. Сами моды уже лежат в данных Companion как
`uniq_armor_mods.json` (`costumeUniqueMods`, `vaultSuitUniqueMods`).

Скрипт пишет `data/companion/equipment/clothes_mods.json`:
    {"clothing_vault_jumpsuit": {"ТКАНЕВАЯ ОСНОВА": ["uniq_weave_ballistic", …],
                                 "ПОДКЛАДКА КОМБИНЕЗОНА": ["uniq_vaultsuit_…"]}}

Запуск:
    python3 tools/clothes_mods_from_helper.py /tmp/helper
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# имя вещи в helper (CLOTHING_COMPATIBILITY) → id в clothes.json
ITEM_IDS = {
    "Military Fatigues": "clothing_military_fatigues",
    "Casual Clothes": "clothing_casual_clothes",
    "Sturdy Clothes": "clothing_sturdy_clothes",
    "Leather Clothes": "clothing_road_leathers",
    "Brotherhood of Steel Uniform": "clothing_bos_uniform",
    "Fancy Clothes": "clothing_fancy_clothes",
    "Casual Hat": "headwear_casual_hat",
    "Fancy Hat": "headwear_fancy_hat",
    "Vault Jumpsuit": "clothing_vault_jumpsuit",
}
# константа helper → (подпись строки, категория модов Companion)
MOD_GROUPS = {
    "BALLISTIC_WEAVE": ("ТКАНЕВАЯ ОСНОВА", "costumeUniqueMods"),
    "VAULT_SUIT_MODS": ("ПОДКЛАДКА КОМБИНЕЗОНА", "vaultSuitUniqueMods"),
}


def compat_from_ts(text: str) -> dict[str, list[str]]:
    """CLOTHING_COMPATIBILITY: {вещь: [константы/имена модов]}."""
    start = text.index("export const CLOTHING_COMPATIBILITY")
    end = text.index("];", start)
    body = text[start:end]
    out: dict[str, list[str]] = {}
    # запись бывает двух видов: `modNames: BALLISTIC_WEAVE` (имя константы)
    # и `modNames: [...VAULT_SUIT_MODS, ...BALLISTIC_WEAVE]`
    pattern = re.compile(
        r"\{ itemName: '((?:[^'\\]|\\.)*)', modNames: (.+?) \},", re.S)
    for match in pattern.finditer(body):
        name = match.group(1).replace("\\'", "'")
        spec = match.group(2)
        mods = [m.replace("\\'", "'") for m in
                re.findall(r"'((?:[^'\\]|\\.)*)'", spec)]
        mods += re.findall(r"\.\.\.(BALLISTIC_WEAVE|VAULT_SUIT_MODS)", spec)
        bare = re.fullmatch(r"(BALLISTIC_WEAVE|VAULT_SUIT_MODS)", spec.strip())
        if bare:
            mods.append(bare.group(1))
        out[name] = mods
    return out


def build(compat: dict[str, list[str]], unique_mods: list[dict]
          ) -> dict[str, dict[str, list[str]]]:
    by_category: dict[str, list[str]] = {}
    for mod in unique_mods:
        by_category.setdefault(mod.get("modCategory", ""), []).append(mod["id"])
    out: dict[str, dict[str, list[str]]] = {}
    for name, consts in compat.items():
        item_id = ITEM_IDS.get(name)
        if not item_id:
            continue
        groups: dict[str, list[str]] = {}
        for const in consts:
            if const not in MOD_GROUPS:
                continue
            label, category = MOD_GROUPS[const]
            ids = by_category.get(category) or []
            if ids:
                groups[label] = ids
        if groups:
            out[item_id] = groups
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("helper", help="путь к клону Fallout-2d20-helper")
    ap.add_argument("--data", default=str(ROOT / "data" / "companion"))
    args = ap.parse_args(argv)

    text = (Path(args.helper) / "back/src/db/seed/data/itemModCompatibility.ts"
            ).read_text(encoding="utf-8")
    equipment = Path(args.data) / "equipment"
    unique = json.loads((equipment / "uniq_armor_mods.json")
                        .read_text(encoding="utf-8"))
    clothes = json.loads((equipment / "clothes.json").read_text(encoding="utf-8"))

    out = build(compat_from_ts(text), unique)
    known = {item["id"] for group in clothes["clothes"] for item in group["items"]}
    out = {key: value for key, value in out.items() if key in known}
    (equipment / "clothes_mods.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"предметов одежды с модами: {len(out)} из {len(known)}")
    for item_id, groups in out.items():
        print("  " + item_id + ": " + ", ".join(
            f"{label} × {len(ids)}" for label, ids in groups.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
