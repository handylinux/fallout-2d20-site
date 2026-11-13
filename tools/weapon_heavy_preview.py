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
import weapon_mod_policy as policy
import weapon_table_borders as borders
from weapons2cards import Companion, build_card

WEAPONS = ('weapon_fat_man', 'weapon_flamer', 'weapon_gatling_laser')
ORDER_FILE = Path(__file__).resolve().parent.parent / 'data/weapons/heavy-guns-order.json'
CARD_OVERRIDES = Path(__file__).resolve().parent.parent / 'data/weapons/heavy-card-overrides.json'
SITE_SPECIFIC_MODS = Path(__file__).resolve().parent.parent / 'data/weapons/heavy-site-specific-mods.json'
MAX_DETAILED_MODS = policy.MAX_DETAILED_MODS
# Physical source pages; independent of editable output ordering.
SOURCE_PAGES = {'weapon_fat_man': 58, 'weapon_flamer': 59, 'weapon_gatling_laser': 60, 'weapon_heavy_incinerator': 61, 'weapon_junk_jet': 62, 'weapon_minigun': 63, 'weapon_missile_launcher': 64, 'weapon_50_cal_machine_gun': 65, 'weapon_auto_grenade_launcher': 66, 'weapon_broadsider': 67, 'weapon_gatling_gun': 68, 'weapon_gauss_minigun': 69, 'weapon_cryolator': 70, 'weapon_tesla_cannon': 71, 'weapon_drone_cannon': 72, 'weapon_harpoon_gun': 73, 'weapon_tear_gas_launcher': 74, 'weapon_eugene': 75, 'weapon_plasma_caster': 76, 'weapon_sten_injector': 77}
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


def render_source_heavy(comp, wid, page_num, source, source_page, out, extra_description="", card_overrides=None):
    """Preserve the original mod block as vector PDF, without weapon art."""
    card = build_card(comp, wid, page=page_num, image='')
    if card_overrides:
        card.update(card_overrides)
    if extra_description:
        card['description'] = (card.get('description', '') + '\n\n' + extra_description).strip()
    with pymupdf.open(source) as original:
        page = original[source_page - 1]
        words = [x for x in page.get_text('words') if 'МОДИФИКАЦИ' in x[4]]
        if len(words) != 1:
            raise ValueError(f'{wid}: не найден заголовок модификаций на странице {source_page}')
        top = words[0][1] - 5
        description = (card.get('description') or '').strip()
        desc_bottom = w.DESC_TOP + len(w.wrap_text(description, 'Carlito', 10, w.DESC_RIGHT - w.DESC_LEFT)) * 15 if description else w.DESC_TOP
        target_top = max(top, desc_bottom + 9)
        if target_top >= 807:
            raise ValueError(f'{wid}: описание не помещается над таблицей оригинала')
        with tempfile.TemporaryDirectory() as tmp:
            base = str(Path(tmp) / 'base.pdf')
            c = canvas.Canvas(base, pagesize=(w.PAGE_W, w.PAGE_H))
            c.setTitle(f"{card['title']} — справочник оружия")
            w.draw_paper(c)
            w.draw_title(c, card)
            w.draw_stats(c, card)
            w.draw_description(c, card, max_bottom=target_top - 8)
            w.draw_page_number(c, page_num)
            c.showPage()
            c.save()
            with pymupdf.open(base) as result:
                clip = pymupdf.Rect(0, top, page.rect.width, 807)
                borders.place_source_block(result[0], original, source_page - 1, clip, target_top)
                result.save(str(out), garbage=4, deflate=True)
    return {'mode': 'source', 'font_size': None, 'mod_count': None}


