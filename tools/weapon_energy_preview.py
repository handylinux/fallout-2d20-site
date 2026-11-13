#!/usr/bin/env python3
"""Preview the energy section: original reference tables and three source mod blocks."""
import argparse
import json
import tempfile
from pathlib import Path

import pymupdf
from reportlab.pdfgen import canvas
import build_small_guns_book as small
import companion_mods_receiver as conv
import weapon_heavy_preview as heavy
import weapon2pdf as w
import weapon_mod_policy as policy
from weapons2cards import Companion, build_card

ORDER = Path(__file__).resolve().parent.parent / 'data/weapons/energy-guns-order.json'
SOURCE_PAGES = dict(zip([
    'weapon_laser_musket', 'weapon_laser_gun', 'weapon_plasma_gun', 'weapon_gamma_gun',
    'weapon_mesmetron', 'weapon_wattz_2000', 'weapon_tesla_rifle', 'weapon_acid_soaker',
    'weapon_alien_atomizer', 'weapon_alien_disintegrator', 'weapon_alien_blaster',
    'weapon_microwave_emitter', 'weapon_arc_welder', 'weapon_assaultron_head_laser'
], range(81, 95)))
MOD_OVERRIDES = Path(__file__).resolve().parent.parent / 'data/weapons/energy-mod-overrides.json'
OVERRIDES = Path(__file__).resolve().parent.parent / 'data/weapons/energy-stat-overrides.json'
SPECIALS = Path(__file__).resolve().parent.parent / 'data/weapons/energy-specials.ru.json'

SAMPLES = [('weapon_laser_musket', 81), ('weapon_laser_gun', 82), ('weapon_plasma_gun', 83)]


MUSKET_MODS = ('mod_three_crank_capacitor', 'mod_four_crank_capacitor',
               'mod_five_crank_capacitor', 'mod_six_crank_capacitor')


def musket_reference(comp, prefixes):
    # Pick precisely the weapon-specific capacitors, not every energy mod.
    allowed = {('Capacitor', mid) for mid in MUSKET_MODS}
    data, problems = small.make_mod_data(comp, ['weapon_laser_musket'], prefixes,
        allowed=allowed, title='МОДИФИКАЦИИ ЭНЕРГЕТИЧЕСКОГО ОРУЖИЯ')
    actual = comp.slots.get('weapon_laser_musket', {}).get('Capacitor', [])
    if set(actual) != set(MUSKET_MODS):
        raise ValueError('Список конденсаторов мушкета изменился: требуется сверка')
    section = data['sections'][0]
    rows_by_id = dict(zip([mid for mid in actual if mid in MUSKET_MODS], section['rows']))
    overrides = json.loads(MOD_OVERRIDES.read_text(encoding='utf-8')).get('weapon_laser_musket', {})
    columns = {'name': 0, 'prefix': 1, 'effects': 2, 'weight': 3, 'cost': 4, 'perks': 5}
    for mid, row in rows_by_id.items():
        for key, value in overrides.get(mid, {}).items():
            if key not in columns or not isinstance(value, str):
                raise ValueError(f'{mid}: неверное поле поправки {key}')
            row[columns[key]] = value
    section['rows'] = [rows_by_id[mid] for mid in MUSKET_MODS]
    section['category'] = 'УНИКАЛЬНЫЙ КОНДЕНСАТОР — ЛАЗЕРНЫЙ МУШКЕТ'
    return data, problems


