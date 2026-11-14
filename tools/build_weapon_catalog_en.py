#!/usr/bin/env python3
"""Build the complete English Fallout 2d20 Weapons Reference Book PDF.

Reproduces the 173+ page reference layout of book-weapon-catalog.pdf in clean
native English from Companion EN data, approved overrides, and structured JSON.
"""
from __future__ import annotations

import argparse
import json
import re
import tempfile
from pathlib import Path

import pymupdf
from reportlab.pdfgen import canvas

import companion_mods_receiver as conv
import weapon2pdf as w
import weapon_heavy_preview as heavy
import weapon_mod_policy as policy
import weapon_mods_table_unicode as tables
from weapons2cards import index_by_id, load as load_json, slugify

ROOT = Path(__file__).resolve().parent.parent
COMP = ROOT / 'data/weapon-book/companion'
EN_DATA = ROOT / 'data/companion/i18n/en-EN/data'
EN_SCREENS = ROOT / 'data/companion/i18n/en-EN/screens'
PREFIXES_EN = ROOT / 'data/weapon-book/mod-prefixes.en.json'
RULES_FRONT_EN = ROOT / 'data/weapons/rules-front.en.json'
DESCS_EN = ROOT / 'data/weapons/descriptions.en.json'
OVERRIDES_EN = ROOT / 'data/weapons/en-book-overrides.json'
HEAVY_SITE_MODS_EN = ROOT / 'data/weapons/heavy-site-specific-mods.en.json'

SMALL_ORDER = ROOT / 'data/weapons/small-guns-order.json'
HEAVY_ORDER = ROOT / 'data/weapons/heavy-guns-order.json'
ENERGY_ORDER = ROOT / 'data/weapons/energy-guns-order.json'
MELEE_ORDER = ROOT / 'data/weapons/melee-original-order.json'
REMAINING_ORDER = ROOT / 'data/weapons/remaining-order.json'

EN_TABLE_HEADERS = ('MODIFICATION', 'PREFIX', 'EFFECTS', 'WEIGHT', 'COST', 'PERKS')
EN_CARD_MOD_HEADERS = ('', 'NAME', 'PREFIX', 'EFFECTS', 'WEIGHT', 'COST', 'PERKS')
EN_CARD_LABELS = {
    'weight': 'Weight',
    'cost': 'Cost',
    'rarity': 'Rarity',
    'mods_heading': 'SUPPORTED MODIFICATIONS',
    'no_mods': 'NO SUPPORTED MODIFICATIONS',
    'headers': ['AMMO', 'DAMAGE\nTYPE', 'DAMAGE', 'FIRE\nRATE', 'RANGE', 'EFFECTS', 'QUALITIES'],
}

ALL_SLOT_ORDER = [
    'Fuel', 'Receiver', 'Capacitor', 'Barrel', 'Nozzle', 'Tank', 'Magazine',
    'Grip', 'Stock', 'Sight', 'Muzzle', 'Dish', 'Concentrate', 'Container',
    'Launcher', 'Canister', 'Camera', 'Frame', 'Winch', 'Unique',
]
MOD_TABLE_SLOT_TITLES = {
    'Receiver': 'RECEIVER',
    'Barrel': 'BARREL',
    'Magazine': 'MAGAZINE',
    'Grip': 'GRIP',
    'Stock': 'STOCK',
    'Sight': 'SIGHT',
    'Muzzle': 'MUZZLE',
    'Capacitor': 'CAPACITOR',
    'Nozzle': 'NOZZLE',
    'Winch': 'WINCH',
    'Frame': 'FRAME',
    'Fuel': 'FUEL',
    'Tank': 'TANK',
    'Launcher': 'LAUNCHER',
    'Canister': 'CANISTER',
    'Camera': 'CHAMBER',
    'Dish': 'DISH',
    'Concentrate': 'CONCENTRATE',
    'Container': 'CONTAINER',
    'Unique': 'UNIQUE',
}
SLOT_ALIASES = {'dish': 'dishe', 'camera': 'chamber'}

MUSKET_CRANK_MODS = (
    'mod_three_crank_capacitor',
    'mod_four_crank_capacitor',
    'mod_five_crank_capacitor',
    'mod_six_crank_capacitor',
)
ORANGE_BULLET = (0.933, 0.525, 0.157)
COVER_GOLD = (245 / 255, 196 / 255, 35 / 255)
COVER_SHADOW = (26 / 255, 38 / 255, 52 / 255)
COVER_CHARCOAL = (28 / 255, 28 / 255, 28 / 255)


