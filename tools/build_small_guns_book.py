#!/usr/bin/env python3
"""Build the small-guns book section from editable JSON, with its divider."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

import pymupdf
import companion_mods_receiver as conv
import weapon2pdf as w
import weapon_mod_policy as policy
import weapon_mods_table_unicode as tables
from weapons2cards import Companion, build_card

ROOT = Path(__file__).resolve().parent.parent
ORDER = ROOT / 'data/weapons/small-guns-order.json'
CARD_OVERRIDES = ROOT / 'data/weapons/small-guns-card-overrides.json'
MOD_OVERRIDES = ROOT / 'data/weapons/small-guns-mod-overrides.json'
SLOT_ORDER = ['Receiver', 'Barrel', 'Magazine', 'Grip', 'Stock', 'Sight',
              'Muzzle', 'Capacitor', 'Winch', 'Frame']
SLOT_TITLES = {'Receiver': 'РЕСИВЕРА', 'Barrel': 'СТВОЛА', 'Magazine': 'МАГАЗИНА',
               'Grip': 'РУКОЯТИ', 'Stock': 'ЛОЖИ', 'Sight': 'ПРИЦЕЛА', 'Muzzle': 'ДУЛА',
               'Capacitor': 'КОНДЕНСАТОРА', 'Winch': 'ЛЕБЁДКИ', 'Frame': 'РАМЫ',
               'Unique': 'УНИКАЛЬНЫЕ', 'Fuel': 'ТОПЛИВА', 'Tank': 'БАКА',
               'Nozzle': 'СОПЛА', 'Launcher': 'ПУСКОВОЙ УСТАНОВКИ',
               'Canister': 'КАНИСТРЫ', 'Camera': 'КАМЕРЫ'}


def make_mod_data(comp, weapon_ids, prefixes, allowed=None,
                  title="МОДИФИКАЦИИ СТРЕЛКОВОГО ОРУЖИЯ"):
    """Group all mods referenced by these weapons' slot lists; never guess missing IDs."""
    if len(set(weapon_ids)) != len(weapon_ids):
        raise ValueError('Повторяющийся ID оружия')
    unknown = [wid for wid in weapon_ids if wid not in comp.weapons]
    if unknown:
        raise ValueError('Неизвестные ID оружия: ' + ', '.join(unknown))
    slots = {}
    problems = []
    for wid in weapon_ids:
        for slot, ids in (comp.slots.get(wid) or {}).items():
            for mid in ids:
                if allowed is not None and (slot, mid) not in allowed:
                    continue
                slots.setdefault(slot, {})[mid] = None
                mod = comp.mods.get(mid)
                if mod is None:
                    problems.append(f'{wid}: нет записи мода {mid} (слот {slot})')
                elif wid not in (mod.get('applies_to_ids') or []):
                    problems.append(f'{wid}: {mid} есть в списке слотов, но отсутствует в applies_to_ids')
    names = {key: x.get('name', key) for key, x in comp.mods_ru.items()}
    effects = {key: x.get('name', key) for key, x in comp.effects.items()}
    qualities = {key: x.get('name', key) for key, x in comp.qualities.items()}
    ammo = {key: x.get('name', key) for key, x in comp.ammo.items()}
    sections = []
    ordered = [slot for slot in SLOT_ORDER if slot in slots] + sorted(set(slots) - set(SLOT_ORDER))
    for slot in ordered:
        rows = []
        for mid in slots[slot]:
            mod = comp.mods.get(mid)
            name = names.get(mid, f'[{mid}]')
            if mid not in names:
                problems.append(f'{mid}: нет русского названия')
            localized = comp.mods_ru.get(mid) or {}
            prefix = prefixes.get(mid) or localized.get('prefix') or names.get(mid) or 'Не указано'
            if mod is None:
                rows.append([name, prefix, 'Нет данных', '?', '?', 'Не указано'])
                continue
            description = conv.effect_text(mod, effects, qualities, ammo, comp.damage_types)
            if '[' in description:
                problems.append(f'{mid}: нераспознанное значение — {description}')
            if description == 'Не указано':
                problems.append(f'{mid}: изменения характеристик не указаны')
            for key in ('weight', 'cost'):
                if mod.get(key) is None:
                    problems.append(f'{mid}: {key} не указано')
            rows.append([name, prefix, description, conv.number(mod.get('weight')),
                         conv.number(mod.get('cost')), conv.perks(mod)])
        label = SLOT_TITLES.get(slot, f'[{slot}]')
        if slot not in SLOT_TITLES:
            problems.append(f'Неизвестная категория: {slot}')
        sections.append({'category': f'МОДИФИКАЦИИ {label}', 'rows': rows})
    if not sections:
        raise ValueError('В выбранных слотах нет модификаций')
    data = {'title': title, 'sections': sections}
    return data, problems


