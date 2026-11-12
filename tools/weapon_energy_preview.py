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
from weapons2cards import Companion, build_card

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
    section['rows'] = [rows_by_id[mid] for mid in MUSKET_MODS]
    section['category'] = 'УНИКАЛЬНЫЙ КОНДЕНСАТОР — ЛАЗЕРНЫЙ МУШКЕТ'
    return data, problems


def render_energy(comp, wid, source, source_page, page_num, out):
    if source_page == 81:
        return heavy.render_source_heavy(comp, wid, page_num, source, source_page, out, extra_description=json.loads(SPECIALS.read_text(encoding="utf-8"))[wid])
    # These two original pages have a grid but no heading. Preserve its contents
    # and add the common heading, rather than copying any weapon illustration.
    card = build_card(comp, wid, page=page_num, image='')
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


def build(source, output, report=None):
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve():
        raise ValueError('Выходной файл не должен совпадать с оригиналом')
    w.register_fonts()
    comp = Companion()
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / 'heavy.pdf'
        heavy.build(source, base, weapons=[*heavy.SOURCE_PAGES, 'weapon_gatling_plasma'])
        with pymupdf.open(source) as original, pymupdf.open(base) as result:
            if len(original) < 83:
                raise ValueError('В исходном PDF нужно минимум 83 страницы')
            references = []
            for source_number in (78, 79):
                result.insert_pdf(original, from_page=source_number-1, to_page=source_number-1)
                small.renumber_divider(result[-1], len(result), source_number=source_number)
                references.append(len(result))
            # Continuation of the common reference, not a second weapon-page table.
            mod_data, problems = musket_reference(comp, conv.load(conv.PREFIXES))
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
            for wid, source_page in SAMPLES:
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

'''+f'Таблицы: {references[0]}–{references[-1]}; разделитель: {divider}; оружие: {pages[0]}–{pages[-1]}; всего страниц: {total}.\n\n'+'''Первые две страницы общих таблиц скопированы с физических страниц 78–79 исходного PDF; следующая страница — продолжение общей таблицы с уникальными конденсаторами мушкета из рабочих JSON Companion. Блоки модификаций оружия — со страниц 81–83 оригинала. Копии из PDF — временное решение, не редактируемые JSON-таблицы. Основные характеристики и описания оружия — из рабочих данных Companion и с оригиналом не сверены.

## Требует проверки

- Особенность расхода патронов лазерного мушкета добавлена из оригинала; в рабочем описании Companion она отсутствует.
- Конденсаторы мушкета 3–6 зарядов помещены в общую таблицу: характеристики взяты из Companion, в оригинальных общих таблицах они отсутствуют. Запись качества «Ствол X» и вес 3-зарядного требуют проверки; вес отсутствует в Companion и обозначен «?».
- Штык мушкета отсутствует в исходных общих таблицах энергетического оружия; его характеристики ещё нужно добавить после сверки.
- Для лазерного мушкета и лазерного пистолета исходник указывает «Проникающий 1», а в Companion у эффекта не указан числовой уровень; в текущих карточках он не отображается. Нужна сверка значений.
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
    args = parser.parse_args()
    print(build(args.source, args.out, args.report))

if __name__ == '__main__':
    main()
