#!/usr/bin/env python3
"""Append available melee weapons to the evolving book."""
import argparse
import json
import tempfile
from pathlib import Path

import pymupdf
import build_small_guns_book as small
import companion_mods_receiver as conv
import weapon2pdf as w
import weapon_energy_preview as energy
import weapon_heavy_preview as heavy
import weapon_mod_policy as policy
from weapons2cards import Companion

ROOT = Path(__file__).resolve().parent.parent
ORDER = ROOT / 'data/weapons/melee-original-order.json'
CARD_OVERRIDES = ROOT / 'data/weapons/melee-card-overrides.json'
SLOT_LABELS = ROOT / 'data/weapons/melee-slot-labels.json'
MOD_OVERRIDES = ROOT / 'data/weapons/melee-site-mod-overrides.json'


def build(source, output, report=None, toc=None, toc_pdf=None):
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve():
        raise ValueError('Выходной файл не должен совпадать с оригиналом')
    comp = Companion()
    # Local presentation only: the shared ID's name must not contain a weapon.
    comp.mods_ru['mod_heavy']['name'] = 'Утяжелённая'
    comp.mods_ru['mod_lead_lining']['name'] = 'Свинцовая подкладка'
    ids = json.loads(ORDER.read_text(encoding='utf-8'))
    if len(ids) != len(set(ids)) or any(wid not in comp.weapons or comp.weapons[wid].get('mainSkill') != 'MELEE_WEAPONS' for wid in ids):
        raise ValueError('Неверный порядок оружия ближнего боя')
    prefixes = conv.load(conv.PREFIXES)
    overrides = json.loads(CARD_OVERRIDES.read_text(encoding="utf-8"))
    slot_labels = conv.load(SLOT_LABELS)
    mod_overrides = conv.load(MOD_OVERRIDES)
    w.register_fonts()
    specifics = {wid: policy.specific_mods(comp, wid) for wid in ids}
    # Per-weapon stats differ even for identical mod IDs; keep details on cards.
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        base = tmp / 'energy.pdf'
        energy.build(source, base, full=True, toc=toc, toc_pdf=toc_pdf)
        with pymupdf.open(base) as result, pymupdf.open(source) as original:
            references = []
            result.insert_pdf(original, from_page=94, to_page=94)
            divider = len(result)
            small.renumber_divider(result[-1], divider, source_number=95)
            if toc is not None:
                toc.append([1, 'ОРУЖИЕ БЛИЖНЕЙ БОЙ', divider])
            pages = []
            for wid in ids:
                pagefile = tmp / f'{wid}.pdf'
                card_override = dict(overrides.get(wid, {}))
                # All melee cards use the requested dash, even when a source
                # incorrectly provides a ranged-distance label.
                card_override["range"] = "-"
                heavy.render_heavy(comp, wid, len(result)+1, prefixes, pagefile,
                                   unique_mods=specifics[wid], card_overrides=card_override,
                                   mod_overrides=mod_overrides.get(wid),
                                   slot_labels={"Unique": slot_labels.get(wid, "НЕ УТОЧНЁН")})
                with pymupdf.open(pagefile) as page:
                    result.insert_pdf(page)
                pages.append(len(result))
                if toc is not None:
                    toc.append([2, comp.weapon_name(wid), len(result)])
            output.parent.mkdir(parents=True, exist_ok=True)
            result.save(output, garbage=4, deflate=True)
            total = len(result)
    if report:
        lines = ['# Оружие ближнего боя', '',
                 f'Общая таблица: {references}; разделитель: {divider}; оружие: {pages}; всего: {total}.', '',
                 f'{len(ids)} оружий из рабочих данных Companion: первые шесть по оригиналу, остальные добавлены по алфавиту. Порядок редактируется в data/weapons/melee-original-order.json. Характеристики, описания и модификации требуют сверки. Изображения оружия не вставлены.', '',
                 'Модификации подробно указаны на страницах оружия: одинаковые ID могут иметь разные характеристики для разных предметов. Техническое название слота Unique в Companion не означает, что все его моды уникальны.', '',
                 '## Известные расхождения', '',
                 '- Боевой нож: исходник указывает урон 4, Companion 3; пока указан Companion.',
                 '- Потрошитель: исходник указывает «Проникающий 1» и только два мода, Companion — «Порочный» и четыре мода. Исходник повторяет описание боевого ножа; использовано описание Companion.',
                 '- Шиш-кебаб: исходник указывает вес 1, цену 20 и редкость 0; Companion — 3, 200 и 3. Пока указан Companion, значения требуют проверки.',
                 '- У ряда оружий оригинал указывает «Проникающий 1», в Companion уровень не указан; пока указан Companion.',
                 '- Меч: в Companion есть электрошокер, которого нет в списке оригинала. Возможное дополнение требует проверки. Русское описание сверено с сайтом и Companion.',
                 '- Оружие без списка слотов и без явного withoutMods отмечено «модификации требуют проверки», а не как гарантированно лишённое модов.', '', '## Автоматическая диагностика', '']
        lines += ['- ' + p for p in problems] or ['- Замечаний нет.']
        Path(report).write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return {'pages': total, 'references': references, 'divider': divider, 'weapons': pages}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    print(build(args.source, args.out, args.report))

if __name__ == '__main__':
    main()