class EnglishCatalogData:
    """Clean English Companion + curated override model for all 143 weapons."""

    def __init__(self):
        self.weapons = index_by_id(load_json(COMP / 'equipment/weapons.json'))
        self.mods = index_by_id(load_json(COMP / 'equipment/weapon_mods.json'))
        self.slots = load_json(COMP / 'equipment/weapon_mod_slots.json')

        self.weapons_en = index_by_id(load_json(EN_DATA / 'equipment/weapons/weapons.json'))
        self.mods_en = index_by_id(load_json(EN_DATA / 'equipment/weapon_mods.json'))
        self.ammo = index_by_id(load_json(EN_DATA / 'equipment/ammo/ammo_types.json'))
        self.qualities = index_by_id(load_json(EN_DATA / 'system/qualities.json'))
        self.effects = index_by_id(load_json(EN_DATA / 'system/damageEffects.json'))
        if 'quality_targetting_computer' in self.qualities:
            self.qualities['quality_targetting_computer']['name'] = 'Targeting Computer'

        modal = load_json(EN_SCREENS / 'inventory/modals/addItemModal.json')
        self.damage_types = modal['filter']['damageTypes']
        screen = load_json(EN_SCREENS / 'weaponsAndArmor/screen.json')
        self.slot_labels_map = screen['weapon']['modSlots']

        self.prefixes = load_json(PREFIXES_EN)
        self.descriptions = load_json(DESCS_EN)
        overrides = load_json(OVERRIDES_EN)
        self.card_overrides = overrides.get('card_overrides', {})
        self.mod_global_overrides = overrides.get('mod_global_overrides', {})
        self.mod_weapon_overrides = overrides.get('mod_weapon_overrides', {})
        self.melee_slot_labels = overrides.get('melee_slot_labels', {})
        self.heavy_site_mods = load_json(HEAVY_SITE_MODS_EN)

    @staticmethod
    def _has_cyrillic(text: str) -> bool:
        return bool(re.search(r'[а-яА-ЯёЁ]', str(text or '')))

    def slot_label(self, slot: str) -> str:
        key = slot.lower()
        key = SLOT_ALIASES.get(key, key)
        label = (
            self.slot_labels_map.get(key)
            or self.slot_labels_map.get(key.rstrip('s'))
            or MOD_TABLE_SLOT_TITLES.get(slot)
            or slot
        )
        return label.upper()

    def applicable_slots(self, wid: str) -> dict[str, list[str]]:
        """Return confirmed slot->mod_ids mapping, ignoring bogus template links."""
        if wid == 'weapon_plasma_mine':
            return {}
        raw = self.slots.get(wid) or {}
        cleaned: dict[str, list[str]] = {}
        for slot, mids in raw.items():
            valid = [mid for mid in mids if wid in ((self.mods.get(mid) or {}).get('applies_to_ids') or [])]
            if valid:
                cleaned[slot] = valid
        return cleaned

    def specific_mods(self, wid: str) -> set[tuple[str, str]]:
        """Mirror weapon_mod_policy against validated applicable_slots."""
        slots = self.applicable_slots(wid)
        pairs = [(slot, mid) for slot, ids in slots.items() for mid in ids]
        if not pairs or len(pairs) > policy.MAX_DETAILED_MODS:
            return set()
        other_refs = {
            mid
            for other_wid in self.weapons
            if other_wid != wid
            for ids in self.applicable_slots(other_wid).values()
            for mid in ids
        }
        return {
            (slot, mid)
            for slot, mid in pairs
            if mid not in other_refs and (self.mods.get(mid) or {}).get('applies_to_ids') == [wid]
        }

    def mod_name(self, mid: str) -> str:
        ov = self.mod_global_overrides.get(mid, {})
        if ov.get('name'):
            return ov['name']
        return (self.mods_en.get(mid) or {}).get('name') or f'[{mid}]'

    def ammo_name(self, weapon: dict) -> str:
        raw = weapon.get('ammoId') or ''
        names = []
        for aid in raw.split(','):
            aid = aid.strip()
            if not aid:
                continue
            name = (self.ammo.get(aid) or {}).get('name')
            if not name:
                raise ValueError(f'Missing EN ammo name for {aid}')
            names.append(name)
        return ' / '.join(names)

    def damage_type_name(self, value) -> str:
        if isinstance(value, list):
            return ' and '.join(self.damage_types.get(v, v) for v in value)
        return self.damage_types.get(value, value or '')

    def effect_names(self, weapon: dict) -> list[str]:
        out = []
        for eff in weapon.get('effects') or []:
            eid = eff.get('effectId')
            name = (self.effects.get(eid) or {}).get('name')
            if not name:
                continue
            val = eff.get('value')
            if eid == 'effect_piercing_x' and val is None:
                val = 1
            if val is not None:
                name = f'{name} {val}'
            out.append(name)
        return out

    def quality_names(self, weapon: dict) -> list[str]:
        out = []
        for q in weapon.get('qualities') or []:
            qid = q.get('qualityId')
            name = (self.qualities.get(qid) or {}).get('name')
            if not name:
                continue
            val = q.get('value')
            if qid == 'quality_tranq_x' and val is None:
                val = 3
            if val is not None:
                if name.endswith(' X'):
                    name = f"{name[:-2]} {val}"
                elif name.endswith(' (X)'):
                    name = f"{name[:-4]} ({val})"
                else:
                    name = f'{name} {val}'
            elif name.endswith(' X'):
                name = f"{name[:-2]} (X)"
            out.append(name)
        return out

    def format_number(self, value) -> str:
        if value is None or value == 0:
            return '—'
        if isinstance(value, (int, float)):
            return f'{value:+g}'
        return str(value)

    def format_perks(self, mod: dict) -> str:
        out = []
        for key in ('perk1', 'perk2'):
            val = (mod.get(key) or '').strip()
            if val:
                out.append(val)
        return ', '.join(out) if out else '—'

    def effect_text_en(self, mod: dict) -> str:
        parts = []
        for key, title, unit in (
            ('damageModifier', 'Damage', ' DC'),
            ('fireRateModifier', 'Fire Rate', ''),
            ('rangeModifier', 'Range', ' zone'),
        ):
            val = mod.get(key)
            if val is None:
                continue
            op, n = val.get('op'), val['value']
            if key == 'rangeModifier' and op in ('+', '-') and n == 1:
                parts.append(f'Range: {"increase" if op == "+" else "decrease"} by 1 zone')
            elif op == 'set':
                parts.append(f'{title}: set {n}{unit}')
            elif op in ('+', '-'):
                parts.append(f'{title}: {op}{n}{unit}')
        if mod.get('ammoOverride'):
            aid = mod['ammoOverride']
            aname = (self.ammo.get(aid) or {}).get('name') or aid
            parts.append(f'Ammo: {aname}')
        if mod.get('damageTypeOverride'):
            ov = mod['damageTypeOverride']
            raw_vals = ov['value'] if isinstance(ov.get('value'), list) else [ov.get('value')]
            tname = ' and '.join(self.damage_types.get(v, v) for v in raw_vals if v)
            action = 'Damage Type' if ov.get('op') == 'set' else 'Add Damage Type'
            parts.append(f'{action}: {tname}')
        for key, lookup, kind in (
            ('effectChanges', self.effects, 'effect'),
            ('qualityChanges', self.qualities, 'quality'),
        ):
            for ch in mod.get(key) or []:
                verb = {'gain': 'Gain', 'remove': 'Lose', 'lose': 'Lose'}.get(ch.get('op'))
                if not verb:
                    continue
                name = (lookup.get(ch.get('id')) or {}).get('name') or ch.get('id', '?')
                val = ch.get('value')
                if val is not None:
                    if name.endswith(' X'):
                        name = f'{name[:-2]} {val}'
                    else:
                        name = f'{name} {val}'
                elif name.endswith(' X'):
                    name = f'{name[:-2]} (X)'
                parts.append(f'{verb} "{name}" {kind}')
        return '; '.join(parts)

    def build_mod_row(self, wid: str | None, mid: str) -> list[str]:
        mod = self.mods[mid]
        name = self.mod_name(mid)
        prefix = self.prefixes.get(mid) or '—'
        eff = self.effect_text_en(mod)
        wt = self.format_number(mod.get('weight'))
        cost = self.format_number(mod.get('cost'))
        perks = self.format_perks(mod)
        row = {
            'name': name,
            'prefix': prefix,
            'effects': eff,
            'weight': wt,
            'cost': cost,
            'perks': perks,
        }
        row.update(self.mod_global_overrides.get(mid, {}))
        if wid:
            row.update((self.mod_weapon_overrides.get(wid) or {}).get(mid, {}))
        if not row['effects']:
            raise ValueError(f'Empty English effect text for {wid or "shared"} / {mid}')
        return [row['name'], row['prefix'], row['effects'], row['weight'], row['cost'], row['perks']]

    def ordered_slots(self, wid: str) -> list[str]:
        slots = self.applicable_slots(wid)
        return [s for s in ALL_SLOT_ORDER if slots.get(s)] + sorted(s for s in slots if s not in ALL_SLOT_ORDER)

    def build_card(self, wid: str, page: int, range_override: str | None = None) -> dict:
        base = self.weapons[wid]
        en = self.weapons_en[wid]
        rng = en.get('rangeName') or ''
        if self._has_cyrillic(rng):
            rng = ''
        if range_override is not None:
            rng = range_override
        mods_grid = []
        slots = self.applicable_slots(wid)
        for slot in self.ordered_slots(wid):
            items = [self.mod_name(mid) for mid in slots[slot]]
            if items:
                mods_grid.append({'slot': self.slot_label(slot), 'items': items})
        card = {
            'id': wid,
            'title': en['name'],
            'weight': base.get('weight', ''),
            'cost': base.get('cost', ''),
            'rarity': base.get('rarity', ''),
            'ammo': self.ammo_name(base),
            'damageType': self.damage_type_name(base.get('damageType')),
            'damage': base.get('damage', ''),
            'fireRate': base.get('fireRate', ''),
            'range': rng or '-',
            'effects': self.effect_names(base),
            'qualities': self.quality_names(base),
            'description': self.descriptions[wid],
            'image': '',
            'mods': mods_grid,
            'labels': EN_CARD_LABELS,
            'page': page,
        }
        card.update(self.card_overrides.get(wid, {}))
        if range_override is not None:
            card['range'] = range_override
        return card

    def detailed_rows(self, wid: str) -> list[tuple[str, list[str]]]:
        slots = self.applicable_slots(wid)
        return [
            (slot, self.build_mod_row(wid, mid))
            for slot in self.ordered_slots(wid)
            for mid in slots[slot]
        ]

    def make_mod_table_data(
        self,
        weapon_ids: list[str],
        allowed: set[tuple[str, str]] | None = None,
        title: str = 'SMALL GUNS MODIFICATIONS',
    ) -> dict:
        grouped: dict[str, dict[str, None]] = {}
        for wid in weapon_ids:
            for slot, mids in self.applicable_slots(wid).items():
                for mid in mids:
                    if allowed is not None and (slot, mid) not in allowed:
                        continue
                    grouped.setdefault(slot, {})[mid] = None
        ordered = [s for s in ALL_SLOT_ORDER if s in grouped] + sorted(set(grouped) - set(ALL_SLOT_ORDER))
        sections = []
        for slot in ordered:
            rows = [self.build_mod_row(None, mid) for mid in grouped[slot]]
            heading = MOD_TABLE_SLOT_TITLES.get(slot, self.slot_label(slot))
            sections.append({'category': f'{heading} MODS', 'rows': rows})
        return {
            'title': title,
            'headers': EN_TABLE_HEADERS,
            'col_widths': (92, 94, 178, 40, 34, w.CONTENT_W - 438),
            'sections': sections,
        }


