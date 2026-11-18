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
import weapon_book_toc as toc_render
import rasterize_pdf
from weapon_catalog_artwork import ArtworkResolver
from weapons2cards import Companion, build_card

ROOT = Path(__file__).resolve().parent.parent
ORDER = ROOT / 'data/weapons/remaining-order.json'
OVERRIDES = ROOT / 'data/weapons/remaining-card-overrides.json'
TITLES = {'energy': 'ДОПОЛНИТЕЛЬНЫЕ ЭНЕРГЕТИЧЕСКИЕ МОДИФИКАЦИИ',
          'unarmed': 'МОДИФИКАЦИИ ДЛЯ БЕЗОРУЖНОГО БОЯ'}


def _run_chain(source, output, toc, toc_pdf, report, artwork=None):
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
    mods_starts = {}
    energy_header_done = False
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        base = tmp / 'melee.pdf'
        melee.build(source, base, toc=toc, toc_pdf=toc_pdf, artwork=artwork)
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
                        if group == 'energy' and section['category'] == 'МОДИФИКАЦИИ КОНДЕНСАТОРА':
                            # Keep this category together instead of orphaning its last rows.
                            section['page_break_before'] = True
                    problems.extend(warnings)
                    tablefile = tmp / (group + '-mods.pdf')
                    small.tables.render(data, tablefile, page_start=len(result)+1)
                    start = len(result) + 1
                    with pymupdf.open(tablefile) as table:
                        result.insert_pdf(table)
                    references[group] = list(range(start, len(result)+1))
                    if toc is not None:
                        mods_starts[group] = start
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
                    if toc is not None:
                        toc.append([1, title, len(result)])
                pages[group] = []
                for wid in ids:
                    pagefile = tmp / (wid + '.pdf')
                    card_override = dict(overrides.get(wid, {}))
                    # The generated card can supply a confirmed Russian title
                    # when Companion's localisation still contains an English
                    # placeholder (for example Rock / Pulse Mine).
                    toc_title = card_override.get('title') or comp.weapon_name(wid)
                    layer = artwork.layer_for(wid) if artwork is not None else None
                    if group == 'unarmed':
                        card_override['range'] = '-'
                    if wid == 'weapon_plasma_mine':
                        card = build_card(comp, wid, page=len(result)+1, image='')
                        card.update(card_override)
                        card['mods'] = []
                        w.render_card(card, str(pagefile), artwork=layer)
                    else:
                        heavy.render_heavy(comp, wid, len(result)+1, prefixes, pagefile,
                                           unique_mods=specific[wid], card_overrides=card_override,
                                           mod_overrides=mod_overrides.get(wid),
                                           slot_labels={'Unique': slot_labels.get(wid, 'НЕ УТОЧНЁН')},
                                           artwork=layer)
                    with pymupdf.open(pagefile) as page:
                        result.insert_pdf(page)
                    pages[group].append(len(result))
                    if toc is not None:
                        if group == 'energy' and not energy_header_done:
                            toc.append([1, 'ДОПОЛНИТЕЛЬНОЕ ЭНЕРГЕТИЧЕСКОЕ ОРУЖИЕ', len(result)])
                            toc.append([2, TITLES['energy'], mods_starts['energy']])
                            energy_header_done = True
                        toc.append([2, toc_title, len(result)])
            closing = []
            for source_page in range(102, 106):
                result.insert_pdf(original, from_page=source_page-1, to_page=source_page-1)
                small.renumber_divider(result[-1], len(result), source_number=source_page)
                closing.append(len(result))
            # The total page count must be a multiple of 4 for exact booklet
            # printing, so extra blank pages go before the back cover.
            padding = (-(len(result) + 1)) % 4
            for i in range(padding):
                # `len(result)` increases after every insertion.  Derive the
                # next printed number from the current document rather than
                # adding the loop index again, otherwise three padding pages
                # would visibly skip numbers.
                blank_pno = len(result) + 1
                blank_pdf = tmp / f'pad-blank-{i}.pdf'
                toc_render.make_blank_page(blank_pno, blank_pdf)
                with pymupdf.open(blank_pdf) as bdoc:
                    result.insert_pdf(bdoc)
            result.insert_pdf(original, from_page=105, to_page=105)
            small.renumber_divider(result[-1], len(result), source_number=106)
            closing.append(len(result))
            output.parent.mkdir(parents=True, exist_ok=True)
            result.save(output, garbage=4, deflate=True)
            total = len(result)
    if report:
        no_slots = [wid for wid in all_ids if not comp.slots.get(wid) and not comp.weapons[wid].get('withoutMods')]
        if artwork is None:
            artwork_note = 'Иллюстрации оружия не запрошены для этой технической сборки.'
        else:
            coverage = artwork.coverage()
            counts = coverage.get('counts', {})
            artwork_note = (
                'Artwork Publisher воспроизведён только по точному weapon_id из manifest: '
                f"{counts.get('replayed', 0)} страниц с экспортированными слоями; "
                f"{counts.get('manifest-page-without-exported-artwork', 0)} исходных страниц "
                'не имеют экспортированного растрового placement; замены не используются.'
            )
        lines = ['# Полный рабочий каталог: оставшиеся категории', '',
                 'Этот отчёт описывает состав и ограничения данных оставшихся категорий; он не является перечнем незавершённых действий по финальному PDF. Воспроизводимая сборка и проверки актуальной русской версии описаны в `docs/weapon-pdf.md`.', '',
                 f'Всего страниц: {total}. Таблицы дополнений: {references}. Страницы оружия: {pages}. Завершающие страницы оригинала: {closing}.', '',
                 'Добавлены доступные записи Companion: пистолет института, безоружное, метательное и взрывчатка. Порядок — data/weapons/remaining-order.json. Шесть оригинальных и 25 дополнительных оружий ближнего боя описаны отдельно в weapon-melee-report.md. Данные не являются проверкой всех книг или сайта.', '',
                 '- Кулаки и Рукопашная атака показаны отдельными карточками по подтверждению пользователя. Опасная бритва не включена: это ссылка на другое оружие.',
                 '- Голова ассаултрона не включена: это не самостоятельное оружие. Головной лазер Штурмотрона остаётся отдельной карточкой с подтверждённым Publisher artwork.',
                 '- У плазменной мины в Companion указан тяжёлый ствол; это сомнительно для мины, поэтому на странице он не заявлен как подтверждённый. Требуется проверка по книге.',
                 '- Для баллистического кулака и перчатки-вытеснителя Companion не содержит слотов, а проверенные статьи сайта не публикуют списки модификаций.',
                 '- Дополнительная таблица энергетических модов построена по записям слотов Companion для weapon_institute_laser, а не по физическим страницам 78–79; её применимость и характеристики не сверены с книгой.',
                 '- Общие таблицы созданы по данным Companion и требуют проверки; некоторые вес, эффекты или перки отсутствуют и обозначены вопросительным знаком либо «Не указано».',
                 '- Для безоружного боя дистанция заменена на прочерк согласно принятому правилу ближнего боя; камень оставлен среди метательного оружия.',
                 '- Данные взрывчатки, правила её применения и принадлежность к официальным источникам не сверены. Краткое описание Companion может не включать специальные правила.',
                 artwork_note + ' Завершение скопировано из оригинала, номера страниц заменены.', '',
                 '## В проверенных источниках не приведён список модификаций', '',
                 *['- '+wid for wid in no_slots], '', '## Автоматическая диагностика таблиц', '',
                 *(['- '+x for x in problems] or ['- Замечаний нет.'])]
        Path(report).write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return {'pages': total, 'references': references, 'weapons': pages, 'closing': closing,
            'toc': toc, 'padding': padding}