def renumber_divider(page, number, source_number=13):
    """Remove only source page number, preserving background and artwork."""
    words = [word for word in page.get_text('words') if word[4] == str(source_number) and word[1] > 800]
    if len(words) != 1:
        raise ValueError(f'Не удалось однозначно найти номер {source_number} на странице-разделителе')
    page.add_redact_annot(pymupdf.Rect(words[0][:4]), fill=False, cross_out=False)
    page.apply_redactions(images=0, graphics=0, text=0)
    page.insert_font(fontname='dividernum', fontfile=tables.REGULAR)
    font = pymupdf.Font(fontfile=tables.REGULAR)
    label = str(number)
    x = w.MARGIN_L + 2.57 if number % 2 == 0 else w.CONTENT_R - 2.57 - font.text_length(label, fontsize=9.96)
    page.insert_text((x, w.PAGE_NUMBER_TOP + 9.96 * .75), label,
                     fontname='dividernum', fontsize=9.96, color=(0, 0, 0))


def small_guns_reference_ids(comp, weapon_ids):
    unknown = [wid for wid in weapon_ids if wid not in comp.weapons]
    if unknown:
        raise ValueError('Неизвестные ID оружия: ' + ', '.join(unknown))
    return [wid for wid in weapon_ids if comp.weapons[wid].get('mainSkill') == 'SMALL_GUNS']


