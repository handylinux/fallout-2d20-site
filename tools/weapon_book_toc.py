#!/usr/bin/env python3
"""Shared printed table-of-contents and padding-page rendering for weapon books.

Two dotted columns per page, section headers bold, every entry mapped to its
final page number.  Used by both the English and Russian catalog builders.
"""
from __future__ import annotations

from pathlib import Path

from reportlab.pdfgen import canvas

import weapon2pdf as w

TOC_TITLE_EN = 'TABLE OF CONTENTS'
TOC_TITLE_RU = 'ОГОЛОВЛЕНИЕ'
TOC_GUTTER = 22.0
TOC_L1_SIZE = 10.5
TOC_L2_SIZE = 9.2
TOC_L1_LEADING = 15.5
TOC_L2_LEADING = 11.8
TOC_L1_GAP = 7.0
TOC_INDENT = 11.0
TOC_TOP = 104.0
TOC_BOTTOM = 772.0
TOC_NUM_RIGHT_PAD = 3.0
TOC_LEAD_STEP = 3.2
TOC_LEAD_COLOR = (0.36, 0.36, 0.36)


def make_blank_page(page_num: int, out_path: Path):
    """Render a plain paper-background page used to pad the book to a multiple of 4."""
    c = canvas.Canvas(str(out_path), pagesize=(w.PAGE_W, w.PAGE_H))
    w.draw_paper(c)
    w.draw_page_number(c, page_num)
    c.showPage()
    c.save()


def _toc_entry_font(level: int, title: str) -> str:
    if level == 1 or title.endswith('Modifications') or title.endswith('МОДИФИКАЦИИ'):
        return 'Carlito-Bold'
    return 'Carlito'


def _toc_entry_size(level: int) -> float:
    return TOC_L1_SIZE if level == 1 else TOC_L2_SIZE


def _toc_entry_leading(level: int) -> float:
    return TOC_L1_LEADING if level == 1 else TOC_L2_LEADING


def render_toc_pages(entries: list[list], out_path: Path,
                     title: str = TOC_TITLE_EN) -> int:
    """Render the printed table of contents to out_path.

    entries: [[level, title, page], ...] with final page numbers.  Two dotted
    columns per page, section headers bold, weapons listed under their section.
    Returns the number of pages rendered.
    """
    w.register_fonts()
    c = canvas.Canvas(str(out_path), pagesize=(w.PAGE_W, w.PAGE_H))
    col_w = (w.CONTENT_R - w.MARGIN_L - TOC_GUTTER) / 2.0
    col_x = (w.MARGIN_L, w.MARGIN_L + TOC_GUTTER + col_w)
    pages = 0

    def start_page():
        nonlocal pages
        if pages:
            c.showPage()
        pages += 1
        w.draw_paper(c)
        w.draw_center_line(c, w.TITLE_TOP, title, 'Carlito-Bold', w.TITLE_SIZE)
        c.setFillColor(w.BLACK)
        c.rect(
            w.PAGE_W_WORK_CENTER - w.RULE_W / 2.0,
            w.y_from_top(w.RULE_TOP + w.RULE_H),
            w.RULE_W, -w.RULE_H,
            stroke=0, fill=1,
        )

    start_page()
    col = 0
    y_top = TOC_TOP
    for level, entry_title, page in entries:
        leading = _toc_entry_leading(level)
        gap = TOC_L1_GAP if level == 1 else 0.0
        if y_top + gap + leading > TOC_BOTTOM:
            col += 1
            if col > 1:
                start_page()
                col = 0
            y_top = TOC_TOP
            gap = 0.0
        y_top += gap
        font = _toc_entry_font(level, entry_title)
        size = _toc_entry_size(level)
        while level != 1 and w.sw(entry_title, font, size) > col_w - TOC_INDENT - 46.0:
            size -= 0.5
        text_x = col_x[col] + (0.0 if level == 1 else TOC_INDENT)
        num_text = str(page)
        num_x = col_x[col] + col_w - TOC_NUM_RIGHT_PAD - w.sw(num_text, font, size)
        baseline_top = y_top + w.ASCENT * size
        c.setFillColor(w.BLACK)
        c.setFont(font, size)
        c.drawString(text_x, w.y_from_top(baseline_top), entry_title)
        c.drawString(num_x, w.y_from_top(baseline_top), num_text)
        leader_start = text_x + w.sw(entry_title, font, size) + 4.0
        leader_end = num_x - 4.0
        if leader_end > leader_start:
            c.setFillColorRGB(*TOC_LEAD_COLOR)
            c.setFont('Carlito', size)
            x = leader_start
            while x < leader_end:
                c.drawString(x, w.y_from_top(baseline_top), '.')
                x += TOC_LEAD_STEP
        y_top += leading
    c.save()
    return pages


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('entries', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--title', default=TOC_TITLE_EN)
    args = parser.parse_args(argv)
    import json

    entries = json.loads(args.entries.read_text(encoding='utf-8'))
    print(render_toc_pages(entries, args.out, title=args.title))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