def build_cover_page(source: Path) -> pymupdf.Document:
    """Create the clean English cover from original page 1 artwork."""
    cover_doc = pymupdf.open(source)
    cover_doc.select([0])
    page = cover_doc[0]

    # Strip all Russian text spans and pre-rendered WordArt bitmap overlays cleanly.
    for block in page.get_text('dict')['blocks']:
        for line in block.get('lines', []):
            for span in line.get('spans', []):
                if span.get('text', '').strip():
                    page.add_redact_annot(pymupdf.Rect(span['bbox']), fill=False, cross_out=False)
    page.apply_redactions(images=0, graphics=0, text=0)
    wordart_xrefs = [
        img[0] for img in page.get_images(full=True)
        if (rects := page.get_image_rects(img[0])) and all(r.y1 <= 180 or r.y0 >= 725 for r in rects)
    ]
    for xref in wordart_xrefs:
        page.delete_image(xref)
    page.clean_contents()

    page.insert_font(fontname='coverbold', fontfile=tables.BOLD)
    bold = pymupdf.Font(fontfile=tables.BOLD)

    vol = 'VOLUME 1'
    vol_sz = 26.0
    vol_w = bold.text_length(vol, fontsize=vol_sz)
    vol_x = 298.58 - vol_w / 2.0
    page.insert_text((vol_x, 58.5), vol, fontname='coverbold', fontsize=vol_sz, color=COVER_GOLD)

    manual = 'BROTHERHOOD MANUAL'
    man_sz = 45.0
    while man_sz > 28 and bold.text_length(manual, fontsize=man_sz) > 515:
        man_sz -= 0.5
    man_w = bold.text_length(manual, fontsize=man_sz)
    man_x = (page.rect.width - man_w) / 2.0
    man_y = 127.0
    page.insert_text((man_x + 1.8, man_y + 1.8), manual, fontname='coverbold', fontsize=man_sz, color=COVER_SHADOW)
    page.insert_text((man_x, man_y), manual, fontname='coverbold', fontsize=man_sz, color=COVER_GOLD)

    sub = 'WASTELAND ARSENAL'
    sub_sz = 44.0
    while sub_sz > 28 and bold.text_length(sub, fontsize=sub_sz) > 520:
        sub_sz -= 0.5
    sub_w = bold.text_length(sub, fontsize=sub_sz)
    sub_x = (page.rect.width - sub_w) / 2.0
    sub_y = 776.5
    page.insert_text((sub_x, sub_y), sub, fontname='coverbold', fontsize=sub_sz, color=COVER_CHARCOAL)
    return cover_doc


