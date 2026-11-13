#!/usr/bin/env python3
"""Assemble a broad working catalogue and preserve the original closing art."""
import argparse
import json
import tempfile
from pathlib import Path

import pymupdf
from reportlab.pdfgen import canvas
import build_small_guns_book as small
import companion_mods_receiver as conv
import weapon2pdf as w
import weapon_heavy_preview as heavy
import weapon_melee_preview as melee
import weapon_mod_policy as policy
from weapons2cards import Companion, build_card

ROOT = Path(__file__).resolve().parent.parent
ORDER = ROOT / 'data/weapons/remaining-order.json'
OVERRIDES = ROOT / 'data/weapons/remaining-card-overrides.json'
TITLES = {'energy': 'ДОПОЛНИТЕЛЬНЫЕ ЭНЕРГЕТИЧЕСКИЕ МОДИФИКАЦИИ',
          'unarmed': 'МОДИФИКАЦИИ ДЛЯ БЕЗОРУЖНОГО БОЯ'}


def build(source, output, report=None):
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve():
        raise ValueError('Выходной файл совпадает с оригиналом')
    comp = Companion()
    groups = json.loads(ORDER.read_text(encoding='utf-8'))
    overrides = json.loads(OVERRIDES.read_text(encoding='utf-8'))
    mod_overrides = conv.load(melee.MOD_OVERRIDES)
    slot_labels = conv.load(melee.SLOT_LABELS)
    comp.mods_ru['mod_heavy']['name'] = 'Утяжелённая'
    comp.mods_ru['mod_lead_lining']['name'] = 'Свинцовая подкладка'
    if list(groups) != ['energy', 'unarmed', 'thrown', 'explosives']:
        raise ValueError('Некорректные категории')
    all_ids = sum(groups.values(), [])
    previous = sum([json.loads((ROOT / 'data/weapons' / f).read_text(encoding='utf-8')) for f in
                    ('small-guns-order.json', 'heavy-guns-order.json', 'energy-guns-order.json', 'melee-original-order.json')], [])
    if len(set(all_ids + previous)) != len(all_ids + previous) or any(wid not in comp.weapons for wid in all_ids):
        raise ValueError('Повторяющийся или неизвестный ID')
    prefixes = conv.load(conv.PREFIXES)
    w.register_fonts()
    problems = []
    pages = {}
    references = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        base = tmp / 'melee.pdf'
        melee.build(source, base)
        with pymupdf.open(base) as result, pymupdf.open(source) as original:
            for group, ids in groups.items():
                specific = {wid: policy.specific_mods(comp, wid) for wid in ids}
                # The plasma mine's "heavy barrel" is inconsistent with the
                # item type even though both Companion cross-links agree.
                pairs = {(slot, mid) for wid in ids if wid != 'weapon_plasma_mine'
                         for slot, mids in (comp.slots.get(wid) or {}).items() for mid in mids}
                allowed = pairs - (set().union(*specific.values()) if specific else set())
                if allowed and group != 'unarmed':
                    data, warnings = small.make_mod_data(comp, ids, prefixes, allowed=allowed,
                                               title=TITLES.get(group, 'МОДИФИКАЦИИ ОРУЖИЯ'))
                    for section in data['sections']:
                        if section['category'] == 'МОДИФИКАЦИИ УНИКАЛЬНЫЕ':
                            section['category'] = 'МОДИФИКАЦИИ ДЛЯ РАЗНЫХ ВИДОВ ОРУЖИЯ'
                    problems.extend(warnings)
                    tablefile = tmp / (group + '-mods.pdf')
                    small.tables.render(data, tablefile, page_start=len(result)+1)
                    start = len(result) + 1
                    with pymupdf.open(tablefile) as table:
                        result.insert_pdf(table)
                    references[group] = list(range(start, len(result)+1))
                if group in ('unarmed', 'thrown', 'explosives'):
                    title = {'unarmed': 'РУКОПАШНОЕ ОРУЖИЕ', 'thrown': 'МЕТАТЕЛЬНОЕ ОРУЖИЕ',
                             'explosives': 'ВЗРЫВЧАТКА'}[group]
                    divider_file = tmp / (group + '-divider.pdf')
                    c = canvas.Canvas(str(divider_file), pagesize=(w.PAGE_W, w.PAGE_H))
                    w.draw_paper(c)
                    w.draw_center_line(c, 360, title, 'Carlito-Bold', w.TITLE_SIZE)
                    w.draw_page_number(c, len(result) + 1)
                    c.showPage(); c.save()
                    with pymupdf.open(divider_file) as divider:
                        result.insert_pdf(divider)
                pages[group] = []
                for wid in ids:
                    pagefile = tmp / (wid + '.pdf')
                    card_override = dict(overrides.get(wid, {}))
                    if group == 'unarmed':
                        card_override['range'] = '-'
                    if wid == 'weapon_plasma_mine':
                        card = build_card(comp, wid, page=len(result)+1, image='')
                        card.update(card_override)
                        card['mods'] = []
                        w.render_card(card, str(pagefile))
                    else:
                        heavy.render_heavy(comp, wid, len(result)+1, prefixes, pagefile,
                                           unique_mods=specific[wid], card_overrides=card_override,
                                           mod_overrides=mod_overrides.get(wid),
                                           slot_labels={'Unique': slot_labels.get(wid, 'НЕ УТОЧНЁН')})
                    with pymupdf.open(pagefile) as page:
                        result.insert_pdf(page)
                    pages[group].append(len(result))
            closing = []
            for source_page in range(102, 107):
                result.insert_pdf(original, from_page=source_page-1, to_page=source_page-1)
                small.renumber_divider(result[-1], len(result), source_number=source_page)
                closing.append(len(result))
            output.parent.mkdir(parents=True, exist_ok=True)
            result.save(output, garbage=4, deflate=True)
            total = len(result)
    if report:
        no_slots = [wid for wid in all_ids if not comp.slots.get(wid) and not comp.weapons[wid].get('withoutMods')]
        lines = ['# Полный рабочий каталог: оставшиеся категории', '',
                 f'Всего страниц: {total}. Таблицы дополнений: {references}. Страницы оружия: {pages}. Завершающие страницы оригинала: {closing}.', '',
                 'Добавлены доступные записи Companion: пистолет института, безоружное, метательное и взрывчатка. Порядок — data/weapons/remaining-order.json. Шесть оригинальных и 25 дополнительных оружий ближнего боя описаны отдельно в weapon-melee-report.md. Данные не являются проверкой всех книг или сайта.', '',
                 '- Кулаки и Unarmed Attack объединены как подтверждённый пользователем дубль; выбрана запись unarmed_human. Опасная бритва не включена как ссылка на другое оружие.',
                 '- Голова штурмотрона не добавлена второй раз: возможный дубль головного лазера пока не подтверждён. Это не утверждение, что записи полностью идентичны.',
                 '- У плазменной мины в Companion указан тяжёлый ствол; это сомнительно для мины, поэтому на странице он не заявлен как подтверждённый. Требуется проверка по книге.',
                 '- Для баллистического кулака и перчатки-вытеснителя Companion не содержит слотов, а проверенные статьи сайта не публикуют списки модификаций.',
                 '- Общие таблицы созданы по данным Companion и требуют проверки; некоторые вес, эффекты или перки отсутствуют и обозначены вопросительным знаком либо «Не указано».',
                 '- Для безоружного боя дистанция заменена на прочерк согласно принятому правилу ближнего боя; камень оставлен среди метательного оружия.',
                 '- Данные взрывчатки, правила её применения и принадлежность к официальным источникам не сверены. Краткое описание Companion может не включать специальные правила.',
                 '- Иллюстрации оружия оставлены пустыми. Завершение скопировано из оригинала, номера страниц заменены.', '',
                 '## В проверенных источниках не приведён список модификаций', '',
                 *['- '+wid for wid in no_slots], '', '## Автоматическая диагностика таблиц', '',
                 *(['- '+x for x in problems] or ['- Замечаний нет.'])]
        Path(report).write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return {'pages': total, 'references': references, 'weapons': pages, 'closing': closing}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    args = p.parse_args()
    print(build(args.source, args.out, args.report))

if __name__ == '__main__':
    main()