def render_energy(comp, wid, source, source_page, page_num, out):
    overrides = json.loads(OVERRIDES.read_text(encoding='utf-8')).get(wid, {})
    if wid == 'weapon_assaultron_head_laser':
        special = json.loads(SPECIALS.read_text(encoding='utf-8')).get(wid, '')
        unique = policy.specific_mods(comp, wid)
        if len(unique) != 4:
            raise ValueError('Конденсаторы лазера штурмотрона требуют сверки применимости')
        return heavy.render_heavy(comp, wid, page_num, conv.load(conv.PREFIXES), out,
                                  extra_description=special, card_overrides=overrides,
                                  unique_mods=unique,
                                  mod_overrides=json.loads(MOD_OVERRIDES.read_text(encoding='utf-8')).get(wid))
    if source_page not in (82, 83):
        special = json.loads(SPECIALS.read_text(encoding='utf-8')).get(wid, '')
        return heavy.render_source_heavy(comp, wid, page_num, source, source_page, out, extra_description=special, card_overrides=overrides)
    # These two original pages have a grid but no heading. Preserve its contents
    # and add the common heading, rather than copying any weapon illustration.
    card = build_card(comp, wid, page=page_num, image='')
    card.update(overrides)
    special = json.loads(SPECIALS.read_text(encoding='utf-8')).get(wid, '')
    if special:
        card['description'] = (card.get('description', '') + '\n\n' + special).strip()
    with pymupdf.open(source) as original:
        page = original[source_page - 1]
        matches = [word for word in page.get_text('words') if word[4] == 'КОНДЕНСАТОР']
        if len(matches) != 1:
            raise ValueError(f'{wid}: не найдено начало таблицы оригинала')
        grid_top = matches[0][1] - 12
        heading_top = grid_top - w.MODS_HEADING_GAP
        description = (card.get('description') or '').strip()
        if description and w.DESC_TOP + len(w.wrap_text(description, 'Carlito', 10, w.DESC_RIGHT-w.DESC_LEFT))*15 > heading_top - 10:
            raise ValueError(f'{wid}: описание не помещается над таблицей')
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / 'page.pdf'
            c = canvas.Canvas(str(base), pagesize=(w.PAGE_W, w.PAGE_H))
            w.draw_paper(c); w.draw_title(c, card); w.draw_stats(c, card)
            w.draw_description(c, card, max_bottom=heading_top-10)
            w.draw_center_line(c, heading_top, w.MODS_HEADING, 'Carlito-Bold', w.MODS_HEADING_SIZE)
            w.draw_page_number(c, page_num); c.showPage(); c.save()
            with pymupdf.open(base) as result:
                clip = pymupdf.Rect(0, grid_top, page.rect.width, 807)
                result[0].show_pdf_page(clip, original, source_page-1, clip=clip)
                result.save(str(out), garbage=4, deflate=True)