def render_rules_pages(rules_data: dict, page_start: int) -> tuple[pymupdf.Document, int, int]:
    """Render Damage Effects and Weapon Qualities in matching book typography."""
    regular = pymupdf.Font(fontfile=tables.REGULAR)
    bold = pymupdf.Font(fontfile=tables.BOLD)
    doc = pymupdf.open()
    icon_xref = 0

    BODY_SIZE = 12.0
    LEADING = 16.8
    INTRO_X = 39.0
    INTRO_R = 559.0
    BULLET_X = 38.9
    TEXT_X = 53.0
    TEXT_R = 559.5
    TOP_START = 105.0
    PAGE_LIMIT = 790.0
    ICON_SIZE = 11.5
    ICON_GAP = 2.0

    def draw_page_chrome(page: pymupdf.Page, title: str | None, pno: int):
        page.insert_font(fontname='body', fontfile=tables.REGULAR)
        page.insert_font(fontname='bold', fontfile=tables.BOLD)
        x, by, width, height = w.paper_placement()
        if Path(w.PAPER).is_file():
            page.insert_image(
                pymupdf.Rect(x, w.PAGE_H - (by + height), x + width, w.PAGE_H - by),
                filename=w.PAPER,
                keep_proportion=False,
            )
        if title:
            tw = bold.text_length(title, fontsize=w.TITLE_SIZE)
            page.insert_text(
                ((w.PAGE_W - tw) / 2.0, w.TITLE_TOP + w.TITLE_SIZE * 0.85),
                title, fontname='bold', fontsize=w.TITLE_SIZE, color=(0, 0, 0),
            )
            page.draw_rect(
                pymupdf.Rect(
                    w.PAGE_W_WORK_CENTER - w.RULE_W / 2.0, w.RULE_TOP,
                    w.PAGE_W_WORK_CENTER + w.RULE_W / 2.0, w.RULE_TOP + w.RULE_H,
                ),
                color=None, fill=(0, 0, 0),
            )
        lbl = str(pno)
        nx = w.MARGIN_L + 2.57 if pno % 2 == 0 else w.CONTENT_R - 2.57 - regular.text_length(lbl, fontsize=9.96)
        page.insert_text((nx, w.PAGE_NUMBER_TOP + 9.96 * 0.75), lbl, fontname='body', fontsize=9.96, color=(0, 0, 0))

    def tokenize_rich(prefix: str, body: str) -> list[tuple[str, str]]:
        tokens: list[tuple[str, str]] = []
        if prefix:
            for w_part in prefix.split(' '):
                if w_part:
                    tokens.append(('bold', w_part))
        body_toks = tables.damage_tokens(body)
        for raw_word in body_toks.split(' '):
            if not raw_word:
                continue
            tokens.append(('norm', raw_word))
        return tokens

    def tok_width(kind: str, text: str) -> float:
        f = bold if kind == 'bold' else regular
        parts = text.split(tables.DAMAGE_MARK)
        return sum(f.text_length(p, fontsize=BODY_SIZE) for p in parts) + (len(parts) - 1) * (ICON_SIZE + ICON_GAP)

    def wrap_tokens(tokens: list[tuple[str, str]], width: float) -> list[list[tuple[str, str]]]:
        lines: list[list[tuple[str, str]]] = []
        cur: list[tuple[str, str]] = []
        cur_w = 0.0
        space_w = regular.text_length(' ', fontsize=BODY_SIZE)
        for kind, word in tokens:
            ww = tok_width(kind, word)
            if cur and cur_w + space_w + ww > width:
                lines.append(cur)
                cur = [(kind, word)]
                cur_w = ww
            else:
                cur_w += (space_w if cur else 0.0) + ww
                cur.append((kind, word))
        if cur:
            lines.append(cur)
        return lines

    def draw_token_line(page: pymupdf.Page, x0: float, width: float, baseline: float, line: list[tuple[str, str]], justify: bool):
        nonlocal icon_xref
        space_w = regular.text_length(' ', fontsize=BODY_SIZE)
        words_w = sum(tok_width(k, t) for k, t in line)
        gap = (width - words_w) / (len(line) - 1) if justify and len(line) > 1 else space_w
        if gap > 2.6 * space_w:
            gap = space_w
        cx = x0
        for idx, (kind, word) in enumerate(line):
            fname = 'bold' if kind == 'bold' else 'body'
            font = bold if kind == 'bold' else regular
            parts = word.split(tables.DAMAGE_MARK)
            for p_i, part in enumerate(parts):
                if part:
                    page.insert_text((cx, baseline), part, fontname=fname, fontsize=BODY_SIZE, color=(0, 0, 0))
                    cx += font.text_length(part, fontsize=BODY_SIZE)
                if p_i < len(parts) - 1:
                    rect = pymupdf.Rect(cx, baseline - ICON_SIZE * 0.84, cx + ICON_SIZE, baseline + ICON_SIZE * 0.16)
                    icon_xref = page.insert_image(rect, filename=w.DAMAGE_ICON if not icon_xref else None, xref=icon_xref, keep_proportion=True)
                    cx += ICON_SIZE + ICON_GAP
            if idx < len(line) - 1:
                cx += gap

    section_pages = {}
    for sec_key in ('damage_effects', 'weapon_qualities'):
        sec = rules_data[sec_key]
        pno = page_start + len(doc)
        section_pages[sec_key] = pno
        page = doc.new_page(width=w.PAGE_W, height=w.PAGE_H)
        draw_page_chrome(page, sec['title'], pno)
        y = TOP_START

        intro_lines = wrap_tokens(tokenize_rich('', sec['intro']), INTRO_R - INTRO_X)
        for li, line in enumerate(intro_lines):
            draw_token_line(page, INTRO_X, INTRO_R - INTRO_X, y + BODY_SIZE * 0.85, line, justify=(li < len(intro_lines) - 1))
            y += LEADING
        y += 18.0

        for item in sec['items']:
            lines = wrap_tokens(tokenize_rich(f"{item['name']}:", item['text']), TEXT_R - TEXT_X)
            needed = len(lines) * LEADING + 9.0
            if y + needed > PAGE_LIMIT:
                pno = page_start + len(doc)
                page = doc.new_page(width=w.PAGE_W, height=w.PAGE_H)
                draw_page_chrome(page, None, pno)
                y = 48.0
            page.draw_rect(
                pymupdf.Rect(BULLET_X, y + 3.6, BULLET_X + 6.2, y + 9.8),
                color=None,
                fill=ORANGE_BULLET,
            )
            for li, line in enumerate(lines):
                draw_token_line(page, TEXT_X, TEXT_R - TEXT_X, y + BODY_SIZE * 0.85, line, justify=(li < len(lines) - 1))
                y += LEADING
            y += 9.0

    return doc, section_pages['damage_effects'], section_pages['weapon_qualities']


