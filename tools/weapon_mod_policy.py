"""Shared policy for placing and publishing weapon modifications.

The vendored Companion snapshot is preserved verbatim.  Publication-only rules
live here so that a source-data anomaly cannot silently appear in one locale
but not the other.
"""

# The Publisher source lists one ``Ложа с компенсатором отдачи`` on the Gauss
# Rifle, Light Machine Gun and Pump-Action Shotgun pages.  Companion also puts
# the suppressed record beside the canonical record on exactly those three
# weapons. Its separate range / Close Quarters rule is not independently
# Publisher-backed; publishing it creates two near-identical stocks. Retain raw
# Companion data, but omit that duplicate from every printed catalogue view.
RECOIL_COMPENSATING_CANONICAL_ID = "mod_recoil_compensating_stock"
RECOIL_COMPENSATING_SUPPRESSED_ID = "mod_recoil_compensating"
RECOIL_COMPENSATING_OVERLAP_WEAPON_IDS = frozenset({
    "weapon_gauss_rifle",
    "weapon_light_machine_gun",
    "weapon_pump_action_shotgun",
})
CATALOG_EXCLUDED_MOD_IDS = frozenset({RECOIL_COMPENSATING_SUPPRESSED_ID})

# A Publisher-verified visible name for the surviving canonical record.  This
# is a display correction only; the vendored localisation remains untouched.
CATALOG_RUSSIAN_MOD_NAMES = {
    RECOIL_COMPENSATING_CANONICAL_ID: "Ложа с компенсатором отдачи",
}

# In both Companion cross-links this mine is listed as having a barrel,
# but the source does not support any plasma mine modifications.
CATALOG_EXCLUDED_MOD_LINKS = frozenset({('weapon_plasma_mine', 'mod_heavy_barrel')})

# Above this total, detailed rows compete with the name grid and description.
MAX_DETAILED_MODS = 8


def catalog_mod_ids(mod_ids):
    """Return publication-eligible mod IDs in their source order.

    This intentionally filters only audited duplicate records rather than
    changing the Companion snapshot or guessing replacements from names.
    """
    return [mod_id for mod_id in mod_ids if mod_id not in CATALOG_EXCLUDED_MOD_IDS]


def published_slot_mod_ids(weapon_id, mod_ids):
    """Filter both globally suppressed records and audited incompatible links."""
    return [mid for mid in catalog_mod_ids(mod_ids)
            if (weapon_id, mid) not in CATALOG_EXCLUDED_MOD_LINKS]


def specific_mods(comp, weapon_id):
    """Return confirmed (slot, mod ID) pairs eligible for weapon-page detail.

    Slot/applicability disagreements are not guessed: a mod must name only this
    weapon and not appear in another weapon's slot list. A caller must still
    verify the detailed table physically fits before excluding these pairs from
    a shared reference.
    """
    slots = comp.slots.get(weapon_id) or {}
    pairs = [(slot, mid) for slot, ids in slots.items()
             for mid in catalog_mod_ids(ids)]
    if not pairs or len(pairs) > MAX_DETAILED_MODS:
        return set()
    other_refs = {mid for wid, mapping in comp.slots.items() if wid != weapon_id
                  for ids in (mapping or {}).values()
                  for mid in catalog_mod_ids(ids)}
    return {(slot, mid) for slot, mid in pairs
            if mid not in other_refs and (comp.mods.get(mid) or {}).get('applies_to_ids') == [weapon_id]}