def build(source, output, report=None, toc_pdf=None, toc=None):
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve():
        raise ValueError('Выходной файл не должен совпадать с исходным PDF')
    weapon_ids = json.loads(ORDER.read_text(encoding='utf-8'))
    comp = Companion()
    prefixes = conv.load(conv.PREFIXES)
    card_overrides = conv.load(CARD_OVERRIDES)
    mod_overrides = conv.load(MOD_OVERRIDES)
    # Reference tables are grouped by skill, even if the original book put
    # weapons of other skills in the small-guns section.
    reference_ids = small_guns_reference_ids(comp, weapon_ids)
    w.register_fonts()
    # Only remove specific mods from the reference if their detailed card fits.
    import weapon_heavy_preview as detail
    detailed = {}
    fit_problems = []
    with tempfile.TemporaryDirectory() as trial:
        for wid in reference_ids:
            specific = policy.specific_mods(comp, wid)
            if not specific:
                continue
            try:
                detail.render_heavy(comp, wid, 1, prefixes, Path(trial) / 'trial.pdf', unique_mods=specific,
                                    card_overrides=card_overrides.get(wid), mod_overrides=mod_overrides.get(wid))
            except ValueError as exc:
                fit_problems.append(f'{wid}: подробная таблица не помещается; моды оставлены в общей таблице ({exc})')
            else:
                detailed[wid] = specific
    all_pairs = {(slot, mid) for wid in reference_ids
                 for slot, mids in (comp.slots.get(wid) or {}).items() for mid in mids}
    excluded = set().union(*detailed.values()) if detailed else set()
    data, problems = make_mod_data(comp, reference_ids, prefixes, allowed=all_pairs - excluded)
    # Keep the final frame category on page 13, as in the approved four-page reference.
    for section in data['sections']:
        if section['category'] == 'МОДИФИКАЦИИ РАМЫ':
            section['page_break_before'] = True
    problems.extend(fit_problems)
    for wid, pairs in detailed.items():
        for slot, mid in sorted(pairs):
            mod = comp.mods.get(mid) or {}
            if not (mod_overrides.get(wid, {}).get(mid) or {}).get('effects') and conv.effect_text(mod, {}, {}, {}) == 'Не указано':
                problems.append(f'{wid}: {slot} / {mid}: эффект не указан в Companion, на странице оставлено «Не указано»')
    with pymupdf.open(source) as original:
        if original.page_count < 13:
            raise ValueError('В исходном PDF нужно минимум 13 страниц')
        with tempfile.TemporaryDirectory() as tmp, pymupdf.open() as result:
            result.insert_pdf(original, from_page=0, to_page=2)
            if toc_pdf is not None:
                with pymupdf.open(toc_pdf) as toc_doc:
                    result.insert_pdf(toc_doc)
            front_start = len(result) + 1
            result.insert_pdf(original, from_page=3, to_page=8)
            if toc_pdf is not None:
                # The TOC shifts the copied front-matter pages; renumber the
                # printed numbers to the new positions (original 4..9).
                for source_number in range(4, 10):
                    new_number = front_start + (source_number - 4)
                    renumber_divider(result[new_number - 1], new_number,
                                     source_number=source_number)
            if toc is not None:
                # Front-matter sections: original pages 4, 6 and 9.
                toc.append([1, 'ЭФФЕКТЫ УРОНА', front_start])
                toc.append([1, 'КАЧЕСТВА ОРУЖИЯ', front_start + 2])
                toc.append([1, 'АРСЕНАЛ', front_start + 5])
            mod_file = Path(tmp) / 'mods.pdf'
            tables.render(data, mod_file, page_start=len(result) + 1)
            with pymupdf.open(mod_file) as mod_pdf:
                mod_pages = mod_pdf.page_count
                mod_start = len(result) + 1
                result.insert_pdf(mod_pdf)
            result.insert_pdf(original, from_page=12, to_page=12)
            divider_number = len(result)
            renumber_divider(result[-1], divider_number)
            if toc is not None:
                toc.append([1, 'СТРЕЛКОВОЕ ОРУЖИЕ', divider_number])
                toc.append([2, 'МОДИФИКАЦИИ СТРЕЛКОВОГО ОРУЖИЯ', mod_start])
            for i, wid in enumerate(weapon_ids):
                card = build_card(comp, wid, page=len(result) + 1, image='')
                page_file = Path(tmp) / f'weapon-{i}.pdf'
                if wid in detailed:
                    detail.render_heavy(comp, wid, len(result) + 1, prefixes, page_file,
                                        unique_mods=detailed[wid], card_overrides=card_overrides.get(wid),
                                        mod_overrides=mod_overrides.get(wid))
                else:
                    card.update(card_overrides.get(wid, {}))
                    w.render_card(card, str(page_file))
                with pymupdf.open(page_file) as weapon_page:
                    result.insert_pdf(weapon_page)
                if toc is not None:
                    toc.append([2, comp.weapon_name(wid), len(result)])
            output.parent.mkdir(parents=True, exist_ok=True)
            result.save(str(output), garbage=4, deflate=True)
            total = len(result)
    if report:
        report = Path(report)
        report.parent.mkdir(parents=True, exist_ok=True)
        counts = ', '.join(f"{s['category']}: {len(s['rows'])}" for s in data['sections'])
        report.write_text('# Таблицы стрелкового оружия: проверка данных\n\n'
                          f'Оружия: {len(weapon_ids)}. Страниц модов: {mod_pages}. '
                          f'Разделитель: стр. {divider_number}. Всего страниц: {total}.\n\n'
                          f'Категории: {counts}.\n\n'
                          'Немногочисленные уникальные моды приведены подробно на странице оружия, если таблица помещается; из общей таблицы они исключены. '
                          'Отбор по спискам слотов оружия в рабочей копии Companion. '
                          'Пустые поля не интерпретируются как нули; совпадение правил с книгой не проверено.\n\n'
                          'Абордажный пистолет: параметры четырёх модов взяты со страницы сайта, особое правило — из оригинального PDF; расхождения и источник приведены в docs/weapon-boarding-comparison.md.\n\n'
                          '## Требует проверки\n\n' +
                          ('\n'.join(f'- {p}' for p in sorted(set(problems))) if problems else 'Не найдено.') + '\n',
                          encoding='utf-8')
    return {'pages': total, 'mods_pages': mod_pages, 'divider': divider_number,
            'weapon_count': len(weapon_ids), 'issues': len(set(problems))}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args(argv)
    try:
        result = build(args.source, args.out, args.report)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f'Ошибка: {exc}\n')
    print(result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