def renumber_source_page(page: pymupdf.Page, number: int, source_number: int):
    words = [word for word in page.get_text('words') if word[4] == str(source_number) and word[1] > 800]
    if len(words) != 1:
        raise ValueError(f'Could not find unique page number {source_number} on source page')
    page.add_redact_annot(pymupdf.Rect(words[0][:4]), fill=False, cross_out=False)
    page.apply_redactions(images=0, graphics=0, text=0)
    page.insert_font(fontname='dividernum', fontfile=tables.REGULAR)
    font = pymupdf.Font(fontfile=tables.REGULAR)
    label = str(number)
    x = w.MARGIN_L + 2.57 if number % 2 == 0 else w.CONTENT_R - 2.57 - font.text_length(label, fontsize=9.96)
    page.insert_text((x, w.PAGE_NUMBER_TOP + 9.96 * 0.75), label, fontname='dividernum', fontsize=9.96, color=(0, 0, 0))


def make_text_divider(title: str, page_num: int, out_path: Path):
    c = canvas.Canvas(str(out_path), pagesize=(w.PAGE_W, w.PAGE_H))
    w.draw_paper(c)
    w.draw_center_line(c, 360, title, 'Carlito-Bold', w.TITLE_SIZE)
    w.draw_page_number(c, page_num)
    c.showPage()
    c.save()


