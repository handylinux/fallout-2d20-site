#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
armor_catalog_pdf — каталог брони, силовой брони и одежды в PDF.

Конвейер — сначала HTML, потом PDF:
  данные (armor.json / powerArmor.json)  →  печатный HTML (каталог)  →
  xhtml2pdf  →  PDF

Состав документа (всё из данных companion):
  1. Броня       — все сеты armor.json (рейдерская, кожаная, металлическая,
                   боевая, броня синтов, броня охранника Волт-Тек).
  2. Силовая броня — все сеты powerArmor.json (каркас, рейдерская, Т-45,
                   Т-51, Т-60, X-01).
  3. Одежда       — данные из clothes.json + i18n (костюмы, обмундирование,
                   головные уборы). Изображений и описаний в данных нет →
                   карточки с зарезервированным местом (плейсхолдерами)
                   под изображение и описание.

Карточка предмета:
  - место под изображение — зарезервировано, если картинки в data нет;
  - название предмета — текст из i18n (редактируемый в PDF);
  - характеристики — ФИЗ./ЭНРГ./РАД. СУ, ВЕС, ЦЕНА, РЕДКОСТЬ (+ ПРОЧНОСТЬ
    для силовой брони) — редактируемый векторный текст;
  - место под описание — зарезервировано, если описания в data нет.

Текст рендерится как векторный шрифт (xhtml2pdf) — редактируется в
PDF-редакторе (не растр).

Пример:
    python3 tools/armor_catalog_pdf.py \\
        --data data/companion \\
        --out docs/render/samples/armor-catalog.pdf
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

from xhtml2pdf import pisa

sys.path.insert(0, str(Path(__file__).resolve().parent))
import weapon2pdf as w  # noqa: E402
from armor2page import (  # noqa: E402
    AREA_TITLES,
    Companion,
    fmt_number,
    stat_fields,
)
from armor_book_pdf import esc, scale_to, text_w  # noqa: E402

# --- геометрия (pt, A4 595.276×841.89) ------------------------------------
# Отступы симметричные (как в справочнике брони после корректировок).
MARGIN_L = 48.0
CONTENT_R = 595.276 - MARGIN_L
CONTENT_W = CONTENT_R - MARGIN_L

PAGE_PAD_T = 59.8
PAGE_PAD_B = 59.8
PAGE_PAD_LR = 48.0

TITLE_SIZE = 22.0
SECTION_SIZE = 18.0
SET_SIZE = 14.0

CARD_GAP = 12.0          # между карточками в сетке
CARD_IMG_W = 116.0       # ширина зарезервированного места под изображение
CARD_IMG_H = 124.0       # высота зарезервированного места под изображение
CARD_DESC_H = 42.0       # высота зарезервированного места под описание

PLACEHOLDER_COLOR = "#cfcfcf"   # цвет плейсхолдера
GRID_BORDER = "#000"

BEIGE = "#FFEBCD"
LIGHT = "#f4f1ea"


# --- помощь ----------------------------------------------------------------
def _placeholder(label: str, w: float, h: float) -> str:
    """Зарезервированное место (плейсхолдер) под изображение/описание."""
    return (
        f'<div style="width:{w:.1f}pt;height:{h:.1f}pt;'
        f'border:0.6pt dashed {GRID_BORDER};'
        f'background:{PLACEHOLDER_COLOR};'
        f'display:flex;align-items:center;justify-content:center;'
        f'color:#333;font-size:9pt;font-family:Carlito">{esc(label)}</div>'
    )


def _stat_rows(piece: dict) -> str:
    """Строки характеристик (редактируемый текст)."""
    out = []
    for label, key in stat_fields(piece):
        val = fmt_number(piece.get(key, 0))
        out.append(
            f'<tr><th style="text-align:left;padding-left:3pt">'
            f'{esc(label)}</th>'
            f'<td style="text-align:center">{esc(val)}</td></tr>'
        )
    return "".join(out)