def build(source, output, report=None, full=False):
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve():
        raise ValueError('Выходной файл не должен совпадать с оригиналом')
    w.register_fonts()
    comp = Companion()
    if full:
        ids = json.loads(ORDER.read_text(encoding='utf-8'))
        if len(set(ids)) != len(ids) or any(wid not in SOURCE_PAGES for wid in ids):
            raise ValueError('Некорректный порядок энергетического оружия')
        weapons = [(wid, SOURCE_PAGES[wid]) for wid in ids]
    else:
        weapons = SAMPLES
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / 'heavy.pdf'
        heavy.build(source, base, weapons=[*heavy.SOURCE_PAGES, 'weapon_gatling_plasma'])
        with pymupdf.open(source) as original, pymupdf.open(base) as result:
            if len(original) < max(page for _, page in weapons):
                raise ValueError('В исходном PDF отсутствуют требуемые страницы')
            references = []
            for source_number in (78, 79):
                result.insert_pdf(original, from_page=source_number-1, to_page=source_number-1)
                small.renumber_divider(result[-1], len(result), source_number=source_number)
                references.append(len(result))
            # Continuation of the common reference, not a second weapon-page table.
            prefixes = conv.load(conv.PREFIXES)
            mod_data, problems = musket_reference(comp, prefixes)
            if full and any(wid == 'weapon_alien_blaster' for wid, _ in weapons):
                magazine, magazine_problems = small.make_mod_data(comp, ['weapon_alien_blaster'], prefixes,
                    allowed={('Magazine', 'mod_fusion_mag')}, title=mod_data['title'])
                mod_data['sections'].extend(magazine['sections'])
                problems.extend(magazine_problems)
            extra = Path(tmp) / 'musket-reference.pdf'
            small.tables.render(mod_data, extra, page_start=len(result) + 1)
            with pymupdf.open(extra) as additional:
                for i in range(len(additional)):
                    result.insert_pdf(additional, from_page=i, to_page=i)
                    references.append(len(result))
            result.insert_pdf(original, from_page=79, to_page=79)
            divider = len(result)
            small.renumber_divider(result[-1], divider, source_number=80)
            pages = []
            for wid, source_page in weapons:
                file = Path(tmp) / (wid+'.pdf')
                render_energy(comp, wid, source, source_page, len(result)+1, file)
                with pymupdf.open(file) as weapon:
                    result.insert_pdf(weapon)
                pages.append(len(result))
            output.parent.mkdir(parents=True, exist_ok=True)
            result.save(str(output), garbage=4, deflate=True)
            total = len(result)
    if report:
        Path(report).write_text('''# Энергетическое оружие: пробная сборка

'''+f'Таблицы: {references[0]}–{references[-1]}; разделитель: {divider}; оружие: {pages[0]}–{pages[-1]}; всего страниц: {total}.\n\n'+'''Первые две страницы общих таблиц скопированы с физических страниц 78–79 исходного PDF; следующая страница — продолжение общей таблицы с уникальными конденсаторами мушкета из рабочих JSON Companion. Блоки модификаций оружия взяты со страниц 81–94 оригинала, кроме конденсаторов головного лазера штурмотрона: они набраны из рабочих JSON Companion на странице оружия. Копии из PDF — временное решение, не редактируемые JSON-таблицы. Основные характеристики и описания оружия — из рабочих данных Companion; перечисленные ниже расхождения частично исправлены в energy-stat-overrides.json, остальные характеристики полностью не сверены.

## Требует проверки

- Особенность расхода патронов лазерного мушкета добавлена из оригинала; в рабочем описании Companion она отсутствует.
- Конденсаторы мушкета 3–6 зарядов: на сайте разъяснён расход зарядов; в общей таблице вместо неясной записи «Ствол X» указан расход на атаку. Вес 3-зарядного указан прочерком как на сайте.
- Четыре уникальных конденсатора головного лазера штурмотрона показаны на странице оружия: расход зарядов, перки и прочерк веса MK III взяты с сайта, отличия от Companion записаны в docs/weapon-site-comparison.md. Термоядерный магазин бластера пришельцев находится в общей таблице.
- Головной лазер штурмотрона: оригинал указывает энергоячейку и не указывает качества; Companion — ядерный блок и «Двуручное». В карточке пока выбран оригинал.
- Пистолет института и запись weapon_assaultron_head пока не добавлены: требуется проверить моды и возможный дубль головного лазера.
- Штык мушкета отсутствует в исходных общих таблицах энергетического оружия; его характеристики ещё нужно добавить после сверки.
- Для лазерного мушкета, лазерного пистолета и головного лазера исходник указывает «Проникающий 1», а в Companion числовой уровень не указан; в карточках выбран оригинал.
- Карабин Теслы: в оригинале урон 5, в Companion 4; в карточке выбран оригинал.
- Бластер пришельцев: в оригинале энергетический и радиационный урон, эффект «Порочный» и качество «Неточное»; в Companion этих значений нет. В карточке выбран оригинал.
- Страница исходного PDF с плазменным пистолетом повторяет описание лазерного пистолета; сейчас используется описание Companion.
- Списки модификаций на исходных страницах лазерного и плазменного пистолетов отличаются от рабочих списков Companion; в сборке пока использован оригинал. Следует сверить применимость и характеристики.
- Общая таблица тяжёлого оружия пока отсутствует; она требует отдельной сверки. Гатлинг-плазма остаётся без подтверждённого списка модов.
''', encoding='utf-8')
    return {'pages': total, 'references': references, 'divider': divider, 'weapons': pages}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--full', action='store_true', help='все 14 страниц оригинального энергетического раздела')
    args = parser.parse_args()
    print(build(args.source, args.out, args.report, args.full))

if __name__ == '__main__':
    main()