def build(source, output, report=None, with_toc=True, artwork_manifest=None,
          artwork_root=None, artwork_coverage=None, rasterize_cover=False,
          cover_dpi=rasterize_pdf.DEFAULT_COVER_DPI,
          cover_jpeg_quality=rasterize_pdf.DEFAULT_COVER_JPEG_QUALITY):
    """Build the complete Russian weapon catalogue.

    With the printed table of contents (default) this runs the chain twice:
    the first pass records where every section and weapon lands, the TOC is
    rendered with those page numbers shifted by its own page count, and the
    second pass rebuilds the document with the TOC inserted after the
    STAND BY spread (page 4).  Page numbers must match the shifted ones.

    If ``artwork_manifest`` is supplied, the final pass replays only artwork
    that has an exact ``weapon_id`` match in that manifest.  The fast first
    pass deliberately omits it because it is used solely to calculate page
    numbers.  No final-page fallback or substitute image is permitted.  When
    ``rasterize_cover`` is set, only the complete Publisher cover is rendered
    as one opaque RGB JPEG after the verified vector book is assembled.
    """
    source, output = Path(source), Path(output)
    artwork = ArtworkResolver(artwork_manifest, artwork_root, source)

    def finish(stats):
        if artwork.enabled:
            artwork.assert_all_available_layers_requested()
        if rasterize_cover:
            stats['cover'] = rasterize_pdf.rasterize_cover_page(
                output, output, dpi=cover_dpi, jpeg_quality=cover_jpeg_quality
            )
        else:
            stats['cover'] = {'rasterized': False}
        coverage = artwork.coverage()
        if artwork_coverage is not None:
            artwork.write_coverage(artwork_coverage)
        stats['artwork'] = coverage
        return stats

    if not with_toc:
        stats = _run_chain(source, output, [], None, report, artwork=artwork)
        stats['toc_pages'] = 0
        return finish(stats)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        toc1 = []
        _run_chain(source, tmp / 'pass1.pdf', toc1, None, None)
        toc_pdf = tmp / 'toc.pdf'
        offset = 0
        for _ in range(6):
            toc_render.render_toc_pages(
                [[lvl, title, page + offset] for lvl, title, page in toc1],
                toc_pdf, title=toc_render.TOC_TITLE_RU,
            )
            pages = pymupdf.open(toc_pdf).page_count
            if pages == offset:
                break
            offset = pages
        else:
            raise RuntimeError('Количество страниц оглавления не сошлось')
        toc2 = []
        stats = _run_chain(source, output, toc2, toc_pdf, report, artwork=artwork)
        expected = [[lvl, title, page + offset] for lvl, title, page in toc1]
        if toc2 != expected:
            raise RuntimeError('Несовпадение нумерации страниц между проходами сборки')
        stats['toc_pages'] = offset
        return finish(stats)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    p.add_argument('--no-toc', action='store_true', help='без печатного оглавления')
    p.add_argument('--artwork-manifest', type=Path,
                   help='artwork-manifest.json, созданный из этого же Publisher PDF')
    p.add_argument('--artwork-root', type=Path,
                   help='каталог экспортированных PNG (по умолчанию рядом с manifest)')
    p.add_argument('--artwork-coverage', type=Path,
                   help='куда записать проверяемый JSON coverage artwork')
    p.add_argument('--rasterize-cover', action='store_true',
                   help='после сборки заменить только обложку одним непрозрачным RGB JPEG')
    p.add_argument('--cover-dpi', type=int, default=rasterize_pdf.DEFAULT_COVER_DPI,
                   help=f'DPI JPEG-обложки (по умолчанию {rasterize_pdf.DEFAULT_COVER_DPI})')
    p.add_argument('--cover-jpeg-quality', type=int,
                   default=rasterize_pdf.DEFAULT_COVER_JPEG_QUALITY,
                   help=('качество JPEG-обложки от 1 до 100 '
                         f'(по умолчанию {rasterize_pdf.DEFAULT_COVER_JPEG_QUALITY})'))
    args = p.parse_args()
    print(build(args.source, args.out, args.report, with_toc=not args.no_toc,
                artwork_manifest=args.artwork_manifest, artwork_root=args.artwork_root,
                artwork_coverage=args.artwork_coverage,
                rasterize_cover=args.rasterize_cover, cover_dpi=args.cover_dpi,
                cover_jpeg_quality=args.cover_jpeg_quality))

if __name__ == '__main__':
    main()