def _card_html(name: str, piece: dict) -> str:
    """Карточка одного предмета."""
    img = _placeholder("ИЗОБРАЖЕНИЕ", CARD_IMG_W, CARD_IMG_H)
    desc = _placeholder("ОПИСАНИЕ", CARD_IMG_W, CARD_DESC_H)
    return (
        f'<td class="card">'
        f'<div class="card-title">{esc(name)}</div>'
        f'<table class="card-body"><tr>'
        f'<td class="card-img" style="width:{CARD_IMG_W + 8:.1f}pt;'
        f'vertical-align:top">{img}</td>'
        f'<td class="card-text" style="vertical-align:top">'
        f'<table class="stat">{_stat_rows(piece)}</table>'
        f'</td></tr></table>'
        f'<div class="card-desc">{desc}</div>'
        f'</td>'
    )


def _empty_card_html(label: str) -> str:
    """Пустая зарезервированная карточка (одежда без данных)."""
    img = _placeholder("ИЗОБРАЖЕНИЕ", CARD_IMG_W, CARD_IMG_H)
    desc = _placeholder("ОПИСАНИЕ", CARD_IMG_W, CARD_DESC_H)
    return (
        f'<td class="card">'
        f'<div class="card-title">{esc(label)}</div>'
        f'<table class="card-body"><tr>'
        f'<td class="card-img" style="width:{CARD_IMG_W + 8:.1f}pt;'
        f'vertical-align:top">{img}</td>'
        f'<td class="card-text" style="vertical-align:top">'
        f'<table class="stat">'
        f'<tr><th style="text-align:left;padding-left:3pt">ФИЗ. СУ</th>'
        f'<td style="text-align:center">—</td></tr>'
        f'<tr><th style="text-align:left;padding-left:3pt">ЭНРГ. СУ</th>'
        f'<td style="text-align:center">—</td></tr>'
        f'<tr><th style="text-align:left;padding-left:3pt">РАД. СУ</th>'
        f'<td style="text-align:center">—</td></tr>'
        f'<tr><th style="text-align:left;padding-left:3pt">ВЕС</th>'
        f'<td style="text-align:center">—</td></tr>'
        f'<tr><th style="text-align:left;padding-left:3pt">ЦЕНА</th>'
        f'<td style="text-align:center">—</td></tr>'
        f'<tr><th style="text-align:left;padding-left:3pt">РЕДКОСТЬ</th>'
        f'<td style="text-align:center">—</td></tr>'
        f'</table></td></tr></table>'
        f'<div class="card-desc">{desc}'
        f'</div>'
        f'</td>'
    )


def _set_block_html(set_key: str, set_name: str, collection: str,
                    comp: Companion, page_break: bool) -> str:
    """Блок одного сета: заголовок + сетка карточек деталей."""
    pieces = comp.set_pieces(collection, set_key)
    cards = []
    for p in pieces:
        cards.append(_card_html(comp.item_name(p), p))
    if not cards:
        cards.append(_empty_card_html(set_name))
    # сетка: по две карточки в строку
    rows = []
    for i in range(0, len(cards), 2):
        pair = cards[i]
        if i + 1 < len(cards):
            pair += cards[i + 1]
        rows.append(f"<tr>{pair}</tr>")
    grid = (
        '<table class="grid">'
        + "".join(rows)
        + '</table>'
    )
    pb = "page-break-before:always;" if page_break else ""
    return (
        f'<div style="{pb}">'
        f'<div class="set-title">{esc(set_name)}</div>'
        f'{grid}'
        f'</div>'
    )


# --- CSS --------------------------------------------------------------------
def build_css() -> str:
    regular = w.FONT_DIR + "/Carlito-Regular.ttf"
    bold = w.FONT_DIR + "/Carlito-Bold.ttf"
    card_w = (CONTENT_W - CARD_GAP) / 2
    return f"""
@font-face{{
  font-family:'Carlito';
  src:url('file://{regular}') format('truetype');
}}
@font-face{{
  font-family:'CarlitoBold';
  src:url('file://{bold}') format('truetype');
}}
.sheet{{ border-collapse:collapse; width:100%; }}
body{{ font-family:'Carlito'; font-size:10pt; margin:0; color:#000; }}
.card{{ border:0.6pt solid {GRID_BORDER}; padding:6pt 7pt;
       width:{card_w:.1f}pt; vertical-align:top;
       page-break-inside:avoid; }}
.grid{{ border-collapse:separate; border-spacing:0; }}
.grid td{{ }}
.set-title{{ font-family:CarlitoBold; font-size:{SET_SIZE}pt;
            margin:14pt 0 8pt 0; }}
.card-title{{ font-family:CarlitoBold; font-size:11pt;
             margin-bottom:4pt; }}
.card-body{{ border-collapse:collapse; }}
.card-img{{ vertical-align:top; }}
.card-text{{ vertical-align:top; padding-left:8pt; }}
.stat{{ border-collapse:collapse; font-size:9.5pt;
       font-family:Carlito; }}
.stat th{{ background:#000; color:#fff; padding:2.4pt 4pt;
          border:0.5pt solid {GRID_BORDER}; }}
.stat td{{ background:{BEIGE}; text-align:center; padding:2.4pt 4pt;
          border:0.5pt solid {GRID_BORDER}; }}
.card-desc{{ margin-top:5pt; }}
.page-title{{ font-family:CarlitoBold; font-size:{TITLE_SIZE}pt;
              text-align:center; margin-top:{PAGE_PAD_T}pt; }}
.page-sub{{ font-family:Carlito; font-size:13pt;
           text-align:center; margin-top:6pt; }}
.section-title{{ font-family:CarlitoBold; font-size:{SECTION_SIZE}pt;
                margin-top:14pt; }}
.page-note{{ font-size:10pt; font-family:Carlito; margin-bottom:10pt; }}
"""


