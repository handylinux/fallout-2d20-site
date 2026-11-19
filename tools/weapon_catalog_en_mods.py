"""Resolve EN modification rows before building card tables and chapter indexes."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Iterable
import json

import companion_mods_en as mods
from weapon_mod_policy import published_slot_mod_ids
from weapons2cards_en import Companion

PUBLISHER_VARIANTS = Path(__file__).resolve().parent.parent / "data/weapon-book/publisher-mod-variants.en.json"
MIN_SHARED_WEAPONS = 4
# Known conflicting Companion links; the Russian book uses a separate site reference.
UNVERIFIED_WEAPON_IDS = frozenset({"weapon_gatling_plasma"})
Row = tuple[str, str, str, str, str, str, str]  # slot and the six displayed cells


def _slots_in_order(slots: Iterable[str]) -> list[str]:
    keys = set(slots)
    return [slot for slot in mods.SLOT_ORDER if slot in keys] + sorted(keys - set(mods.SLOT_ORDER))


def weapon_rows(companion: Companion, weapon_ids: set[str]) -> dict[str, list[Row]]:
    """Use audited weapon-specific Publisher variants on 1:1 ties, never a global ID override."""
    prefixes = mods.load_prefixes()
    overrides = json.loads(PUBLISHER_VARIANTS.read_text(encoding="utf-8"))
    rows_by_weapon = {}
    for weapon_id in sorted(weapon_ids):
        slots = companion.slots.get(weapon_id) or {}
        pairs = [(slot, mid) for slot in _slots_in_order(slots)
                 for mid in published_slot_mod_ids(weapon_id, slots[slot])]
        if weapon_id in overrides:
            record = overrides[weapon_id]
            audited = record["rows"]
            if (any(len(row) != 8 or any(not isinstance(value, str) for value in row) for row in audited)
                    or len(audited) != len(pairs) or {tuple(row[:2]) for row in audited} != set(pairs)):
                raise ValueError(f"{weapon_id}: audited Publisher rows no longer match the Companion slot inventory")
            rows_by_weapon[weapon_id] = [(slot, *cells) for slot, _mid, *cells in audited]
        else:
            rows_by_weapon[weapon_id] = [(slot, *mods.mod_row(companion, mid, prefixes))
                                         for slot, mid in pairs]
    return rows_by_weapon


def variant_weapons(weapon_ids: Iterable[str], rows_by_weapon: dict[str, list[Row]]) -> dict[Row, set[str]]:
    """Index complete identical rows by distinct verified weapons in this chapter."""
    weapons_by_variant: dict[Row, set[str]] = defaultdict(set)
    for weapon_id in weapon_ids:
        if weapon_id in UNVERIFIED_WEAPON_IDS:
            continue
        for row in rows_by_weapon[weapon_id]:
            weapons_by_variant[row].add(weapon_id)
    return weapons_by_variant


def shared_rows(weapon_ids: Iterable[str], rows_by_weapon: dict[str, list[Row]]) -> list[Row]:
    return [row for row, weapons in variant_weapons(weapon_ids, rows_by_weapon).items()
            if len(weapons) >= MIN_SHARED_WEAPONS]


def table_data(title: str, rows: list[Row], *, gap: int = 18) -> dict:
    by_slot = defaultdict(list)
    for slot, *cells in rows:
        by_slot[slot].append(cells)
    sections = [{"category": mods.SLOT_TITLES[slot], "rows": by_slot[slot]}
                for slot in _slots_in_order(by_slot)]
    for section in sections[1:]:
        section["gap_before"] = gap
    return {"title": title, "headers": list(mods.HEADERS), "sections": sections}


def card_mod_names(companion: Companion, rows: list[Row]) -> list[dict]:
    by_slot = defaultdict(list)
    for slot, name, *_ in rows:
        if name not in by_slot[slot]:
            by_slot[slot].append(name)
    return [{"slot": companion.slot_label(slot), "items": names} for slot, names in by_slot.items()]


def specific_section(title: str, rows: list[Row], *, unverified: bool = False) -> dict:
    """Identify the weapon, without presenting its rows as chapter-wide options."""
    ambiguous = defaultdict(set)
    for slot, name, *_ in rows:
        ambiguous[name].add(slot)
    cells = [[f"{name} ({slot})" if len(ambiguous[name]) > 1 else name, *values]
             for slot, name, *values in rows]
    suffix = " — COMPATIBILITY NEEDS CLARIFICATION" if unverified else ""
    return {"category": title.upper() + suffix, "rows": cells, "gap_before": 8}