def render_heavy(comp, wid, page_num, prefixes, out, extra_description='', card_overrides=None, unique_slots=(), unique_mods=(), mod_overrides=None, slot_labels=None, site_mod_rows=None):
    card = build_card(comp, wid, page=page_num, image='')
    if card_overrides:
        card.update(card_overrides)
    if extra_description:
        card['description'] = (card.get('description', '') + '\n\n' + extra_description).strip()
    if wid == 'weapon_gatling_plasma' and site_mod_rows is None:
        # The slot list conflicts with applies_to_ids; do not claim it has no mods.
        c = canvas.Canvas(str(out), pagesize=(w.PAGE_W, w.PAGE_H))
        w.draw_paper(c); w.draw_title(c, card); w.draw_stats(c, card)
        w.draw_description(c, card, max_bottom=700)
        w.draw_center_line(c, 710, 'МОДИФИКАЦИИ ТРЕБУЮТ ПРОВЕРКИ', 'Carlito-Bold', w.MODS_HEADING_SIZE)
        w.draw_page_number(c, page_num); c.showPage(); c.save()
        return {'mode': 'unverified', 'font_size': None, 'mod_count': 0}
    if site_mod_rows is not None:
        fields = ('name', 'prefix', 'effects', 'weight', 'cost', 'perks')
        rows = [(item['slot'], [item[key] for key in fields]) for item in site_mod_rows]
    else:
        rows = build_rows(comp, wid, prefixes)
    if not rows:
        w.render_card(card, str(out))
        return {'mode': 'none', 'font_size': None, 'mod_count': 0}
    if len(rows) > MAX_DETAILED_MODS:
        missing = [mid for ids in (comp.slots.get(wid) or {}).values() for mid in ids
                   if not (comp.mods_ru.get(mid) or {}).get('name')]
        if missing:
            raise ValueError(f'{wid}: нет названий модов: {", ".join(missing)}')
        w.render_card(card, str(out))
        return {'mode': 'names', 'font_size': None, 'mod_count': len(rows)}
    # Fixed dimensions and content-driven heights, so no clipping or distortion.
    widths = [65, 72, 72, 171, 30, 31, w.CONTENT_W - 441]
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for idx, color in enumerate([w.BEIGE, w.ORANGE]):
            path = str(Path(tmp) / f'icon-{idx}.jpg')
            w.flatten_on_color(w.DAMAGE_ICON, 10, 10, color, dpi=144).save(path, 'JPEG', quality=95)
            paths.append(path)

        unique_mods = set(unique_mods)
        ordered_slots = comp.slots.get(wid) or {}
        slot_order = [s for s in ORDER if ordered_slots.get(s)] + sorted(s for s in ordered_slots if s not in ORDER and ordered_slots[s])
        ids_in_order = ([(item['slot'], item['id']) for item in site_mod_rows] if site_mod_rows is not None
                        else [(slot, mid) for slot in slot_order for mid in ordered_slots[slot]])
        valid_fields = {'name': 0, 'prefix': 1, 'effects': 2, 'weight': 3, 'cost': 4, 'perks': 5}
        for (_, mid), (_, values) in zip(ids_in_order, rows):
            for field, value in (mod_overrides or {}).get(mid, {}).items():
                if field not in valid_fields or not isinstance(value, str):
                    raise ValueError(f'{wid}: неверное поле поправки {mid}.{field}')
                values[valid_fields[field]] = value

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
                is_unique = slot in unique_slots or ids_in_order[index - 1] in unique_mods
                group = (slot, is_unique)
                if group != prev:
                    if prev is not None:
                        commands.append(('SPAN', (0, group_start), (0, index - 1)))
                    group_start, group_index, prev = index, group_index + 1, group
                color = w.BEIGE if group_index % 2 == 0 else w.ORANGE
                label = (slot_labels or {}).get(slot, comp.slot_label(slot)) + (' УНИКАЛЬНЫЙ' if is_unique else '')
                def value_cell(j, value):
                    cell_style = centre if j in (3, 4, 5) else style
                    if j in (0, 1):
                        # Avoid splitting a single long Russian name into a trailing letter.
                        word_width = max((w.sw(word, 'Carlito', font_size) for word in value.split()), default=0)
                        if word_width > widths[j + 1] - 4:
                            fit_size = max(6.5, font_size * (widths[j + 1] - 4) / word_width)
                            cell_style = ParagraphStyle(f'fit-{index}-{j}', parent=style, fontSize=fit_size)
                    return paragraph(value, cell_style, paths[group_index % 2])
                cells.append([paragraph(label, white, paths[group_index % 2])] +
                             [value_cell(j, value) for j, value in enumerate(values)])
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
        c.setStrokeColor(w.BLACK); c.setLineWidth(.7)
        c.rect(w.MARGIN_L + .35, w.y_from_top(w.MODS_BOTTOM) + .35, w.CONTENT_W - .7, height - .7, stroke=1, fill=0)
        w.draw_page_number(c, page_num)
        c.showPage()
        c.save()
        return {'mode': 'detailed', 'font_size': font_size, 'mod_count': len(rows)}


