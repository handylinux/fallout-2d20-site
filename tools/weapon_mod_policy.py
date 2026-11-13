"""Shared policy for placing specific weapon modifications."""

# Above this total, detailed rows compete with the name grid and description.
MAX_DETAILED_MODS = 8


def specific_mods(comp, weapon_id):
    """Return confirmed (slot, mod ID) pairs eligible for weapon-page detail.

    Slot/applicability disagreements are not guessed: a mod must name only this
    weapon and not appear in another weapon's slot list. A caller must still
    verify the detailed table physically fits before excluding these pairs from
    a shared reference.
    """
    slots = comp.slots.get(weapon_id) or {}
    pairs = [(slot, mid) for slot, ids in slots.items() for mid in ids]
    if not pairs or len(pairs) > MAX_DETAILED_MODS:
        return set()
    other_refs = {mid for wid, mapping in comp.slots.items() if wid != weapon_id
                  for ids in (mapping or {}).values() for mid in ids}
    return {(slot, mid) for slot, mid in pairs
            if mid not in other_refs and (comp.mods.get(mid) or {}).get('applies_to_ids') == [weapon_id]}
