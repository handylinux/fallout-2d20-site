#!/usr/bin/env python3
"""Build print-ready weapon cards from the Companion JSON.

The PDF renderer (tools/weapon2pdf.py) works on a *card*: a flat, already
translated description of one page.  This script produces those cards from
`data/companion/` so nothing is retyped by hand.

    companion JSON  →  card JSON  →  A4 PDF

Descriptions: Companion's RU `flavour` is English for most weapons (130 of
146), which is acceptable for now.  A future `data/weapons/descriptions.ru.json`
(`{"weapon_id": "текст"}`) overrides it without touching this script.

Usage:
    python3 tools/weapons2cards.py weapon_10mm_pistol --page 18 \
        --image assets/pdf/weapons/placeholder.png
    python3 tools/weapons2cards.py --all --image-dir assets/pdf/weapons
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMP = os.path.join(ROOT, "data", "companion")
RU = os.path.join(COMP, "i18n", "ru-RU", "data")

# Book order for the pages we have seen; the remaining slots (energy weapons,
# robots) are appended alphabetically.  A weapon only shows the slots that are
# actually present in weapon_mod_slots.json.
SLOT_ORDER = ["Receiver", "Barrel", "Capacitor", "Nozzle", "Grip", "Stock",
              "Magazine", "Sight", "Muzzle"]

# Book spellings for the classic slots; everything else comes from the
# Companion translation (weapon.modSlots in screens/weaponsAndArmor).
SLOT_LABEL_OVERRIDES = {
    "Receiver": "РЕСИВЕР",
    "Barrel": "СТВОЛ",
    "Capacitor": "КОНДЕНСАТОР",
    "Nozzle": "СОПЛО",
    "Grip": "РУКОЯТЬ",
    "Stock": "ЛОЖА",
    "Magazine": "МАГАЗИН",
    "Sight": "ПРИЦЕЛ",
    "Muzzle": "ДУЛО",
}


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def index_by_id(rows):
    return {row["id"]: row for row in rows}


class Companion:
    def __init__(self):
        self.weapons = index_by_id(load(os.path.join(COMP, "equipment", "weapons.json")))
        self.mods = index_by_id(load(os.path.join(COMP, "equipment", "weapon_mods.json")))
        self.slots = load(os.path.join(COMP, "equipment", "weapon_mod_slots.json"))
        self.weapons_ru = index_by_id(load(os.path.join(
            RU, "equipment", "weapons", "weapons.json")))
        self.mods_ru = index_by_id(load(os.path.join(
            RU, "equipment", "weapon_mods.json")))
        self.ammo = index_by_id(load(os.path.join(
            RU, "equipment", "ammo", "ammo_types.json")))
        self.qualities = index_by_id(load(os.path.join(RU, "system", "qualities.json")))
        self.effects = index_by_id(load(os.path.join(
            RU, "system", "damageEffects.json")))
        self.damage_types = load(os.path.join(
            COMP, "i18n", "ru-RU", "screens",
            "addItemModal.json"))["filter"]["damageTypes"]
        self.slot_labels = load(os.path.join(
            COMP, "i18n", "ru-RU",
            "screens-weaponsAndArmor.json"))["weapon"]["modSlots"]

        descriptions = os.path.join(ROOT, "data", "weapons",
                                    "descriptions.ru.json")
        self.descriptions = load(descriptions) if os.path.exists(descriptions) else {}

    # --- helpers -----------------------------------------------------------
    def weapon_name(self, wid):
        return (self.weapons_ru.get(wid) or {}).get("name") or wid

    def ammo_name(self, w):
        ammo = self.ammo.get(w.get("ammoId") or "") or {}
        name = ammo.get("name") or ""
        return re.sub(r"^Патрон\s+", "", name)

    def damage_type(self, value):
        if isinstance(value, list):
            return " и ".join(self.damage_types.get(v, v) for v in value)
        return self.damage_types.get(value, value or "")

    def quality_names(self, w):
        names = []
        for q in w.get("qualities") or []:
            name = (self.qualities.get(q.get("qualityId")) or {}).get("name")
            if name:
                names.append(name)
        return names

    def effect_names(self, w):
        names = []
        for e in w.get("effects") or []:
            name = (self.effects.get(e.get("effectId")) or {}).get("name")
            if name:
                if e.get("value") is not None:  # «Проникающий 2»
                    name = f"{name} {e['value']}"
                names.append(name)
        return names

    def slot_label(self, slot):
        if slot in SLOT_LABEL_OVERRIDES:
            return SLOT_LABEL_OVERRIDES[slot]
        name = self.slot_labels.get(slot.lower().rstrip("s"))
        if not name:
            name = self.slot_labels.get(slot.lower(), slot)
        return name.upper()

    def mod_rows(self, wid):
        slots = self.slots.get(wid) or {}
        order = [s for s in SLOT_ORDER if slots.get(s)]
        order += sorted(s for s in slots if s not in SLOT_ORDER and slots[s])
        rows = []
        for slot in order:
            items = []
            for mid in slots[slot]:
                name = (self.mods_ru.get(mid) or {}).get("name")
                if name:
                    items.append(name)
            if items:
                rows.append({"slot": self.slot_label(slot), "items": items})
        return rows

    def description(self, wid):
        if wid in self.descriptions:
            return self.descriptions[wid]
        return ((self.weapons_ru.get(wid) or {}).get("flavour") or "").strip()


def slugify(wid):
    return wid.removeprefix("weapon_").replace("_", "-")


def build_card(comp: Companion, wid, page=None, image=""):
    w = comp.weapons[wid]
    ru = comp.weapons_ru.get(wid) or {}
    card = {
        "id": wid,
        "title": comp.weapon_name(wid),
        "weight": w.get("weight", ""),
        "cost": w.get("cost", ""),
        "rarity": w.get("rarity", ""),
        "ammo": comp.ammo_name(w),
        "damageType": comp.damage_type(w.get("damageType")),
        "damage": w.get("damage", ""),
        "fireRate": w.get("fireRate", ""),
        "range": ru.get("rangeName") or "-",
        "effects": comp.effect_names(w),
        "qualities": comp.quality_names(w),
        "description": comp.description(wid),
        "image": image,
        "mods": comp.mod_rows(wid),
    }
    if page is not None:
        card["page"] = page
    return card


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ids", nargs="*", help="weapon ids (weapon_10mm_pistol …)")
    ap.add_argument("--all", action="store_true", help="every weapon")
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "data", "weapons", "cards"))
    ap.add_argument("--image", default="", help="same placeholder for every card")
    ap.add_argument("--image-dir", default="",
                    help="look for <slug>.png in this directory")
    ap.add_argument("--page-start", type=int, default=None)
    args = ap.parse_args(argv)

    comp = Companion()
    ids = list(comp.weapons) if args.all else args.ids
    if not ids:
        ap.error("pass weapon ids or --all")

    os.makedirs(args.out_dir, exist_ok=True)
    missing_desc = 0
    for n, wid in enumerate(ids):
        if wid not in comp.weapons:
            print(f"unknown weapon: {wid}", file=sys.stderr)
            continue
        image = args.image
        if args.image_dir:
            candidate = os.path.join(args.image_dir, slugify(wid) + ".png")
            image = candidate if os.path.exists(candidate) else image
        page = args.page_start + n if args.page_start is not None else None
        card = build_card(comp, wid, page=page, image=image)
        if not card["description"]:
            missing_desc += 1
        out = os.path.join(args.out_dir, slugify(wid) + ".json")
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(card, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        print(out)

    if missing_desc:
        print(f"warning: {missing_desc} card(s) without a description",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
