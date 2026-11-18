#!/usr/bin/env python3
"""Editable-text compatibility version of the weapon mod table (Type0 fonts)."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pymupdf
import weapon2pdf as w
from weapon_mods_table import HEADERS, COL_WIDTHS

REGULAR = str(Path(w.FONT_DIR) / 'Carlito-Regular.ttf')
BOLD = str(Path(w.FONT_DIR) / 'Carlito-Bold.ttf')
SIZE, LEADING = 10, 13
# A table must never make a word unreadable by breaking it character by
# character.  Long unbroken identifiers are instead set a little smaller; if
# even this minimum cannot fit, rendering fails loudly rather than creating an
# overflowing or hyphenated-looking cell.
MIN_SIZE = 6.0
TABLE_TOP, HEADER_H, CATEGORY_H, PAGE_BOTTOM = 100, 23, 23, 803
BEIGE, ORANGE = (1, .922, .804), (1, .776, .455)
BLACK, WHITE, BORDER = (0, 0, 0), (1, 1, 1), (.65, .65, .65)
DAMAGE_MARK = "\ue000"
DAMAGE_SIZE = 10.5
DAMAGE_GAP = 2.0  # breathing room before punctuation and following text


def inline_width(text, font, size=SIZE):
    parts = text.split(DAMAGE_MARK)
    return sum(font.text_length(part, fontsize=size) for part in parts) + (len(parts) - 1) * (DAMAGE_SIZE + DAMAGE_GAP)


def damage_tokens(text):
    """Treat standalone DC in effect cells as a damage icon, not as text."""
    return re.sub(r"(?<![\w])DC(?![\w])", DAMAGE_MARK, text)


def wrap(text, font, width, size=SIZE):
    """Wrap at spaces only; an individual word is never split into letters."""
    lines = []
    for paragraph in text.split('\n'):
        line = ''
        for word in paragraph.split():
            candidate = (line + ' ' + word).strip()
            if not line or inline_width(candidate, font, size) <= width:
                line = candidate
                continue
            lines.append(line)
            line = word
        lines.append(line)
    return lines or ['']


def fitted_size(value, font, width, default=SIZE, minimum=MIN_SIZE):
    """Find a readable size at which every unbroken word fits in its cell.

    We deliberately do not fall back to splitting words.  A value that cannot
    fit even at the documented minimum is a layout error the caller must fix.
    """
    words = [word for paragraph in value.split('\n') for word in paragraph.split()]
    if not words:
        return default
    size = float(default)
    while size >= minimum:
        if all(inline_width(word, font, size) <= width for word in words):
            return size
        size -= .25
    widest = max(words, key=lambda word: inline_width(word, font, minimum))
    raise ValueError(f'Слово не помещается в ячейку без разбиения: {widest}')


def render(data, output, page_start=10):
    sections = data.get('sections')
    if sections is None:
        sections = [{'category': data.get('category'), 'rows': data.get('rows')}]
    if not data.get('title') or not isinstance(sections, list) or not sections:
        raise ValueError('Нужны title и разделы таблицы')
    for section in sections:
        if not isinstance(section, dict) or not section.get('category'):
            raise ValueError('Нужно название категории')
        rows = section.get('rows')
        if not isinstance(rows, list) or not rows or any(
            not isinstance(row, list) or len(row) != 6 or
            any(not isinstance(v, str) for v in row) for row in rows
        ) or page_start < 1:
            raise ValueError('Нужны строки из шести текстовых ячеек и положительный номер страницы')
    regular = pymupdf.Font(fontfile=REGULAR)
    bold = pymupdf.Font(fontfile=BOLD)
    doc = pymupdf.open()
    page, y = None, 0
    icon_xref = 0

    table_headers = tuple(data.get('headers') or HEADERS)
    table_widths = tuple(data.get('col_widths') or COL_WIDTHS)

    def text(page, x, baseline, value, name='body', size=SIZE, color=BLACK):
        page.insert_text((x, baseline), value, fontname=name, fontsize=size, color=color)

    def inline_text(page, x, baseline, line, size=SIZE):
        nonlocal icon_xref
        parts = line.split(DAMAGE_MARK)
        icon_size = DAMAGE_SIZE * (size / SIZE)
        gap = DAMAGE_GAP * (size / SIZE)
        for i, part in enumerate(parts):
            if part:
                text(page, x, baseline, part, size=size)
                x += regular.text_length(part, fontsize=size)
            if i < len(parts) - 1:
                if not Path(w.DAMAGE_ICON).is_file():
                    raise ValueError(f'Не найдена иконка урона: {w.DAMAGE_ICON}')
                rect = pymupdf.Rect(x, baseline - icon_size * .85,
                                    x + icon_size, baseline + icon_size * .15)
                icon_xref = page.insert_image(rect, filename=w.DAMAGE_ICON if not icon_xref else None,
                                              xref=icon_xref, keep_proportion=True)
                x += icon_size + gap

    def centered(page, rect, lines, font, name, size, leading, color=BLACK):
        block = (len(lines) - 1) * leading + size
        baseline = rect.y0 + (rect.height - block) / 2 + size * .85
        for line in lines:
            x = rect.x0 + (rect.width - font.text_length(line, fontsize=size)) / 2
            text(page, x, baseline, line, name, size, color)
            baseline += leading

    def new_page(category_name):
        page = doc.new_page(width=w.PAGE_W, height=w.PAGE_H)
        page.insert_font(fontname='body', fontfile=REGULAR)
        page.insert_font(fontname='bold', fontfile=BOLD)
        x, by, width, height = w.paper_placement()
        if Path(w.PAPER).is_file():
            page.insert_image(pymupdf.Rect(x, w.PAGE_H - (by + height), x + width, w.PAGE_H - by),
                              filename=w.PAPER, keep_proportion=False)
        size = w.TITLE_SIZE
        while size > 12 and bold.text_length(data['title'], fontsize=size) > w.CONTENT_W:
            size -= .5
        title_width = bold.text_length(data['title'], fontsize=size)
        title_x = (w.PAGE_W - title_width) / 2
        title_baseline = w.TITLE_TOP + w.TITLE_SIZE * .85
        text(page, title_x, title_baseline, data['title'], 'bold', size, BLACK)
        page.draw_rect(pymupdf.Rect(w.PAGE_W_WORK_CENTER - w.RULE_W / 2, w.RULE_TOP,
                                   w.PAGE_W_WORK_CENTER + w.RULE_W / 2, w.RULE_TOP + w.RULE_H),
                       color=None, fill=BLACK)
        page_no = str(page_start + len(doc) - 1)
        x_num = w.MARGIN_L + 2.57 if (page_start + len(doc) - 1) % 2 == 0 else w.CONTENT_R - 2.57 - regular.text_length(page_no, fontsize=9.96)
        text(page, x_num, w.PAGE_NUMBER_TOP + 9.96 * .75, page_no, size=9.96)
        x = w.MARGIN_L
        for width, name in zip(table_widths, table_headers):
            rect = pymupdf.Rect(x, TABLE_TOP, x + width, TABLE_TOP + HEADER_H)
            page.draw_rect(rect, color=BORDER, fill=BLACK, width=.25)
            centered(page, rect, wrap(name, bold, width - 6, 9), bold, 'bold', 9, 11, WHITE)
            x += width
        return page, draw_category(page, TABLE_TOP + HEADER_H, category_name)

    def draw_category(page, top, category_name):
        category = pymupdf.Rect(w.MARGIN_L, top, w.CONTENT_R, top + CATEGORY_H)
        category_lines = wrap(category_name, bold, w.CONTENT_W - 6, 10)
        if len(category_lines) > 1:
            raise ValueError(f'Слишком длинное название категории: {category_name}')
        page.draw_rect(category, color=BORDER, fill=BLACK, width=.25)
        centered(page, category, category_lines, bold, 'bold', 10, 12, WHITE)
        return category.y1

    for section in sections:
        category_name = section['category']
        for index, row in enumerate(section['rows']):
            values = [damage_tokens(value) if col == 2 else value
                      for col, value in enumerate(row)]
            sizes = [fitted_size(value, regular, width - 6)
                     for value, width in zip(values, table_widths)]
            lines = [wrap(value, regular, width - 6, size)
                     for value, width, size in zip(values, table_widths, sizes)]
            height = max(len(cell) for cell in lines) * LEADING + 6
            if height > PAGE_BOTTOM - (TABLE_TOP + HEADER_H + CATEGORY_H):
                doc.close()
                raise ValueError(f'Строка {index + 1} не помещается на страницу целиком')
            gap = section.get('gap_before', 0) if index == 0 and page is not None else 0
            if not isinstance(gap, (int, float)) or gap < 0:
                raise ValueError('Некорректный отступ между таблицами')
            if page is None or (index == 0 and section.get('page_break_before')) or y + gap + height + (CATEGORY_H if index == 0 else 0) > PAGE_BOTTOM:
                page, y = new_page(category_name)
            elif index == 0:
                y = draw_category(page, y + gap, category_name)
            x = w.MARGIN_L
            for col, (width, cell, size) in enumerate(zip(table_widths, lines, sizes)):
                rect = pymupdf.Rect(x, y, x + width, y + height)
                page.draw_rect(rect, color=BORDER, fill=BEIGE if index % 2 == 0 else ORANGE, width=.25)
                if col >= 3:
                    centered(page, rect, cell, regular, 'body', size, LEADING)
                else:
                    baseline = y + (height - ((len(cell) - 1) * LEADING + size)) / 2 + size * .85
                    for line in cell:
                        inline_text(page, x + 3, baseline, line, size=size)
                        baseline += LEADING
                x += width
            y += height
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        doc.save(str(output), garbage=4, deflate=True)
    finally:
        doc.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--page-start', type=int, default=10)
    args = parser.parse_args(argv)
    try:
        render(json.loads(args.data.read_text(encoding='utf-8')), args.out, args.page_start)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f'Ошибка: {exc}\n')
    print(args.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
