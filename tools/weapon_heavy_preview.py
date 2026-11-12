#!/usr/bin/env python3
"""Build a preview or full heavy-weapon section with detailed mod stats."""
from __future__ import annotations

import argparse
import json
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
ORDER_FILE = Path(__file__).resolve().parent.parent / 'data/weapons/heavy-guns-order.json'
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
            result.append((slot, [name, prefix, conv.effect_text(mod, effects, qualities, ammo, comp.damage_types),
                                  conv.number(mod.get('weight')), conv.number(mod.get('cost')), conv.perks(mod)]))
    return result


def render_heavy(comp, wid, page_num, prefixes, out):
    card = build_card(comp, wid, page=page_num, image='')
    rows = build_rows(comp, wid, prefixes)
    if not rows:
        w.render_card(card, str(out))
        return {'font_size': None, 'mod_count': 0}
    # Fixed dimensions and content-driven heights, so no clipping or distortion.
    widths = [65, 72, 72, 171, 30, 31, w.CONTENT_W - 441]
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for idx, color in enumerate([w.BEIGE, w.ORANGE]):
            path = str(Path(tmp) / f'icon-{idx}.jpg')
            w.flatten_on_color(w.DAMAGE_ICON, 10, 10, color, dpi=144).save(path, 'JPEG', quality=95)
            paths.append(path)

        def make_table(font_size, padding):
            leading = max(10.0, font_size * 1.23)
            style = ParagraphStyle('heavy', fontName='Carlito', fontSize=font_size, leading=leading, alignment=TA_LEFT)
            centre = ParagraphStyle('heavy-center', parent=style, alignment=TA_CENTER)
            white = ParagraphStyle('heavy-heading', parent=centre, fontName='Carlito-Bold', textColor=w.WHITE)
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
                        ('TOPPADDING', (0, 0), (-1, -1), padding), ('BOTTOMPADDING', (0, 0), (-1, -1), padding)]
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
            return table, height

        description = (card.get('description') or '').strip()
        minimum_bottom = w.DESC_TOP + len(w.wrap_text(description, 'Carlito', 10, w.DESC_RIGHT - w.DESC_LEFT)) * 15 if description else w.DESC_TOP
        for font_size, padding in [(8.4, 3), (8.0, 2), (7.5, 1), (7.0, 1), (6.5, .5)]:
            table, height = make_table(font_size, padding)
            top = w.MODS_BOTTOM - height
            available = top - w.MODS_HEADING_GAP - 10
            if minimum_bottom <= available:
                break
        else:
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
        return {'font_size': font_size, 'mod_count': len(rows)}


def build(source, output, weapons=WEAPONS, report=None):
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve():
        raise ValueError('Выходной файл не должен совпадать с исходным PDF')
    comp = Companion()
    weapons = tuple(weapons)
    if not weapons or len(set(weapons)) != len(weapons):
        raise ValueError('Нужен неповторяющийся список оружия')
    unknown = [wid for wid in weapons if wid not in comp.weapons]
    if unknown:
        raise ValueError('Неизвестное оружие: ' + ', '.join(unknown))
    prefixes = conv.load(conv.PREFIXES)
    w.register_fonts()
    diagnostics = []
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
            for index, wid in enumerate(weapons):
                path = Path(tmp) / f'heavy-{index}.pdf'
                info = render_heavy(comp, wid, len(result) + 1, prefixes, path)
                if info['font_size'] is not None and info['font_size'] < 8.4:
                    diagnostics.append(f"{wid}: компактная таблица, шрифт {info['font_size']} pt")
                for slot, values in build_rows(comp, wid, prefixes):
                    if values[2] in ('Не указано', 'Нет данных') or '[' in values[2] or '?' in values[3:5]:
                        diagnostics.append(f"{wid} / {slot} / {values[0]}: эффект {values[2]}; вес {values[3]}; цена {values[4]}")
                with pymupdf.open(path) as doc:
                    result.insert_pdf(doc)
            output.parent.mkdir(parents=True, exist_ok=True)
            result.save(str(output), garbage=4, deflate=True)
            total = len(result)
        if report:
            report = Path(report)
            report.parent.mkdir(parents=True, exist_ok=True)
            text = '# Тяжёлое оружие: проверка сборки\n\n'
            text += f'Разделитель: {divider}; оружие: {len(weapons)}; всего страниц: {total}.\n\n'
            text += 'Рабочие данные Companion не сверены с книгой. Для сохранения одной страницы на предмет некоторые таблицы уплотнены.\n\n'
            text += '## Требует внимания\n\n' + ('\n'.join('- ' + x for x in diagnostics) if diagnostics else 'Не обнаружено.') + '\n'
            report.write_text(text, encoding='utf-8')
        return {'divider': divider, 'pages': total, 'weapons': len(weapons), 'issues': len(diagnostics)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--full', action='store_true', help='весь раздел')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args(argv)
    try:
        weapons = json.loads(ORDER_FILE.read_text(encoding='utf-8')) if args.full else WEAPONS
        print(build(args.source, args.out, weapons, args.report))
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f'Ошибка: {exc}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
