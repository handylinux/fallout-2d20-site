#!/usr/bin/env python3
"""Preview the first three heavy weapons with detailed per-weapon mod stats."""
from __future__ import annotations

import argparse
import re
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

import pymupdf
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

import build_small_guns_book as small
import companion_mods_receiver as conv
import weapon2pdf as w
from weapons2cards import Companion, build_card

WEAPONS = ('weapon_fat_man', 'weapon_flamer', 'weapon_gatling_laser')
ORDER = ['Fuel', 'Receiver', 'Capacitor', 'Barrel', 'Tank', 'Grip', 'Stock', 'Magazine', 'Sight', 'Muzzle', 'Nozzle']


def build_rows(comp, wid, prefixes):
    slots = comp.slots.get(wid) or {}
    order = [s for s in ORDER if slots.get(s)] + sorted(s for s in slots if s not in ORDER and slots[s])
    result = []
    for slot in order:
        for mid in slots[slot]:
            mod = comp.mods.get(mid)
            ru = comp.mods_ru.get(mid) or {}
            name = ru.get('name') or f'[{mid}]'
            prefix = prefixes.get(mid) or ru.get('prefix') or ru.get('name') or 'Не указано'
            if not mod:
                result.append((slot, [name, prefix, 'Нет данных', '?', '?', 'Не указано']))
                continue
            effects = {k: x.get('name', k) for k, x in comp.effects.items()}
            qualities = {k: x.get('name', k) for k, x in comp.qualities.items()}
            ammo = {k: x.get('name', k) for k, x in comp.ammo.items()}
            result.append((slot, [name, prefix, conv.effect_text(mod, effects, qualities, ammo),
                                  conv.number(mod.get('weight')), conv.number(mod.get('cost')), conv.perks(mod)]))
    return result


def render_heavy(comp, wid, page_num, prefixes, out):
    card = build_card(comp, wid, page=page_num, image='')
    rows = build_rows(comp, wid, prefixes)
    if not rows:
        w.render_card(card, str(out))
        return
    # Fixed dimensions and content-driven heights, so no clipping or distortion.
    widths = [65, 72, 72, 171, 30, 31, w.CONTENT_W - 441]
    style = ParagraphStyle('heavy', fontName='Carlito', fontSize=8.4, leading=10.3, alignment=TA_LEFT)
    centre = ParagraphStyle('heavy-center', parent=style, alignment=TA_CENTER)
    white = ParagraphStyle('heavy-heading', parent=centre, fontName='Carlito-Bold', textColor=w.WHITE)
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for idx, color in enumerate([w.BEIGE, w.ORANGE]):
            path = str(Path(tmp) / f'icon-{idx}.jpg')
            w.flatten_on_color(w.DAMAGE_ICON, 10, 10, color, dpi=144).save(path, 'JPEG', quality=95)
            paths.append(path)
        def paragraph(value, ps, icon_path):
            value = escape(value)
            safe_path = escape(icon_path, {'"': '&quot;'})
            value = re.sub(r'(?<!\w)DC(?!\w)', lambda _: f'<img src="{safe_path}" width="9" height="9" valign="middle"/> ', value)
            return Paragraph(value or ' ', ps)
        cells = [[paragraph(x, white, paths[0]) for x in ['', 'НАЗВАНИЕ', 'ПРЕФИКС', 'ЭФФЕКТЫ', 'ВЕС', 'ЦЕНА', 'ПЕРКИ']]]
        commands = [('BACKGROUND', (0, 0), (-1, 0), w.BLACK),
                    ('GRID', (0, 0), (-1, -1), .3, w.BLACK),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 2), ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                    ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]
        prev, group_start, group_index = None, 1, -1
        for index, (slot, values) in enumerate(rows, 1):
            if slot != prev:
                if prev is not None:
                    commands.append(('SPAN', (0, group_start), (0, index - 1)))
                group_start, group_index, prev = index, group_index + 1, slot
            color = w.BEIGE if group_index % 2 == 0 else w.ORANGE
            label = comp.slot_label(slot)
            cells.append([paragraph(label, white, paths[group_index % 2])] +
                         [paragraph(v, centre if j in (3, 4, 5) else style, paths[group_index % 2]) for j, v in enumerate(values)])
            commands.extend([('BACKGROUND', (1, index), (-1, index), color),
                             ('BACKGROUND', (0, index), (0, index), w.BLACK)])
        commands.append(('SPAN', (0, group_start), (0, len(rows))))
        table = Table(cells, colWidths=widths, hAlign='LEFT')
        table.setStyle(TableStyle(commands))
        _, height = table.wrap(w.CONTENT_W, w.PAGE_H)
        top = w.MODS_BOTTOM - height
        available = top - w.MODS_HEADING_GAP - 10
        description = (card.get('description') or '').strip()
        if description and w.DESC_TOP + len(w.wrap_text(description, 'Carlito', 10, w.DESC_RIGHT - w.DESC_LEFT)) * 15 > available:
            raise ValueError(f'{wid}: таблица и описание не помещаются на одну страницу')
        c = canvas.Canvas(str(out), pagesize=(w.PAGE_W, w.PAGE_H))
        c.setTitle(f"{card['title']} — справочник оружия")
        w.draw_paper(c)
        w.draw_title(c, card)
        w.draw_stats(c, card)
        w.draw_description(c, card, max_bottom=available)
        w.draw_center_line(c, top - w.MODS_HEADING_GAP, w.MODS_HEADING, 'Carlito-Bold', w.MODS_HEADING_SIZE)
        table.drawOn(c, w.MARGIN_L, w.y_from_top(w.MODS_BOTTOM))
        w.draw_page_number(c, page_num)
        c.showPage()
        c.save()


def build(source, output):
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve():
        raise ValueError('Выходной файл не должен совпадать с исходным PDF')
    comp = Companion()
    prefixes = conv.load(conv.PREFIXES)
    w.register_fonts()
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / 'small-guns.pdf'
        small.build(source, base)
        with pymupdf.open(base) as base_pdf, pymupdf.open(source) as original, pymupdf.open() as result:
            if original.page_count < 57:
                raise ValueError('В исходном PDF нужно минимум 57 страниц')
            result.insert_pdf(base_pdf)
            result.insert_pdf(original, from_page=56, to_page=56)
            divider = len(result)
            small.renumber_divider(result[-1], divider, source_number=57)
            for index, wid in enumerate(WEAPONS):
                path = Path(tmp) / f'heavy-{index}.pdf'
                render_heavy(comp, wid, len(result) + 1, prefixes, path)
                with pymupdf.open(path) as doc:
                    result.insert_pdf(doc)
            output.parent.mkdir(parents=True, exist_ok=True)
            result.save(str(output), garbage=4, deflate=True)
            return {'divider': divider, 'pages': len(result)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        print(build(args.source, args.out))
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f'Ошибка: {exc}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
