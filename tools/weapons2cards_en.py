#!/usr/bin/env python3
"""Build complete English weapon cards and a bookmarked catalog PDF.

Uses the English Companion localization for names, descriptions, mod/ammo names,
qualities, effects, range labels, and slot labels; numeric rules data and the
weapon-to-mod relationship map remain the base Companion equipment data.

    python3 tools/weapons2cards_en.py --pdf docs/render/out/weapon-catalog-en.pdf
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMP = os.path.join(ROOT, "data", "companion")
EN = os.path.join(COMP, "i18n", "en-EN")
DEFAULT_OUT = os.path.join(ROOT, "data", "weapons", "cards", "en")
SLOT_ORDER = ["Receiver", "Barrel", "Capacitor", "Nozzle", "Grip", "Stock",
              "Magazine", "Sight", "Muzzle"]
SLOT_ALIASES = {"dish": "dishe", "camera": "chamber"}
CATEGORY_ORDER = ["Light", "Heavy", "Energy", "Explosive", "Melee", "Thrown", "Unarmed"]
CATEGORY_TITLES = {
    "Light": "Light Weapons", "Heavy": "Heavy Weapons",
    "Energy": "Energy Weapons", "Explosive": "Explosive Weapons",
    "Melee": "Melee Weapons", "Thrown": "Thrown Weapons",
    "Unarmed": "Unarmed Weapons", "Other": "Other Weapons",
}
LABELS = {
    "weight": "Weight", "cost": "Cost", "rarity": "Rarity",
    "mods_heading": "SUPPORTED MODIFICATIONS",
    "no_mods": "NO SUPPORTED MODIFICATIONS",
    "headers": ["AMMO", "DAMAGE\nTYPE", "DAMAGE", "FIRE\nRATE", "RANGE", "EFFECTS", "QUALITIES"],
}


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def index(path):
    return {row["id"]: row for row in load(path)}


class Companion:
    @staticmethod
    def _has_cyrillic(value):
        return any("\u0400" <= char <= "\u04ff" for char in value)

    def __init__(self):
        self.weapons = index(os.path.join(COMP, "equipment", "weapons.json"))
        self.base_mods = index(os.path.join(COMP, "equipment", "weapon_mods.json"))
        self.slots = load(os.path.join(COMP, "equipment", "weapon_mod_slots.json"))
        self.ammo = index(os.path.join(EN, "data/equipment/ammo/ammo_types.json"))
        self.weapons_en = index(os.path.join(EN, "data/equipment/weapons/weapons.json"))
        ru_weapons = index(os.path.join(
            COMP, "i18n/ru-RU/data/equipment/weapons/weapons.json"))
        self.english_range_by_ru_label = {}
        for wid, russian in ru_weapons.items():
            ru_label = russian.get("rangeName")
            en_label = self.weapons_en.get(wid, {}).get("rangeName")
            if ru_label and en_label and not self._has_cyrillic(en_label):
                existing = self.english_range_by_ru_label.setdefault(ru_label, en_label)
                if existing != en_label:
                    raise ValueError(f"Conflicting English range labels for {ru_label}")
        self.mods_en = index(os.path.join(EN, "data/equipment/weapon_mods.json"))
        self.qualities = index(os.path.join(EN, "data/system/qualities.json"))
        if "quality_targetting_computer" in self.qualities:
            self.qualities["quality_targetting_computer"]["name"] = "Targeting Computer"
        self.effects = index(os.path.join(EN, "data/system/damageEffects.json"))
        modal = load(os.path.join(EN, "screens/inventory/modals/addItemModal.json"))
        self.damage_types = modal["filter"]["damageTypes"]
        screen = load(os.path.join(EN, "screens/weaponsAndArmor/screen.json"))
        self.slot_labels = screen["weapon"]["modSlots"]

    def slot_label(self, slot):
        key = slot.lower()
        label = (self.slot_labels.get(key)
                 or self.slot_labels.get(SLOT_ALIASES.get(key, key))
                 or self.slot_labels.get(key.rstrip("s")) or slot)
        return label.upper()

    def card(self, wid):
        w = self.weapons[wid]
        localized = self.weapons_en.get(wid, {})
        if not localized.get("name"):
            raise ValueError(f"Missing English weapon name for {wid}")
        ammo_ids = [value.strip() for value in (w.get("ammoId") or "").split(",")
                    if value.strip()]
        ammo_names = [self.ammo.get(ammo_id, {}).get("name", "")
                      for ammo_id in ammo_ids]
        if any(not name for name in ammo_names):
            raise ValueError(f"Missing English ammo name for {wid}: {ammo_ids}")
        ammo = ", ".join(ammo_names)
        damage_type = w.get("damageType")
        if isinstance(damage_type, list):
            missing = [value for value in damage_type if value not in self.damage_types]
            if missing:
                raise ValueError(f"Missing English damage type(s) for {wid}: {missing}")
            damage_type = " and ".join(self.damage_types[value] for value in damage_type)
        else:
            if damage_type and damage_type not in self.damage_types:
                raise ValueError(f"Missing English damage type for {wid}: {damage_type}")
            damage_type = self.damage_types.get(damage_type, "")

        qualities = []
        for quality in w.get("qualities", []):
            quality_id = quality.get("qualityId")
            if quality_id not in self.qualities:
                raise ValueError(f"Missing English quality for {wid}: {quality_id}")
            name = self.qualities[quality_id]["name"]
            val = quality.get("value")
            if quality_id == "quality_tranq_x" and val is None:
                val = 3
            if val is not None:
                if name.endswith(" X"):
                    name = f"{name[:-2]} {val}"
                elif name.endswith(" (X)"):
                    name = f"{name[:-4]} ({val})"
                else:
                    name = f"{name} {val}"
            elif name.endswith(" X"):
                name = f"{name[:-2]} (X)"
            qualities.append(name)
        effects = []
        for effect in w.get("effects", []):
            effect_id = effect.get("effectId")
            if effect_id not in self.effects:
                raise ValueError(f"Missing English effect for {wid}: {effect_id}")
            name = self.effects[effect_id]["name"]
            val = effect.get("value")
            if effect_id == "effect_piercing_x" and val is None:
                val = 2 if wid == "weapon_underwater_gun" else 1
            if val is not None:
                name = f"{name} {val}"
            effects.append(name)

        slot_map = self.slots.get(wid, {})
        order = [s for s in SLOT_ORDER if slot_map.get(s)]
        order.extend(sorted(s for s in slot_map if s not in SLOT_ORDER and slot_map[s]))
        mods = []
        for slot in order:
            items = []
            for mid in slot_map[slot]:
                if mid not in self.base_mods or mid not in self.mods_en:
                    raise ValueError(f"Unresolved mod {mid} for {wid} ({slot})")
                name = self.mods_en[mid].get("name")
                if not name:
                    raise ValueError(f"Missing English mod name for {mid}")
                items.append(name)
            if items:
                mods.append({"slot": self.slot_label(slot), "items": items})

        kind = w.get("weaponType") or "Other"
        category = CATEGORY_TITLES.get(kind, CATEGORY_TITLES["Other"])
        range_name = localized.get("rangeName") or ""
        if self._has_cyrillic(range_name):
            # Two English records retain a Russian rangeName. Resolve that
            # exact Companion label through other same-data EN/RU weapon pairs.
            range_name = self.english_range_by_ru_label.get(range_name, "")
        return {
            "id": wid, "title": localized["name"], "category": category,
            "weight": w.get("weight", ""), "cost": w.get("cost", ""),
            "rarity": w.get("rarity", ""), "ammo": ammo,
            "damageType": damage_type, "damage": w.get("damage", ""),
            "fireRate": w.get("fireRate", ""),
            "range": range_name or "-",
            "effects": effects, "qualities": qualities,
            "description": (localized.get("flavour") or "").strip(),
            "image": self.image_for(wid), "mods": mods, "labels": LABELS,
        }

    @staticmethod
    def image_for(wid):
        slug = wid.removeprefix("weapon_").replace("_", "-")
        path = os.path.join(ROOT, "assets", "pdf", "weapons", slug + ".png")
        return path if os.path.exists(path) else ""


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=DEFAULT_OUT,
                        help="directory for one presentation-ready JSON per weapon")
    parser.add_argument("--pdf", default="", help="optional combined bookmarked PDF path")
    args = parser.parse_args(argv)

    comp = Companion()
    ids = list(comp.weapons)
    order = {name: i for i, name in enumerate(CATEGORY_ORDER)}
    cards = [comp.card(wid) for wid in ids]
    cards.sort(key=lambda c: (order.get(c["category"].removesuffix(" Weapons"), 99),
                              c["title"].casefold(), c["id"]))
    for page, card in enumerate(cards, 1):
        card["page"] = page
    no_description = [card["id"] for card in cards if not card["description"]]
    no_art = [card["id"] for card in cards if not card["image"]]
    os.makedirs(args.out_dir, exist_ok=True)
    for card in cards:
        slug = card["id"].removeprefix("weapon_").replace("_", "-")
        with open(os.path.join(args.out_dir, slug + ".json"), "w", encoding="utf-8") as f:
            json.dump(card, f, ensure_ascii=False, indent=2)
            f.write("\n")
    print(f"Wrote {len(cards)} English weapon cards to {args.out_dir}")
    if no_description:
        print(f"No English Companion description ({len(no_description)}): "
              + ", ".join(no_description), file=sys.stderr)
    if no_art:
        print(f"No matching reference artwork ({len(no_art)} weapons); left blank.",
              file=sys.stderr)

    if args.pdf:
        try:
            from weapon2pdf import register_fonts, render_catalog
        except ImportError:
            sys.path.insert(0, os.path.dirname(__file__))
            from weapon2pdf import register_fonts, render_catalog
        register_fonts()
        os.makedirs(os.path.dirname(os.path.abspath(args.pdf)), exist_ok=True)
        render_catalog(cards, args.pdf)
        print(f"Wrote {len(cards)} pages to {args.pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