def heavy_reference_data(comp, weapons, prefixes):
    # The table contains shared mods usable by the heavy section (including
    # BIG_GUNS items placed elsewhere by the original book). A name-only card
    # also contributes any otherwise unique mods, so its details are never lost.
    small_ids = json.loads(small.ORDER.read_text(encoding='utf-8'))
    refs = list(dict.fromkeys(list(weapons) + [wid for wid in small_ids
                            if wid in comp.weapons and comp.weapons[wid].get('mainSkill') == 'BIG_GUNS']))
    allowed = set()
    for wid in refs:
        slot_map = comp.slots.get(wid) or {}
        many = sum(len(ids) for ids in slot_map.values()) > MAX_DETAILED_MODS
        for slot, ids in slot_map.items():
            for mid in ids:
                mod = comp.mods.get(mid)
                if many or mod is None or len(set(mod.get('applies_to_ids') or [])) > 1:
                    allowed.add((slot, mid))
    if not allowed:
        return None, []
    return small.make_mod_data(comp, refs, prefixes, allowed=allowed,
                               title='МОДИФИКАЦИИ ТЯЖЁЛОГО ОРУЖИЯ')


def confirmed_common_mod_data(comp):
    """Load source-checked repeated heavy mods; preserve weapon-specific variants."""
    path = Path(__file__).resolve().parent.parent / 'data/weapons/heavy-common-mods.ru.json'
    raw = json.loads(path.read_text(encoding='utf-8'))
    by_slot = {}
    masks = []
    for entry in raw['mods']:
        mid, slot = entry['id'], entry['slot']
        mod = comp.mods.get(mid)
        if not mod or not entry['weapons']:
            raise ValueError(f'{mid}: common heavy mod missing in Companion')
        for wid in entry['weapons']:
            if wid not in (mod.get('applies_to_ids') or []) or mid not in (comp.slots.get(wid) or {}).get(slot, []):
                raise ValueError(f'{mid}: applicability/slot requires re-check for {wid}')
        for mask in entry['mask_rows']:
            if int(mask['page']) != SOURCE_PAGES.get(entry['weapons'][entry['mask_rows'].index(mask)] if len(entry['weapons']) == len(entry['mask_rows']) else entry['weapons'][0]):
                raise ValueError(f'{mid}: wrong source-page mapping in common heavy table')
            masks.append(mask)
        by_slot.setdefault(slot, []).append([entry['name'], entry['prefix'], entry['effects'],
                                             entry['weight'], entry['cost'], entry['perks']])
    order = [slot for slot in small.SLOT_ORDER if slot in by_slot]
    order += sorted(set(by_slot) - set(order))
    sections = [{'category': f'МОДИФИКАЦИИ {small.SLOT_TITLES.get(slot, slot.upper())}',
                 'rows': by_slot[slot]} for slot in order]
    data = {'title': 'МОДИФИКАЦИИ ТЯЖЁЛОГО ОРУЖИЯ', 'sections': sections}
    return data, masks


