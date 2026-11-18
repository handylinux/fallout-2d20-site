#!/usr/bin/env python3
"""Build English presentation cards from the vendored Companion data.

The English catalogue uses the same numeric rules and weapon IDs as the
Russian catalogue, but reads every visible weapon field from the checked-in
``en-EN`` localisation snapshot.  The returned cards intentionally have no
ordinary image path: :mod:`build_weapon_catalog_en` replays Publisher artwork
only from an exact manifest ``weapon_id`` match.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import weapon_mod_policy as mod_policy

ROOT = Path(__file__).resolve().parent.parent
COMP = ROOT / "data" / "weapon-book" / "companion"
EN = COMP / "i18n" / "en-EN"
RU = COMP / "i18n" / "ru-RU" / "data"
DEFAULT_OUT = ROOT / "data" / "weapons" / "cards" / "en"

SLOT_ORDER = ["Receiver", "Barrel", "Capacitor", "Nozzle", "Grip", "Stock",
              "Magazine", "Sight", "Muzzle"]
SLOT_ALIASES = {"dish": "dishe", "camera": "chamber"}
CATEGORY_ORDER = ["Light", "Heavy", "Energy", "Explosive", "Melee", "Thrown", "Unarmed"]
CATEGORY_TITLES = {
    "Light": "Light Weapons",
    "Heavy": "Heavy Weapons",
    "Energy": "Energy Weapons",
    "Explosive": "Explosive Weapons",
    "Melee": "Melee Weapons",
    "Thrown": "Thrown Weapons",
    "Unarmed": "Unarmed Weapons",
    "Other": "Other Weapons",
}

# The Companion snapshot models these records as weapons, but Assaultron Head
# is not a standalone weapon and Straight Razor only references another weapon.
# Keep Unarmed Attack and Assaultron Head Laser: they are independent cards.
CATALOG_EXCLUDED_IDS = frozenset({
    "weapon_assaultron_head",
    "weapon_straight_razor",
})
LABELS = {
    "weight": "Weight",
    "cost": "Cost",
    "rarity": "Rarity",
    "mods_heading": "SUPPORTED MODIFICATIONS",
    "no_mods": "NO SUPPORTED MODIFICATIONS",
    "headers": [
        "AMMO", "DAMAGE\nTYPE", "DAMAGE", "FIRE\nRATE", "RANGE", "EFFECTS",
        "QUALITIES",
    ],
}


def load(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def index_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in rows}


def _has_cyrillic(value: str) -> bool:
    return any("\u0400" <= char <= "\u04ff" for char in value)


class Companion:
    """The English text layer paired with the shared Companion rules data."""

    def __init__(self) -> None:
        self.weapons = index_by_id(load(COMP / "equipment" / "weapons.json"))
        self.base_mods = index_by_id(load(COMP / "equipment" / "weapon_mods.json"))
        self.slots = load(COMP / "equipment" / "weapon_mod_slots.json")
        self.ammo = index_by_id(load(EN / "data" / "equipment" / "ammo" /
                                     "ammo_types.json"))
        self.weapons_en = index_by_id(load(EN / "data" / "equipment" /
                                           "weapons" / "weapons.json"))
        self.mods_en = index_by_id(load(EN / "data" / "equipment" /
                                        "weapon_mods.json"))
        self.qualities = index_by_id(load(EN / "data" / "system" / "qualities.json"))
        self.effects = index_by_id(load(EN / "data" / "system" /
                                        "damageEffects.json"))
        self.damage_types = load(EN / "screens" / "inventory" / "modals" /
                                 "addItemModal.json")["filter"]["damageTypes"]
        self.slot_labels = load(EN / "screens" / "weaponsAndArmor" /
                                "screen.json")["weapon"]["modSlots"]

        # Two English Companion records retain a Russian range label.  Build an
        # exact mapping from the matching RU/EN records rather than translating
        # or guessing the affected range names.
        weapons_ru = index_by_id(load(RU / "equipment" / "weapons" / "weapons.json"))
        self.english_range_by_ru_label: dict[str, str] = {}
        for weapon_id, russian in weapons_ru.items():
            ru_label = russian.get("rangeName")
            en_label = (self.weapons_en.get(weapon_id) or {}).get("rangeName")
            if not isinstance(ru_label, str) or not isinstance(en_label, str):
                continue
            if not ru_label or not en_label or _has_cyrillic(en_label):
                continue
            previous = self.english_range_by_ru_label.setdefault(ru_label, en_label)
            if previous != en_label:
                raise ValueError(f"Conflicting English range labels for {ru_label!r}")

    def slot_label(self, slot: str) -> str:
        key = slot.lower()
        label = (self.slot_labels.get(key)
                 or self.slot_labels.get(SLOT_ALIASES.get(key, key))
                 or self.slot_labels.get(key.rstrip("s"))
                 or slot)
        return str(label).upper()

    def ammo_name(self, weapon: dict[str, Any], weapon_id: str) -> str:
        ids = [value.strip() for value in str(weapon.get("ammoId") or "").split(",")
               if value.strip()]
        names = [str((self.ammo.get(ammo_id) or {}).get("name") or "")
                 for ammo_id in ids]
        if any(not name for name in names):
            raise ValueError(f"Missing English ammo name for {weapon_id}: {ids}")
        return ", ".join(names)

    def damage_type(self, value: Any, weapon_id: str) -> str:
        if isinstance(value, list):
            missing = [item for item in value if item not in self.damage_types]
            if missing:
                raise ValueError(f"Missing English damage type(s) for {weapon_id}: {missing}")
            return " and ".join(str(self.damage_types[item]) for item in value)
        if value and value not in self.damage_types:
            raise ValueError(f"Missing English damage type for {weapon_id}: {value}")
        return str(self.damage_types.get(value) or "")

    def effect_names(self, weapon: dict[str, Any], weapon_id: str) -> list[str]:
        result = []
        for effect in weapon.get("effects") or []:
            effect_id = effect.get("effectId")
            item = self.effects.get(effect_id) or {}
            name = item.get("name")
            if not name:
                raise ValueError(f"Missing English effect for {weapon_id}: {effect_id}")
            result.append(f"{name} {effect['value']}" if effect.get("value") is not None
                          else str(name))
        return result

    def quality_names(self, weapon: dict[str, Any], weapon_id: str) -> list[str]:
        result = []
        for quality in weapon.get("qualities") or []:
            quality_id = quality.get("qualityId")
            item = self.qualities.get(quality_id) or {}
            name = item.get("name")
            if not name:
                raise ValueError(f"Missing English quality for {weapon_id}: {quality_id}")
            result.append(str(name))
        return result

    def mod_rows(self, weapon_id: str) -> list[dict[str, Any]]:
        slot_map = self.slots.get(weapon_id) or {}
        order = [slot for slot in SLOT_ORDER
                 if mod_policy.catalog_mod_ids(slot_map.get(slot) or [])]
        order.extend(sorted(slot for slot in slot_map if slot not in SLOT_ORDER
                            and mod_policy.catalog_mod_ids(slot_map[slot])))
        rows = []
        for slot in order:
            names = []
            for mod_id in mod_policy.catalog_mod_ids(slot_map[slot]):
                if mod_id not in self.base_mods:
                    raise ValueError(f"Unknown mod {mod_id} for {weapon_id} ({slot})")
                name = (self.mods_en.get(mod_id) or {}).get("name")
                if not name:
                    raise ValueError(f"Missing English mod name for {mod_id}")
                names.append(str(name))
            if names:
                rows.append({"slot": self.slot_label(slot), "items": names})
        return rows

    def card(self, weapon_id: str) -> dict[str, Any]:
        weapon = self.weapons.get(weapon_id)
        localized = self.weapons_en.get(weapon_id) or {}
        if weapon is None:
            raise ValueError(f"Unknown weapon ID: {weapon_id}")
        title = localized.get("name")
        if not title:
            raise ValueError(f"Missing English weapon name for {weapon_id}")
        range_name = str(localized.get("rangeName") or "")
        if _has_cyrillic(range_name):
            mapped_range = self.english_range_by_ru_label.get(range_name)
            if not mapped_range:
                raise ValueError(
                    f"Missing confirmed English range label for {weapon_id}: {range_name!r}"
                )
            range_name = mapped_range
        weapon_type = str(weapon.get("weaponType") or "Other")
        return {
            "id": weapon_id,
            "title": str(title),
            "category": CATEGORY_TITLES.get(weapon_type, CATEGORY_TITLES["Other"]),
            "weight": weapon.get("weight", ""),
            "cost": weapon.get("cost", ""),
            "rarity": weapon.get("rarity", ""),
            "ammo": self.ammo_name(weapon, weapon_id),
            "damageType": self.damage_type(weapon.get("damageType"), weapon_id),
            "damage": weapon.get("damage", ""),
            "fireRate": weapon.get("fireRate", ""),
            "range": range_name or "-",
            "effects": self.effect_names(weapon, weapon_id),
            "qualities": self.quality_names(weapon, weapon_id),
            "description": str(localized.get("flavour") or "").strip(),
            "image": "",
            "mods": self.mod_rows(weapon_id),
            "labels": {**LABELS, "headers": list(LABELS["headers"])},
        }


def ordered_cards(companion: Companion | None = None) -> list[dict[str, Any]]:
    """Return the stable confirmed 144-card English catalogue order."""
    companion = companion or Companion()
    rank = {category: index for index, category in enumerate(CATEGORY_ORDER)}
    cards = [companion.card(weapon_id) for weapon_id in companion.weapons
             if weapon_id not in CATALOG_EXCLUDED_IDS]
    cards.sort(key=lambda card: (
        rank.get(str((companion.weapons[card["id"]].get("weaponType") or "Other")), 99),
        str(card["title"]).casefold(),
        str(card["id"]),
    ))
    for number, card in enumerate(cards, start=1):
        card["page"] = number
    return cards


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT,
                        help="optional directory for one English card JSON per weapon")
    args = parser.parse_args(argv)
    cards = ordered_cards()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for card in cards:
        slug = str(card["id"]).removeprefix("weapon_").replace("_", "-")
        (args.out_dir / f"{slug}.json").write_text(
            json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(f"Wrote {len(cards)} English weapon cards to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
