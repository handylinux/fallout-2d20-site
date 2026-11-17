#!/usr/bin/env python3
"""Render an editable-text preview of a weapon mod reference table from JSON."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle

import weapon2pdf as w

HEADERS = ("МОДИФИКАЦИЯ", "ПРЕФИКС", "ЭФФЕКТЫ", "ВЕС", "ЦЕНА", "ПЕРКИ")
# Geometry measured from the original table, within the standard content area,
# with sufficient room for both Russian and English column headings.
COL_WIDTHS = (92, 76, 194, 40, 34, w.CONTENT_W - 436)


def render(data, output, page_start=10, headers=None, col_widths=None):
    if not data.get("title") or not data.get("category"):
        raise ValueError("Нужны title и category")
    rows = data.get("rows")
    if not isinstance(rows, list) or any(not isinstance(row, list) or len(row) != 6
                                         or any(not isinstance(v, str) for v in row)
                                         for row in rows):
        raise ValueError("rows должен содержать строки из шести текстовых ячеек")
    if not rows or page_start < 1:
        raise ValueError("Нужны строки и положительный номер страницы")
    w.register_fonts()
    body_left = ParagraphStyle("body", fontName="Carlito", fontSize=10,
                               leading=13.0, alignment=TA_LEFT)
    body_center = ParagraphStyle("center", parent=body_left, alignment=TA_CENTER)
    white = ParagraphStyle("header", fontName="Carlito-Bold", fontSize=10,
                           leading=12, textColor=colors.white, alignment=TA_CENTER)
    def para(text, style):
        return Paragraph(escape(text).replace("\n", "<br/>"), style)

    table_headers = tuple(data.get("headers") or headers or HEADERS)
    table_widths = tuple(data.get("col_widths") or col_widths or COL_WIDTHS)
    cells = [[para(header, white) for header in table_headers],
             [para(data["category"], white), "", "", "", "", ""]]
    for row in rows:
        cells.append([para(value, body_center if col in (3, 4, 5) else body_left)
                      for col, value in enumerate(row)])
    table = Table(cells, colWidths=table_widths, repeatRows=2, hAlign="LEFT",
                  splitByRow=1, splitInRow=0)
    commands = [
        ("BACKGROUND", (0, 0), (-1, 1), colors.black),
        ("SPAN", (0, 1), (-1, 1)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, 1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, 1), 5),
        ("TOPPADDING", (0, 2), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 2), (-1, -1), 3),
        ("ROWBACKGROUNDS", (0, 2), (-1, -1), [w.BEIGE, w.ORANGE]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.Color(.65, .65, .65)),
    ]
    table.setStyle(TableStyle(commands))
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(output), pagesize=(w.PAGE_W, w.PAGE_H),
                            leftMargin=w.MARGIN_L, rightMargin=w.PAGE_W - w.CONTENT_R,
                            topMargin=100, bottomMargin=35,
                            allowSplitting=1, title=data["title"])
    def page(canvas, doc):
        canvas.saveState()
        w.draw_paper(canvas)
        title = data["title"]
        size = w.TITLE_SIZE
        while size > 12 and w.sw(title, "Carlito-Bold", size) > w.CONTENT_W:
            size -= .5
        w.draw_center_line(canvas, w.TITLE_TOP, title, "Carlito-Bold", size)
        canvas.setFillColor(colors.black)
        canvas.rect(w.PAGE_W_WORK_CENTER - w.RULE_W / 2,
                    w.y_from_top(w.RULE_TOP), w.RULE_W, -w.RULE_H, stroke=0, fill=1)
        w.draw_page_number(canvas, page_start + doc.page - 1)
        canvas.restoreState()
    # Table's frame padding must not shift the measured content column.
    doc.leftMargin -= 6
    doc.rightMargin -= 6
    doc.build([table], onFirstPage=page, onLaterPages=page)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--page-start", type=int, default=10)
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.data.read_text(encoding="utf-8"))
        render(data, args.out, args.page_start)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Ошибка: {exc}\n")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