def render_en_card_page(
    data: EnglishCatalogData,
    wid: str,
    page_num: int,
    out_path: Path,
    detailed: bool = False,
    unique_mods: set[tuple[str, str]] = (),
    slot_labels: dict[str, str] | None = None,
    site_mod_rows: list[dict] | None = None,
    range_override: str | None = None,
):
    card = data.build_card(wid, page=page_num, range_override=range_override)
    if site_mod_rows is not None or detailed:
        rows = None if site_mod_rows is not None else data.detailed_rows(wid)
        return heavy.render_heavy(
            data,
            wid,
            page_num,
            data.prefixes,
            out_path,
            unique_mods=unique_mods,
            slot_labels=slot_labels,
            site_mod_rows=site_mod_rows,
            card=card,
            rows=rows,
            mod_table_headers=EN_CARD_MOD_HEADERS,
            unique_suffix=' UNIQUE',
            unverified_heading='MODIFICATIONS REQUIRE VERIFICATION',
            document_title_suffix='Weapons Reference',
        )
    w.render_card(card, str(out_path))
    return {'mode': 'card', 'font_size': None, 'mod_count': sum(len(c['items']) for c in card['mods'])}


def build(source: Path, output: Path, report: Path | None = None) -> dict:
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve():
        raise ValueError('Output file must differ from source PDF')

    w.register_fonts()
    data = EnglishCatalogData()
    rules_data = load_json(RULES_FRONT_EN)

    small_ids = load_json(SMALL_ORDER)
    heavy_ids = load_json(HEAVY_ORDER)
    energy_ids = list(load_json(ENERGY_ORDER))
    energy_ids.insert(energy_ids.index('weapon_assaultron_head_laser') + 1, 'weapon_institute_laser')
    melee_ids = load_json(MELEE_ORDER)
    rem = load_json(REMAINING_ORDER)
    unarmed_ids = rem['unarmed']
    thrown_ids = rem['thrown']
    explosive_ids = rem['explosives']

    all_ids = small_ids + heavy_ids + energy_ids + melee_ids + unarmed_ids + thrown_ids + explosive_ids
    if len(all_ids) != 143 or len(set(all_ids)) != 143:
        raise ValueError(f'Expected 143 unique weapons, got {len(all_ids)} ({len(set(all_ids))} unique)')

    toc: list[list] = []
    stats = {'weapons': len(all_ids)}

    with pymupdf.open(source) as original, pymupdf.open() as result, tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # 1. Cover & Front Spread
        with build_cover_page(source) as cover:
            result.insert_pdf(cover)
        toc.append([1, 'Cover', 1])

        result.insert_pdf(original, from_page=1, to_page=2)
        renumber_source_page(result[-2], 2, 2)
        renumber_source_page(result[-1], 3, 3)

        # 2. Rules Front (Damage Effects & Weapon Qualities)
        rules_doc, dmg_p, qual_p = render_rules_pages(rules_data, page_start=len(result) + 1)
        try:
            result.insert_pdf(rules_doc)
        finally:
            rules_doc.close()
        toc.append([1, 'Damage Effects', dmg_p])
        toc.append([1, 'Weapon Qualities', qual_p])

        # 3. Arsenal Spread
        result.insert_pdf(original, from_page=8, to_page=8)
        renumber_source_page(result[-1], len(result), 9)
        toc.append([1, 'Arsenal', len(result)])

        # 4. Small Guns
        small_skill_ids = [wid for wid in small_ids if data.weapons[wid].get('mainSkill') == 'SMALL_GUNS']
        small_detailed = {'weapon_boarding_pistol': data.specific_mods('weapon_boarding_pistol')}
        small_all_pairs = {
            (slot, mid)
            for wid in small_skill_ids
            for slot, mids in data.applicable_slots(wid).items()
            for mid in mids
        }
        small_excluded = set().union(*small_detailed.values())
        small_mods_data = data.make_mod_table_data(
            small_skill_ids,
            allowed=small_all_pairs - small_excluded,
            title='SMALL GUNS MODIFICATIONS',
        )
        for sec in small_mods_data['sections']:
            if sec['category'] == 'FRAME MODS':
                sec['page_break_before'] = True

        small_mods_pdf = tmp / 'small-mods.pdf'
        tables.render(small_mods_data, small_mods_pdf, page_start=len(result) + 1)
        with pymupdf.open(small_mods_pdf) as mdoc:
            small_mods_start = len(result) + 1
            result.insert_pdf(mdoc)

        result.insert_pdf(original, from_page=12, to_page=12)
        small_div = len(result)
        renumber_source_page(result[-1], small_div, 13)
        toc.append([1, 'Small Guns', small_div])
        toc.append([2, 'Small Guns Modifications', small_mods_start])
        for wid in small_ids:
            pno = len(result) + 1
            out_p = tmp / f'{wid}.pdf'
            render_en_card_page(
                data, wid, pno, out_p,
                detailed=(wid in small_detailed),
                unique_mods=small_detailed.get(wid, ()),
            )
            with pymupdf.open(out_p) as wp:
                result.insert_pdf(wp)
            toc.append([2, data.weapons_en[wid]['name'], pno])

        # 5. Heavy Guns
        result.insert_pdf(original, from_page=56, to_page=56)
        heavy_div = len(result)
        renumber_source_page(result[-1], heavy_div, 57)
        toc.append([1, 'Heavy Guns', heavy_div])
        for wid in heavy_ids:
            pno = len(result) + 1
            out_p = tmp / f'{wid}.pdf'
            site_mods = (data.heavy_site_mods.get(wid) or {}).get('mods')
            render_en_card_page(data, wid, pno, out_p, detailed=True, site_mod_rows=site_mods)
            with pymupdf.open(out_p) as wp:
                result.insert_pdf(wp)
            toc.append([2, data.weapons_en[wid]['name'], pno])

        # 6. Energy Weapons (Unified table + Institute Laser + 3 detailed cards)
        energy_on_card = {'weapon_gamma_gun', 'weapon_acid_soaker', 'weapon_assaultron_head_laser'}
        energy_ref_ids = [wid for wid in energy_ids if wid not in energy_on_card]
        energy_ref_pairs = {
            (slot, mid)
            for wid in energy_ref_ids
            for slot, mids in data.applicable_slots(wid).items()
            for mid in mids
            if mid not in MUSKET_CRANK_MODS and mid != 'mod_fusion_mag'
        }
        energy_mods_data = data.make_mod_table_data(
            energy_ref_ids,
            allowed=energy_ref_pairs,
            title='ENERGY WEAPON MODIFICATIONS',
        )
        # Append Laser Musket Crank Capacitors and Alien Blaster Fusion Mag
        musket_rows = [data.build_mod_row('weapon_laser_musket', mid) for mid in MUSKET_CRANK_MODS]
        energy_mods_data['sections'].append({
            'category': 'UNIQUE CAPACITORS — LASER MUSKET',
            'page_break_before': True,
            'rows': musket_rows,
        })
        energy_mods_data['sections'].append({
            'category': 'UNIQUE MAGAZINE — ALIEN BLASTER',
            'gap_before': 12,
            'rows': [data.build_mod_row('weapon_alien_blaster', 'mod_fusion_mag')],
        })

        energy_mods_pdf = tmp / 'energy-mods.pdf'
        tables.render(energy_mods_data, energy_mods_pdf, page_start=len(result) + 1)
        with pymupdf.open(energy_mods_pdf) as edoc:
            energy_mods_start = len(result) + 1
            result.insert_pdf(edoc)

        result.insert_pdf(original, from_page=79, to_page=79)
        energy_div = len(result)
        renumber_source_page(result[-1], energy_div, 80)
        toc.append([1, 'Energy Guns', energy_div])
        toc.append([2, 'Energy Weapon Modifications', energy_mods_start])
        for wid in energy_ids:
            pno = len(result) + 1
            out_p = tmp / f'{wid}.pdf'
            is_det = wid in energy_on_card
            uniq = data.specific_mods(wid) if is_det else ()
            render_en_card_page(data, wid, pno, out_p, detailed=is_det, unique_mods=uniq)
            with pymupdf.open(out_p) as wp:
                result.insert_pdf(wp)
            toc.append([2, data.weapons_en[wid]['name'], pno])

        # 7. Melee Weapons
        result.insert_pdf(original, from_page=94, to_page=94)
        melee_div = len(result)
        renumber_source_page(result[-1], melee_div, 95)
        toc.append([1, 'Melee Weapons', melee_div])
        for wid in melee_ids:
            pno = len(result) + 1
            out_p = tmp / f'{wid}.pdf'
            render_en_card_page(
                data, wid, pno, out_p,
                detailed=True,
                unique_mods=data.specific_mods(wid),
                slot_labels={'Unique': data.melee_slot_labels.get(wid, 'UNIQUE')},
                range_override='-',
            )
            with pymupdf.open(out_p) as wp:
                result.insert_pdf(wp)
            toc.append([2, data.weapons_en[wid]['name'], pno])

        # 8. Unarmed, Thrown, Explosives
        for sec_title, ids, force_range in (
            ('UNARMED WEAPONS', unarmed_ids, '-'),
            ('THROWN WEAPONS', thrown_ids, None),
            ('EXPLOSIVES', explosive_ids, None),
        ):
            div_pno = len(result) + 1
            div_pdf = tmp / f'div-{sec_title.lower().replace(" ", "-")}.pdf'
            make_text_divider(sec_title, div_pno, div_pdf)
            with pymupdf.open(div_pdf) as dp:
                result.insert_pdf(dp)
            toc.append([1, sec_title.title(), div_pno])
            for wid in ids:
                pno = len(result) + 1
                out_p = tmp / f'{wid}.pdf'
                use_det = (sec_title == 'UNARMED WEAPONS')
                rng_ov = force_range
                if sec_title == 'EXPLOSIVES' and wid not in {
                    'weapon_baseball_grenade', 'weapon_dynamite', 'weapon_smoke_grenade',
                    'weapon_pulse_grenade', 'weapon_molotov', 'weapon_cryogenic_grenade',
                    'weapon_frag_grenade', 'weapon_frag_grenade_mirv', 'weapon_plasma_grenade',
                    'weapon_flash_bang', 'weapon_nuka_grenade',
                }:
                    rng_ov = '-'
                render_en_card_page(
                    data, wid, pno, out_p,
                    detailed=use_det,
                    unique_mods=data.specific_mods(wid) if use_det else (),
                    slot_labels={'Unique': data.melee_slot_labels.get(wid, 'UNIQUE')} if use_det else None,
                    range_override=rng_ov,
                )
                with pymupdf.open(out_p) as wp:
                    result.insert_pdf(wp)
                toc.append([2, data.weapons_en[wid]['name'], pno])

        # 9. Closing Pages
        for source_page in range(102, 107):
            result.insert_pdf(original, from_page=source_page - 1, to_page=source_page - 1)
            renumber_source_page(result[-1], len(result), source_page)

        result.set_toc(toc)
        result.set_metadata({
            'title': 'Brotherhood Manual — Wasteland Arsenal (Vol. 1)',
            'subject': 'Fallout 2d20 English Weapons Reference Catalog',
            'author': 'Fallout 2d20 Site / Companion',
            'creator': 'tools/build_weapon_catalog_en.py',
        })
        output.parent.mkdir(parents=True, exist_ok=True)
        result.save(str(output), garbage=4, deflate=True)
        stats['pages'] = len(result)
        stats['sections'] = {
            'damage_effects': dmg_p,
            'weapon_qualities': qual_p,
            'small_mods': small_mods_start,
            'small_guns': small_div,
            'heavy_guns': heavy_div,
            'energy_mods': energy_mods_start,
            'energy_guns': energy_div,
            'melee': melee_div,
        }

    if report:
        report = Path(report)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(
            f'# English Weapons Catalog Build Report\n\n'
            f'- Output: `{output}`\n'
            f'- Total pages: {stats["pages"]}\n'
            f'- Weapons: {stats["weapons"]}\n'
            f'- Section starts: `{json.dumps(stats["sections"])}`\n',
            encoding='utf-8',
        )
    return stats


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', nargs='?', type=Path, default=ROOT / 'Справочник оружия.pdf')
    parser.add_argument('--out', type=Path, default=ROOT / 'docs/render/samples/book-weapon-catalog-en.pdf')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args(argv)
    stats = build(args.source, args.out, args.report)
    print(stats)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