def mask_common_mod_details(source_doc, mask_rows):
    """Leave each source mod's name on its weapon card; move details to table."""
    pages = set()
    for row in mask_rows:
        page_index = int(row['page']) - 1
        page = source_doc[page_index]
        y0, y1 = float(row['y0']), float(row['y1'])
        cells = []
        for drawing in page.get_drawings():
            rect, fill = drawing['rect'], drawing.get('fill')
            if (fill and abs(rect.y0-y0) < .4 and abs(rect.y1-y1) < .4
                    and rect.x0 >= 80 and rect.x1 < 570 and 15 <= rect.width < 300):
                cells.append(pymupdf.Rect(rect))
        cells.sort(key=lambda r: r.x0)
        if len(cells) < 6:
            raise ValueError(f"{row['page']}: не нашёл шесть ячеек в строке {row['source_name']}")
        name_cell = cells[0]
        row_words = [word[4] for word in page.get_text('words')
                     if name_cell.x0 <= (word[0]+word[2])/2 <= name_cell.x1
                     and y0 <= (word[1]+word[3])/2 <= y1]
        if not row_words:
            raise ValueError(f"{row['page']}: пустое имя в строке {row['source_name']}")
        # Keep the first cell (mod name); redact prefix/effects/weight/cost/perk only.
        rect = pymupdf.Rect(cells[1].x0 + .5, y0 + .4, max(c.x1 for c in cells) - .5, y1 - .4)
        page.add_redact_annot(rect, fill=False, cross_out=False)
        pages.add(page_index)
    for index in pages:
        source_doc[index].apply_redactions(images=0, graphics=0, text=0)


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
    card_overrides = json.loads(CARD_OVERRIDES.read_text(encoding='utf-8'))
    site_specific = json.loads(SITE_SPECIFIC_MODS.read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / 'small-guns.pdf'
        # The small-guns reference contains only SMALL_GUNS modifications.
        small.build(source, base)
        mod_data, mask_boxes = confirmed_common_mod_data(comp)
        diagnostics.append('В общей таблице приведены моды, повторяющиеся в исходных тяжёлых карточках; одинаковые названия с разными параметрами записаны отдельными вариантами.')
        diagnostics.append('weapon_gatling_plasma: применены пять модов сайта; 17 конфликтующих слотов Companion не использованы.')
        with pymupdf.open(base) as base_pdf, pymupdf.open(source) as original, pymupdf.open() as result:
            if original.page_count < 57:
                raise ValueError('В исходном PDF нужно минимум 57 страниц')
            result.insert_pdf(base_pdf)
            mods_start = len(result) + 1
            mod_file = Path(tmp) / 'heavy-mods.pdf'
            small.tables.render(mod_data, mod_file, page_start=mods_start)
            with pymupdf.open(mod_file) as mod_pdf:
                mods_pages = len(mod_pdf)
                result.insert_pdf(mod_pdf)
            mask_common_mod_details(original, mask_boxes)
            source_for_cards = Path(tmp) / 'heavy-source-with-common-mods-extracted.pdf'
            original.save(source_for_cards, garbage=4, deflate=True)
            result.insert_pdf(original, from_page=56, to_page=56)
            divider = len(result)
            small.renumber_divider(result[-1], divider, source_number=57)
            for index, wid in enumerate(weapons):
                path = Path(tmp) / f'heavy-{index}.pdf'
                if wid in SOURCE_PAGES:
                    info = render_source_heavy(comp, wid, len(result) + 1, source_for_cards, SOURCE_PAGES[wid], path,
                                               card_overrides=card_overrides.get(wid))
                else:
                    info = render_heavy(comp, wid, len(result) + 1, prefixes, path,
                                        card_overrides=card_overrides.get(wid),
                                        site_mod_rows=site_specific.get(wid, {}).get('mods'))
                if info['mode'] == 'names':
                    diagnostics.append(f"{wid}: {info['mod_count']} модов, показаны только названия; характеристики в таблице модов тяжёлого оружия")
                elif info['font_size'] is not None and info['font_size'] < 8.4:
                    diagnostics.append(f"{wid}: компактная таблица, шрифт {info['font_size']} pt")
                with pymupdf.open(path) as doc:
                    result.insert_pdf(doc)
            output.parent.mkdir(parents=True, exist_ok=True)
            result.save(str(output), garbage=4, deflate=True)
            total = len(result)
        if report:
            report = Path(report)
            report.parent.mkdir(parents=True, exist_ok=True)
            text = '# Тяжёлое оружие: проверка сборки\n\n'
            text += f'Общая таблица тяжёлых модов: {mods_pages} стр. (только моды с одинаковыми подтверждёнными параметрами); разделитель: {divider}; оружие: {len(weapons)}; всего страниц: {total}.\n\n'
            text += 'Блоки модификаций для оружия взяты из исходного PDF. Подтверждённый общий «Прицел стрелка» перенесён в таблицу; на страницах оружия сохранено только название. Для гатлинг-плазмы пять модификаций взяты с сайта; их сверка с книгами не завершена. Подробная сверка исходника с Companion приведена в docs/weapon-heavy-mods-comparison.md.\n\n'
            text += '## Требует внимания\n\n' + ('\n'.join('- ' + x for x in diagnostics) if diagnostics else 'Не обнаружено.') + '\n'
            report.write_text(text, encoding='utf-8')
        return {'mods_start': mods_start, 'mods_pages': mods_pages, 'divider': divider, 'pages': total, 'weapons': len(weapons), 'issues': len(diagnostics)}


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