# --- сборка документа --------------------------------------------------------
def build_catalog_html(comp: Companion) -> str:
    body = []

    # --- титул ---
    body.append(
        f'<div class="page-title">СПРАВОЧНИК БРОНИ</div>'
        f'<div class="page-sub">Броня · Силовая броня · Одежда</div>'
        f'<div style="margin-top:18pt;width:386pt;height:2.2pt;'
        f'background:#000"></div>'
    )

    # --- 1. Броня ---
    body.append('<div class="section-title">БРОНЯ</div>')
    for k in comp.armor:
        body.append(
            _set_block_html(k, comp.set_names.get(k, k), "armor", comp,
                            page_break=False)
        )

    # --- 2. Силовая броня ---
    body.append(
        '<div style="page-break-before:always"></div>'
        '<div class="section-title">СИЛОВАЯ БРОНЯ</div>'
    )
    for k in comp.power_armor:
        body.append(
            _set_block_html(k, comp.set_names.get(k, k), "powerArmor", comp,
                            page_break=False)
        )

    # --- 3. Одежда (данные из clothes.json + i18n) ---
    body.append(
        '<div style="page-break-before:always"></div>'
        '<div class="section-title">ОДЕЖДА</div>'
    )
    clothing_groups = comp.clothing_groups()
    if clothing_groups:
        for ct, cname in clothing_groups:
            body.append(
                _set_block_html(ct, cname, "clothing", comp,
                                page_break=False)
            )
    else:
        body.append(
            '<div class="page-note">'
            'Данные об одежде отсутствуют — карточка зарезервирована под '
            'изображение, характеристики и описание.'
            '</div>'
        )
        empty_rows = []
        for i in range(6):
            empty_rows.append(_empty_card_html(f"Одежда {i + 1}"))
        rows = []
        for i in range(0, len(empty_rows), 2):
            pair = empty_rows[i]
            if i + 1 < len(empty_rows):
                pair += empty_rows[i + 1]
            rows.append(f"<tr>{pair}</tr>")
        body.append('<table class="grid">' + "".join(rows) + '</table>')

    css = build_css()
    return (
        '<html><head><style>'
        + css
        + '</style></head><body>'
        + "".join(body)
        + '</body></html>'
    )


def render(out_path: str, repo: Path) -> None:
    data_dir = repo / "data" / "companion"
    comp = Companion(data_dir)
    doc = build_catalog_html(comp)
    out = io.open(out_path, "wb")
    try:
        result = pisa.CreatePDF(doc, dest=out)
    finally:
        out.close()
    if result.err:
        raise RuntimeError(f"xhtml2pdf вернул ошибки: {result.err}")


# --- CLI --------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Каталог брони, силовой брони и одежды в PDF")
    parser.add_argument("--data", default="data/companion",
                        help="каталог с equipment/ и i18n/")
    parser.add_argument("--out", required=True, help="выходной PDF")
    args = parser.parse_args(argv)

    data_dir = Path(args.data)
    if not data_dir.exists():
        parser.error(f"нет каталога с данными: {data_dir}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    w.register_fonts()
    render(str(out), Path.cwd().resolve())
    print(f"{out}  (каталог брони, силовой брони и одежды)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
