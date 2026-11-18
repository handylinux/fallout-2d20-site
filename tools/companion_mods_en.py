#!/usr/bin/env python3
"""English Companion weapon-modification table adapter.

This module deliberately keeps the rules data separate from the page renderer.
It turns the checked-in, language-neutral modification records into six text
cells for :mod:`weapon_mods_table_unicode`, taking every visible item name,
effect name, quality name, ammunition name, damage type and prefix from the
vendored English data.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from weapons2cards_en import Companion

ROOT = Path(__file__).resolve().parent.parent
PREFIXES = ROOT / "data" / "weapon-book" / "mod-prefixes.en.json"

SLOT_ORDER = [
    "Receiver", "Barrel", "Magazine", "Grip", "Stock", "Sight", "Muzzle",
    "Capacitor", "Fuel", "Tank", "Nozzle", "Launcher", "Canister", "Camera",
    "Container", "Concentrate", "Dish", "Winch", "Frame", "Unique",
]

SLOT_TITLES = {
    "Receiver": "RECEIVER MODIFICATIONS",
    "Barrel": "BARREL MODIFICATIONS",
    "Magazine": "MAGAZINE MODIFICATIONS",
    "Grip": "GRIP MODIFICATIONS",
    "Stock": "STOCK MODIFICATIONS",
    "Sight": "SIGHT MODIFICATIONS",
    "Muzzle": "MUZZLE MODIFICATIONS",
    "Capacitor": "CAPACITOR MODIFICATIONS",
    "Fuel": "FUEL MODIFICATIONS",
    "Tank": "TANK MODIFICATIONS",
    "Nozzle": "NOZZLE MODIFICATIONS",
    "Launcher": "LAUNCHER MODIFICATIONS",
    "Canister": "CANISTER MODIFICATIONS",
    "Camera": "CHAMBER MODIFICATIONS",
    "Container": "CONTAINER MODIFICATIONS",
    "Concentrate": "CONCENTRATE MODIFICATIONS",
    "Dish": "DISH MODIFICATIONS",
    "Winch": "WINCH MODIFICATIONS",
    "Frame": "FRAME MODIFICATIONS",
    "Unique": "UNIQUE MODIFICATIONS",
}

HEADERS = ("MODIFICATION", "PREFIX", "EFFECTS", "WEIGHT", "COST", "PERKS")


class EnglishModificationError(ValueError):
    """The localisation snapshot cannot make a complete English table."""


def load_prefixes(path: Path = PREFIXES) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or any(not isinstance(key, str) or not isinstance(value, str)
                                        for key, value in data.items()):
        raise EnglishModificationError(f"Invalid English modification prefixes: {path}")
    return data


def display_number(value: Any) -> str:
    """Render explicit numeric data without treating a missing value as zero."""
    if value is None or value == "":
        return "—"
    if isinstance(value, (int, float)):
        return f"{value:g}"
    return str(value)


def _signed(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:+g}"
    return str(value)


def _label(labels: dict[str, dict[str, Any]], identifier: Any, kind: str) -> str:
    entry = labels.get(str(identifier)) or {}
    value = entry.get("name")
    if not isinstance(value, str) or not value:
        raise EnglishModificationError(f"Missing English {kind} label: {identifier!r}")
    return value


def _change_label(change: dict[str, Any], labels: dict[str, dict[str, Any]], kind: str) -> str:
    operation = change.get("op")
    action = {"gain": "Add", "lose": "Remove", "remove": "Remove"}.get(operation)
    if action is None:
        raise EnglishModificationError(f"Unsupported {kind} change: {change!r}")
    name = _label(labels, change.get("id"), kind)
    if change.get("value") is not None:
        name = f"{name} {change['value']}"
    return f"{action} {kind}: {name}"


def effect_text(mod: dict[str, Any], companion: Companion) -> str:
    """Explain the structured modifier fields in compact English table text.

    Terms whose proper names exist in Companion are always looked up there;
    the surrounding grammar only exposes the operation encoded in the record.
    """
    parts: list[str] = []
    fields = (
        ("damageModifier", "Damage", " DC"),
        ("fireRateModifier", "Fire Rate", ""),
        ("rangeModifier", "Range", " zone"),
    )
    for field, label, suffix in fields:
        change = mod.get(field)
        if change is None:
            continue
        if not isinstance(change, dict) or "value" not in change:
            raise EnglishModificationError(f"Invalid {field} on {mod.get('id')}: {change!r}")
        operation, value = change.get("op"), change["value"]
        if operation == "set":
            parts.append(f"{label}: {display_number(value)}{suffix}")
        elif operation in {"+", "-"}:
            parts.append(f"{label}: {_signed(value) if operation == '+' else '-' + display_number(value)}{suffix}")
        else:
            raise EnglishModificationError(
                f"Unsupported {field} operation on {mod.get('id')}: {operation!r}"
            )

    ammo_override = mod.get("ammoOverride")
    if ammo_override:
        parts.append("Ammo: " + _label(companion.ammo, ammo_override, "ammo"))

    # Some older records carry a direct damageType field; newer ones use the
    # explicit operation object. Both are represented without assuming that one
    # silently supersedes the other.
    direct_damage_type = mod.get("damageType")
    damage_type_override = mod.get("damageTypeOverride")
    override_values = []
    if isinstance(damage_type_override, dict):
        raw = damage_type_override.get("value")
        override_values = raw if isinstance(raw, list) else [raw]
    # Several legacy records duplicate `damageType` as a set override.  Print
    # that one rule once, rather than presenting the same Companion fact twice.
    duplicate_direct_type = (
        isinstance(damage_type_override, dict)
        and damage_type_override.get("op") == "set"
        and direct_damage_type is not None
        and list(override_values) == [direct_damage_type]
    )
    if direct_damage_type and not duplicate_direct_type:
        value = companion.damage_types.get(str(direct_damage_type))
        if not isinstance(value, str) or not value:
            raise EnglishModificationError(
                f"Missing English damage type for {mod.get('id')}: {direct_damage_type!r}"
            )
        parts.append("Damage Type: " + value)

    if damage_type_override is not None:
        if not isinstance(damage_type_override, dict):
            raise EnglishModificationError(
                f"Invalid damageTypeOverride on {mod.get('id')}: {damage_type_override!r}"
            )
        operation = damage_type_override.get("op")
        raw_values = damage_type_override.get("value")
        values = raw_values if isinstance(raw_values, list) else [raw_values]
        names: list[str] = []
        for value in values:
            label = companion.damage_types.get(str(value))
            if not isinstance(label, str) or not label:
                raise EnglishModificationError(
                    f"Missing English damage type for {mod.get('id')}: {value!r}"
                )
            names.append(label)
        if operation not in {"set", "add"} or not names:
            raise EnglishModificationError(
                f"Invalid damageTypeOverride on {mod.get('id')}: {damage_type_override!r}"
            )
        parts.append(("Set" if operation == "set" else "Add") +
                     " Damage Type: " + " and ".join(names))

    for field, labels, kind in (
        ("effectChanges", companion.effects, "Effect"),
        ("qualityChanges", companion.qualities, "Quality"),
    ):
        changes = mod.get(field) or []
        if not isinstance(changes, list):
            raise EnglishModificationError(f"Invalid {field} on {mod.get('id')}: {changes!r}")
        for change in changes:
            if not isinstance(change, dict):
                raise EnglishModificationError(f"Invalid {field} entry on {mod.get('id')}: {change!r}")
            parts.append(_change_label(change, labels, kind))
    return "; ".join(parts) if parts else "—"


def perks_text(mod: dict[str, Any]) -> str:
    perks = [str(mod.get(key) or "").strip() for key in ("perk1", "perk2")]
    perks = [perk for perk in perks if perk]
    return ", ".join(perks) if perks else "—"


def make_mod_data(companion: Companion | None = None,
                  prefixes: dict[str, str] | None = None) -> tuple[dict[str, Any], list[str]]:
    """Return editable English table data for every known Companion modification.

    The second return value contains only non-fatal diagnostics.  The builder
    treats an absent localisation, prefix, or slot title as fatal instead of
    inventing a visible English substitute.
    """
    companion = companion or Companion()
    prefixes = prefixes or load_prefixes()
    mods = companion.base_mods
    missing_names = sorted(mod_id for mod_id in mods
                           if not isinstance((companion.mods_en.get(mod_id) or {}).get("name"), str)
                           or not (companion.mods_en.get(mod_id) or {}).get("name"))
    missing_prefixes = sorted(mod_id for mod_id in mods if not prefixes.get(mod_id))
    if missing_names or missing_prefixes:
        pieces = []
        if missing_names:
            pieces.append("missing English names: " + ", ".join(missing_names))
        if missing_prefixes:
            pieces.append("missing English prefixes: " + ", ".join(missing_prefixes))
        raise EnglishModificationError("; ".join(pieces))

    by_slot: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for mod_id, mod in mods.items():
        slot = mod.get("slot")
        if not isinstance(slot, str) or not slot:
            raise EnglishModificationError(f"Missing slot for {mod_id}")
        by_slot.setdefault(slot, []).append((mod_id, mod))
    unknown_slots = sorted(set(by_slot) - set(SLOT_TITLES))
    if unknown_slots:
        raise EnglishModificationError("Missing English slot titles: " + ", ".join(unknown_slots))

    order = [slot for slot in SLOT_ORDER if slot in by_slot]
    order.extend(sorted(set(by_slot) - set(order)))
    sections: list[dict[str, Any]] = []
    diagnostics: list[str] = []
    for slot in order:
        rows: list[list[str]] = []
        items = sorted(
            by_slot[slot],
            key=lambda pair: (str(companion.mods_en[pair[0]]["name"]).casefold(), pair[0]),
        )
        for mod_id, mod in items:
            rows.append([
                str(companion.mods_en[mod_id]["name"]),
                prefixes[mod_id],
                effect_text(mod, companion),
                display_number(mod.get("weight")),
                display_number(mod.get("cost")),
                perks_text(mod),
            ])
        section: dict[str, Any] = {
            "category": SLOT_TITLES[slot],
            "rows": rows,
        }
        # A clear physical gap keeps adjacent slot tables distinct even when
        # both fit on the same printed page.
        if sections:
            section["gap_before"] = 18
        sections.append(section)

    if sum(len(section["rows"]) for section in sections) != len(mods):
        raise EnglishModificationError("Modification-table rows do not cover every Companion mod")
    return {
        "title": "WEAPON MODIFICATIONS",
        "headers": list(HEADERS),
        "sections": sections,
    }, diagnostics
