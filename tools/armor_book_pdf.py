#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
armor_book_pdf — страница брони в PDF по референсной вёрстке пользователя.

Конвейер — сначала HTML, потом PDF:
  данные брони  →  печатный HTML (референсная вёрстка)  →  xhtml2pdf  →  PDF

Схема — по референсу «сПРАВОЧНИК БРОНИ.pdf» (2 страницы A4):
  страница 1 — заголовок «КОЖАНАЯ БРОНЯ» + черта; справа блок
    «СТАНДАРТНЫЙ КОМПЛЕКТ»: подпись детали над таблицей, таблица
    строк ФИЗ.СУ/ЭНРГ.СУ/РАД.СУ/ВЕС/ЦЕНА/РЕДКОСТЬ (метки — белый на
    чёрном, значения — кремовый); под ним описание; «ПОДДЕРЖИВАЕМЫЕ
    МОДИФИКАЦИИ» + сетка модов (метка зоны — белый на чёрном, названия
    модов — чередующиеся кремовый/оранжевый, длинные названия переносятся);
  страница 2 — заголовок «ВАРИАНТЫ» + черта; две матрицы тиров
    (УКРЕПЛЁННАЯ, ТЯЖЁЛАЯ) рядом: шапка — названия деталей (белый на
    чёрном), строки — статысты (метки — белый на чёрном, значения —
    кремовый); «УНИКАЛЬНЫЕ МОДИФИКАЦИИ КОЖАНОЙ БРОНИ» + таблица
    уникальных модов.

Ячейки sized по ширине контента (не произвольные константы): ширина
меточной колонки — по самой длинной метке, ширина колонок значений —
по содержимому; сетки масштабируются по необходимости до ширины
страницы. Если в данных нет шлема — шлем не рисуется и ему не создаются
элементы/строки.

Пример:
    python3 tools/armor_book_pdf.py \\
        --data data/companion \\
        --pages data/armor-pages \\
        --out docs/render/samples/armor-leather-book.pdf
"""

from __future__ import annotations

import argparse
import html
import io
import json
import math
import shutil
import sys
from pathlib import Path

from xhtml2pdf import pisa

sys.path.insert(0, str(Path(__file__).resolve().parent))
import weapon2pdf as w  # noqa: E402
from armor2page import (  # noqa: E402
    AREA_TITLES,
    Companion,
    fmt_delta,
    fmt_number,
    stat_fields,
)

# --- геометрия (по референсу, pt) ----------------------------------------
# Отступы для переплёта (слева) и обрезки (сверху/справа): контент не
# прилипает к левому краю и верху листа.
BINDING_MARGIN_L = 12.0
TRIM_MARGIN_TOP = 12.0
# отступы слева = отступы справа (A4 width 595.276pt)
MARGIN_L = 36.0 + BINDING_MARGIN_L
CONTENT_R = 595.276 - MARGIN_L
CONTENT_W = CONTENT_R - MARGIN_L

# заголовки страниц (позиции по референсу)
TITLE_TOP = 47.8
TITLE_SIZE = 22.0
TITLE_RULE_W = 385.94
TITLE_RULE_H = 2.2
TITLE_RULE_MARGIN = 6.8
TITLE_MARGIN_L = 46.1     # реф.: заголовок x236.3 (сдвиг от центрирования)
TITLE_RULE_MARGIN_L = 80.9  # реф.: черта x117.1
HEADING_MARGIN_L = 9.1    # реф.: ПОДДЕРЖИВАЕМЫЕ МОДИФИКАЦИИ x152.8
BIG_HEADING_MARGIN_L = 0.0  # заголовок центрирован (как в референсе)

# подписи секций (СТАНДАРТНЫЙ КОМПЛЕКТ, УКРЕПЛЁННАЯ, ТЯЖЁЛАЯ) — 10pt
SECTION_SIZE = 10.0
SECTION_RULE_H = 0.6
SECTION_RULE_PAD = 16.5
SECTION_RULE_MIN = 124.7

# заголовки секций (ПОДДЕРЖИВАЕМЫЕ МОДИФИКАЦИИ, УНИКАЛЬНЫЕ МОДИФИКАЦИИ)
HEADING_SIZE = 18.0
BIG_HEADING_SIZE = 22.0

# характерист. таблицы (страница 1, справа)
CHAR_LABEL_SIZE = 11.0
CHAR_ROW_H = 23.3
# ширины колонок по векторным линиям референса (get_drawings):
#   левая таблица  x315.8→395.4 (79.6) | x395.4→435.0 (39.6)
#   правая таблица x449.3→524.3 (75.0) | x524.3→559.3 (35.0)
CHAR_LEFT_LABEL_W = 79.6
CHAR_LEFT_VALUE_W = 39.6
CHAR_RIGHT_LABEL_W = 75.0
CHAR_RIGHT_VALUE_W = 35.0
CHAR_LEFT_W = CHAR_LEFT_LABEL_W + CHAR_LEFT_VALUE_W   # 119.2 (x315.8..435.0)
CHAR_RIGHT_W = CHAR_RIGHT_LABEL_W + CHAR_RIGHT_VALUE_W  # 110.0 (x449.3..559.3)
CHAR_COL_GAP = 14.3
CHAR_BLOCK_W = CHAR_LEFT_W + CHAR_COL_GAP + CHAR_RIGHT_W  # 243.5
CHAR_ROW_GAP = 6.3         # между рядами таблиц характерист.
CHAR_PIECE_LABEL_GAP = 2.2 # подпись детали → таблица
CHAR_GRID_MARGIN_TOP = 19.6  # от правила СТАНДАРТНЫЙ КОМПЛЕКТ до подписи

# подписи деталей над таблицами характерист.
PIECE_LABEL_SIZE_TOP = 12.0    # ШЛЕМ / НАГРУДНИК (верхний ряд)
PIECE_LABEL_SIZE_BOT = 14.0    # НАРУЧ / ПОНОЖ (нижний ряд)

# описание
DESC_SIZE = 12.0
DESC_LEADING = 17.4

# сетка модов (нижняя часть страницы 1)
MODS_FONT = 10.0
MODS_LINE_H = 12.1
MODS_ROW_PAD = 6.7
MODS_ROW_MIN_H = 30.7
MODS_LABEL_PAD = 19.1
# высоты строк по векторным линиям референса (get_drawings):
#   ШЛЕМ 20.7 (исключен по правилу), НАГРУДНИК 43.1, НАРУЧ 30.7,
#   ПОНОЖ 30.9, УНИКАЛЬНАЯ 30.9
MODS_ROW_H_BY_AREA = {
    "НАГРУДНИК": 43.1,
    "НАРУЧ": 30.7,
    "ПОНОЖ": 30.9,
    "УНИКАЛЬНАЯ": 30.9,
}
# ширины колонок таблицы модификаций по векторным линиям референса
MODS_GRID_LABEL_W = 81.2
MODS_GRID_COLS = (80.7, 69.2, 90.3, 104.6, 97.2)
MODS_COL_PAD = 10.0
MODS_AREA_ORDER = ("Body", "Hand", "Leg")

# матрицы тиров (страница 2)
TIER_HEADER_H = 20.5
TIER_ROW_H = 18.7
TIER_FONT = 10.0
TIER_LABEL_PAD = 6.0
TIER_ELEM_PAD = 6.0
TIER_COL_GAP = 14.0
TIER_LABEL_CENTERS = (146.85 + BINDING_MARGIN_L, 449.65 + BINDING_MARGIN_L)
# ширины колонок матриц тиров по векторным линиям референса (ШЛЕМ опущен
# по правилу отсутствия шлема в данных).
TIER_LEFT_COLS = (54.2, 71.7, 42.5, 43.4)
TIER_RIGHT_COLS = (56.2, 59.5, 40.7, 45.7)
TIER_LABEL_PAD_L = 2.8  # центры подписей тиров (реф.)

# уникальные моды (страница 2)
UNIQ_FONT = 10.0
UNIQ_HEADER_H = 22.3
UNIQ_ROW_MIN_H = 18.5
UNIQ_LINE_H = 12.1
UNIQ_PAD = 10.0
UNIQ_NAME_PAD = 18.8
# ширины колонок таблицы уникальных модов по векторным линиям референса
UNIQ_COLS = (112.0, 55.3, 52.8, 50.7, 31.7, 33.5, 66.4, 120.1)
# названия, которые в референсе обрываются на 2 строки
UNIQ_WRAP_NAMES = {"РАСШИТАЯ КОЖА", "ДУБЛЁНАЯ КОЖА", "ЗАТЕНЁННАЯ КОЖА"}

# цвета (по референсу)
BEIGE = "#FFEBCD"
ORANGE = "#FFC674"
BLACK = "#000000"
WHITE = "#FFFFFF"


# --- текстовая шкала (ширины ячеек по контенту) ---------------------------
_MEASURE_READY = False


def _register_measure_fonts() -> None:
    global _MEASURE_READY
    if _MEASURE_READY:
        return
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    pdfmetrics.registerFont(TTFont("CarlitoReg", w.FONT_DIR + "/Carlito-Regular.ttf"))
    pdfmetrics.registerFont(TTFont("CarlitoBold", w.FONT_DIR + "/Carlito-Bold.ttf"))
    _MEASURE_READY = True


def text_w(text: str, size: float = 10.0, bold: bool = False) -> float:
    """Ширина текста в pt (Carlito)."""
    _register_measure_fonts()
    from reportlab.pdfbase import pdfmetrics
    font = "CarlitoBold" if bold else "CarlitoReg"
    return pdfmetrics.stringWidth(text, font, size)


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def scale_to(widths: list[float], available: float) -> list[float]:
    """Масштабировать ширины колонок до available (сохраняя пропорции)."""
    total = sum(widths)
    if total <= 0:
        return widths
    factor = available / total
    return [x * factor for x in widths]


# --- данные ---------------------------------------------------------------
def base_pieces(set_data: dict, tier_key: str = "standard") -> list[dict]:
    return list((set_data.get("tiers") or {}).get(tier_key, {}).get("pieces", []))


def area_of(piece: dict) -> str:
    areas = piece.get("protectedAreas") or []
    return areas[0] if areas else ""


def pieces_by_area_order(pieces: list[dict]) -> list[dict]:
    """Отсортировать детали по порядку зон референса (Body, Hand, Leg)."""
    order = {a: i for i, a in enumerate(MODS_AREA_ORDER)}
    return sorted(pieces, key=lambda p: order.get(area_of(p), 99))


def area_mods(comp: Companion, area: str, allowed: list[str]) -> list[str]:
    names = []
    for mod in comp.mods:
        if mod.get("modCategory") not in allowed:
            continue
        if area in (mod.get("protectedAreas") or []):
            names.append(comp.mod_names.get(mod.get("id", ""), mod.get("id", "")))
    return names


def unique_mod_names(comp: Companion, allowed: list[str]) -> list[str]:
    names = []
    for mod in comp.unique_mods:
        if mod.get("modCategory") in allowed:
            names.append(comp.mod_names.get(mod.get("id", ""), mod.get("id", "")))
    return names


# Calibri шире Carlito по кирииллице ~6%; для решений об обрывке
# используем завышенную оценку ширины, чтобы обёртка совпадала с референсом.
W_FACTOR = 1.08


def _w(text: str, size: float) -> float:
    return text_w(text, size) * W_FACTOR


def wrap_lines(text: str, col_w: float, size: float = MODS_FONT) -> list[str]:
    """Разбить текст на строки шириной col_w: по словам, а если слово
    ширее колонки — по символам (как в референсе: Звукоизолиро / ванная)."""
    if not text:
        return [""]
    words = text.split(" ")
    lines: list[str] = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if _w(trial, size) <= col_w:
            cur = trial
            continue
        if cur:
            lines.append(cur)
            cur = word
        # слово шире колонки — обрывает по символам
        if _w(word, size) > col_w:
            piece = ""
            for ch in word:
                if _w(piece + ch, size) <= col_w:
                    piece += ch
                else:
                    lines.append(piece)
                    piece = ch
            cur = piece
    if cur:
        lines.append(cur)
    return lines or [""]


def cell_lines(text: str, col_w: float, size: float = MODS_FONT) -> int:
    """Примерное число строк текста в колонке ширины col_w."""
    return max(1, len(wrap_lines(text, col_w, size)))


# --- подготовка ресурсов (фон) ---------------------------------------------
def prepare_resources(repo: Path) -> dict:
    """Растянутая бумага до A4 (xhtml2pdf не знает background-size)."""
    from PIL import Image

    tmp_dir = repo / "docs" / "render" / ".tmp-pdf"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    paper = Image.open(repo / "assets" / "pdf" / "paper.jpg").convert("RGB")
    paper.resize((1191, 1684), Image.LANCZOS).save(
        tmp_dir / "paper_a4.jpg", quality=90)
    return {"paper": str(tmp_dir / "paper_a4.jpg")}


# --- CSS --------------------------------------------------------------------
def build_css(paper_url: str) -> str:
    regular = w.FONT_DIR + "/Carlito-Regular.ttf"
    bold = w.FONT_DIR + "/Carlito-Bold.ttf"
    return f"""
@font-face{{
  font-family:'CarlitoReg';
  src:url('file://{regular}') format('truetype');
}}
@font-face{{
  font-family:CarlitoBold;
  src:url('file://{bold}') format('truetype');
}}
@page{{
  size:A4;
  background-image:url('file://{paper_url}');
}}
body{{
  font-family:'CarlitoReg';
  font-size:10pt;
  margin:0;
  color:#000;
}}
.sheet{{
  border-collapse:collapse;
  width:100%;
  height:841pt;
}}
.card{{ border:0.6pt solid #000; }}
.mods{{ border:0.6pt solid #000; }}
"""


# --- блоки-заголовки --------------------------------------------------------
def build_title_html(title: str, margin_l: float = TITLE_MARGIN_L) -> str:
    title = esc(title.upper())
    return (
        f'<div style="margin-left:{margin_l}pt;text-align:center;'
        f'font-size:{TITLE_SIZE}pt;font-family:CarlitoBold;'
        f'line-height:{TITLE_SIZE}pt">{title}</div>'
        f'<div style="margin-left:{TITLE_RULE_MARGIN_L}pt;width:{TITLE_RULE_W}pt;'
        f'height:{TITLE_RULE_H}pt;background:#000;margin-top:{TITLE_RULE_MARGIN}pt">'
        f'</div>'
    )


def build_section_label_html(label: str) -> str:
    label = esc(label.upper())
    tw = text_w(label, SECTION_SIZE, bold=True)
    rule_w = max(tw + SECTION_RULE_PAD, SECTION_RULE_MIN)
    return (
        f'<div style="text-align:center;font-size:{SECTION_SIZE}pt;'
        f'font-family:CarlitoBold;line-height:{SECTION_SIZE + 2.0}pt">'
        f'{label}</div>'
        f'<div style="width:{rule_w:.1f}pt;height:{SECTION_RULE_H}pt;'
        f'background:#000;margin:2.8pt auto 0 auto"></div>'
    )


def build_heading_html(text: str, size: float, margin_l: float = 0.0,
                       raw: bool = False) -> str:
    body = text if raw else esc(text.upper())
    return (
        f'<div style="margin-left:{margin_l}pt;text-align:center;'
        f'font-size:{size}pt;'
        f'font-family:CarlitoBold;line-height:{size}pt">'
        f'{body}</div>'
    )


# --- характерист. таблицы (страница 1, справа) ----------------------------
def stat_labels(piece: dict) -> list[str]:
    return [label for label, _key in stat_fields(piece)]


def build_char_tables_grid(pieces: list[dict]) -> str:
    """Сетка 2×2 характерист. таблиц по позициям референса:
    верхний ряд — ШЛЕМ (лев.) / НАГРУДНИК (прав.), нижний — НАРУЧ (лев.) /
    ПОНОЖ (прав.). Без шлема — пустая ячейка на его месте."""
    pieces = pieces_by_area_order(pieces)
    if not pieces:
        return ""

    col_w = (CHAR_BLOCK_W - CHAR_COL_GAP) / 2.0

    # позиции зон в сетке референса (строка, столбец)
    pos_map = {"Body": (0, 1), "Hand": (1, 0), "Leg": (1, 1)}
    grid: dict[tuple[int, int], dict | None] = {
        (0, 0): None, (0, 1): None, (1, 0): None, (1, 1): None,
    }
    for p in pieces:
        slot = pos_map.get(area_of(p))
        if slot:
            grid[slot] = p

    def block(piece: dict | None, label_size: float,
              label_col: float, value_col: float, slot_w: float) -> str:
        if piece is None:
            block_h = label_size + CHAR_PIECE_LABEL_GAP + CHAR_ROW_H * 6
            return f'<div style="width:{slot_w:.1f}pt;height:{block_h:.1f}pt"></div>'
        name = " / ".join(AREA_TITLES.get(a, a.upper())
                          for a in piece.get("protectedAreas", []))
        rows = []
        for label, key in stat_fields(piece):
            value = fmt_number(piece.get(key, 0))
            rows.append(
                f'<tr>'
                f'<td style="width:{label_col:.1f}pt;background:#000;color:#fff;'
                f'font-family:CarlitoBold;font-size:{CHAR_LABEL_SIZE}pt;'
                f'text-align:left;padding-left:2.8pt;vertical-align:middle;'
                f'height:{CHAR_ROW_H}pt;'
                f'line-height:{CHAR_LABEL_SIZE}pt;border:0.6pt solid #000">'
                f'{esc(label)}</td>'
                f'<td style="width:{value_col:.1f}pt;background:{BEIGE};'
                f'border:0.6pt solid #000;'
                f'font-family:CarlitoReg;font-size:{CHAR_LABEL_SIZE}pt;'
                f'text-align:center;vertical-align:middle;'
                f'line-height:{CHAR_LABEL_SIZE}pt">'
                f'{esc(value)}</td>'
                f'</tr>'
            )
        table = (
            f'<table class="card" style="width:{label_col + value_col:.1f}pt;'
            f'border-collapse:collapse;border:0.6pt solid #000">'
            + "".join(rows) +
            '</table>'
        )
        return (
            f'<div style="text-align:center;font-size:{label_size}pt;'
            f'font-family:CarlitoBold;line-height:{label_size}pt;'
            f'margin-bottom:{CHAR_PIECE_LABEL_GAP}pt">{esc(name)}</div>'
            + table
        )

    def slot(inner: str, w: float) -> str:
        return (f'<td style="width:{w:.1f}pt;border:none;'
                f'vertical-align:top">{inner}</td>')

    gap_td = f'<td style="width:{CHAR_COL_GAP}pt;border:none"></td>'
    top_row = (slot(block(grid[(0, 0)], PIECE_LABEL_SIZE_TOP,
                         CHAR_LEFT_LABEL_W, CHAR_LEFT_VALUE_W, CHAR_LEFT_W),
                    CHAR_LEFT_W)
               + gap_td
               + slot(block(grid[(0, 1)], PIECE_LABEL_SIZE_TOP,
                            CHAR_RIGHT_LABEL_W, CHAR_RIGHT_VALUE_W,
                            CHAR_RIGHT_W), CHAR_RIGHT_W))
    bot_row = (slot(block(grid[(1, 0)], PIECE_LABEL_SIZE_BOT,
                         CHAR_LEFT_LABEL_W, CHAR_LEFT_VALUE_W, CHAR_LEFT_W),
                    CHAR_LEFT_W)
               + gap_td
               + slot(block(grid[(1, 1)], PIECE_LABEL_SIZE_BOT,
                            CHAR_RIGHT_LABEL_W, CHAR_RIGHT_VALUE_W,
                            CHAR_RIGHT_W), CHAR_RIGHT_W))
    rows = (
        "<tr>" + top_row + "</tr>"
        + f'<tr><td style="height:{CHAR_ROW_GAP}pt;border:none;'
          f'colspan="3"></td></tr>'
        + "<tr>" + bot_row + "</tr>"
    )
    return '<table style="border:none">' + rows + "</table>"


# --- описание ----------------------------------------------------------------
def build_intro_html(spec: dict) -> str:
    intro = spec.get("intro") or []
    if not intro:
        return ""
    para = intro[0]
    return (
        f'<div style="margin-left:3pt;width:{CONTENT_W - 6}pt;'
        f'font-size:{DESC_SIZE}pt;line-height:{DESC_LEADING}pt;'
        f'text-align:justify">{esc(para)}</div>'
    )


# --- сетка модов (нижняя часть страницы 1) --------------------------------
def build_mods_grid(comp: Companion, set_data: dict) -> str:
    allowed_std = set_data.get("allowedModCategories") or ["standardMods"]
    allowed_uniq = set_data.get("allowedUniqueModCategories") or []

    area_mods_map: dict[str, list[str]] = {}
    for area in MODS_AREA_ORDER:
        names = area_mods(comp, area, allowed_std)
        if names:
            area_mods_map[area] = names

    uniq = unique_mod_names(comp, allowed_uniq)

    rows_data: list[tuple[str, list[str]]] = []
    for area in MODS_AREA_ORDER:
        if area in area_mods_map:
            rows_data.append((AREA_TITLES.get(area, area.upper()),
                              area_mods_map[area]))
    if uniq:
        rows_data.append(("УНИКАЛЬНАЯ", uniq))
    if not rows_data:
        return ""

    ncols = 5

    # ширины колонок — по векторным линиям референса (get_drawings):
    # мод-колонки 80.7 / 69.2 / 90.3 / 104.6 / 97.2.
    # Используем измеренные ширины референса, чтобы обёртка текста
    # (Асбестовая подкладка, Звукоизолированная → 2 строки) повторялась
    # точно. Шлем-строку опускаем по правилу отсутствия шлема в данных.
    # Меточную колонку делаем по самой длинной метке + отступ (не фиксированную
    # 81.2): после симметричных отступов CONTENT_W суженее референса, и фикс
    # 81.2 оставлял мод-колонкам недостаточно места — «Сбалансированная»
    # (87.1pt) не помещалась в колонку 2 (85.4pt) и обрывалась. Метка
    # «УНИКАЛЬНАЯ» (59.9pt) требует ~68pt, освобождая pt для мод-колонок.
    label_col = 0.0
    for lbl, _mods in rows_data:
        need = text_w(lbl, MODS_FONT, bold=True) + 8.0
        if need > label_col:
            label_col = need
    col_widths = scale_to(list(MODS_GRID_COLS),
                          CONTENT_W - label_col)

    # чередование цветов: НАГРУДНИК=крем, НАРУЧ=оранжевый, ПОНОЖ=крем,
    # УНИКАЛЬНАЯ=оранжевый (по референсу, без шлема)
    fills = [BEIGE, ORANGE]

    rows_html = []
    for i, (label, mods) in enumerate(rows_data):
        fill = fills[i % 2]
        max_lines = 1
        for c in range(ncols):
            if c < len(mods):
                max_lines = max(max_lines,
                                len(wrap_lines(mods[c], col_widths[c],
                                               MODS_FONT)))
        content_h = max_lines * MODS_LINE_H + MODS_ROW_PAD
        row_h = max(MODS_ROW_H_BY_AREA.get(label, MODS_ROW_MIN_H),
                    content_h)

        cells = []
        for c in range(ncols):
            text = mods[c] if c < len(mods) else ""
            body = "<br/>".join(esc(ln) for ln in
                                wrap_lines(text, col_widths[c], MODS_FONT))
            cells.append(
                f'<td style="width:{col_widths[c]:.1f}pt;background:{fill};'
                f'font-size:{MODS_FONT}pt;text-align:center;'
                f'vertical-align:middle;height:{row_h}pt;'
                f'line-height:{MODS_LINE_H}pt;border:0.6pt solid #000">'
                f'{body}</td>'
            )
        rows_html.append(
            f'<tr>'
            f'<td style="width:{label_col:.1f}pt;background:#000;color:#fff;'
            f'font-family:CarlitoBold;font-size:{MODS_FONT}pt;'
            f'text-align:left;padding-left:3.4pt;'
            f'text-align:center;vertical-align:middle;height:{row_h}pt;'
            f'line-height:{MODS_LINE_H}pt;border:0.6pt solid #000">'
            f'{esc(label)}</td>'
            + "".join(cells) +
            f'</tr>'
        )

    total_w = label_col + sum(col_widths)
    table = (
        f'<table class="mods" style="width:{total_w:.1f}pt;'
        f'border-collapse:collapse">'
        + "".join(rows_html) +
        '</table>'
    )
    return table


# --- матрицы тиров (страница 2) --------------------------------------------
def build_tier_matrix(pieces: list[dict], col_widths: tuple = None) -> str:
    """Матрица тира: шапка — названия деталей (белый на чёрном), строки —
    статысты (метки — белый на чёрном, значения — кремовый)."""
    areas: list[str] = []
    for p in pieces:
        for a in p.get("protectedAreas", []):
            if a not in areas:
                areas.append(a)
    order = {a: i for i, a in enumerate(MODS_AREA_ORDER)}
    areas.sort(key=lambda a: order.get(a, 99))
    area_titles = [AREA_TITLES.get(a, a.upper()) for a in areas]

    pieces = pieces_by_area_order(pieces)
    labels = stat_labels(pieces[0] if pieces else {})
    if col_widths is None:
        label_w = max((text_w(l, TIER_FONT, bold=True) for l in labels),
                      default=0.0)
        label_col = label_w + TIER_LABEL_PAD
        col_widths = tuple(text_w(t, TIER_FONT, bold=True) + TIER_ELEM_PAD
                           for t in area_titles)
    else:
        label_col = col_widths[0]
        col_widths = col_widths[1:]

    head_cells = (
        f'<td style="width:{label_col:.1f}pt;background:#000;'
        f'border:0.6pt solid #000"></td>'
        + "".join(
            f'<td style="width:{cw:.1f}pt;background:#000;color:#fff;'
            f'font-family:CarlitoBold;font-size:{TIER_FONT}pt;'
            f'text-align:center;vertical-align:middle;'
            f'height:{TIER_HEADER_H}pt;line-height:{TIER_FONT}pt;'
            f'border:0.6pt solid #000">{esc(t)}</td>'
            for t, cw in zip(area_titles, col_widths)
        )
    )
    rows = []
    for label, key in stat_fields(pieces[0] if pieces else {}):
        cells = (
            f'<td style="width:{label_col:.1f}pt;background:#000;color:#fff;'
            f'font-family:CarlitoBold;font-size:{TIER_FONT}pt;'
            f'text-align:left;padding-left:{TIER_LABEL_PAD_L}pt;'
            f'vertical-align:middle;height:{TIER_ROW_H}pt;'
            f'line-height:{TIER_FONT}pt;'
            f'border:0.6pt solid #000">{esc(label)}</td>'
            + "".join(
                f'<td style="width:{cw:.1f}pt;background:{BEIGE};'
                f'border:0.6pt solid #000;'
                f'font-family:CarlitoReg;font-size:{TIER_FONT}pt;'
                f'text-align:center;vertical-align:middle;'
                f'line-height:{TIER_FONT}pt">'
                f'{esc(fmt_number(piece.get(key, 0)))}</td>'
                for piece, cw in zip(pieces, col_widths)
            )
        )
        rows.append(f'<tr>{cells}</tr>')

    total_w = label_col + sum(col_widths)
    return (
        f'<table style="border-collapse:collapse;border:0.6pt solid #000;'
        f'width:{total_w:.1f}pt">'
        f'<tr>{head_cells}</tr>' + "".join(rows) +
        '</table>'
    )


def build_tiers_grid(set_data: dict) -> str:
    """Две матрицы тиров рядом (УКРЕПЛЁННАЯ, ТЯЖЁЛАЯ)."""
    matrices: list[tuple[str, list[dict]]] = []
    for key, tier in (set_data.get("tiers") or {}).items():
        if key == "standard":
            continue
        pieces = list(tier.get("pieces", []))
        if pieces:
            matrices.append((key, pieces))
    if not matrices:
        return ""

    # позиции референса: левая матрица x36.2, правая x319.7 (с учётом
    # отступа переплёта)
    left_w = 319.7 + BINDING_MARGIN_L - MARGIN_L - TIER_COL_GAP
    right_w = CONTENT_R - 319.7 - BINDING_MARGIN_L
    left_cols = TIER_LEFT_COLS
    right_cols = TIER_RIGHT_COLS

    def cell(inner: str, w: float) -> str:
        return (f'<td style="width:{w:.1f}pt;border:none;'
                f'vertical-align:top">{inner}</td>')

    gap_td = f'<td style="width:{TIER_COL_GAP}pt;border:none"></td>'
    first = matrices[0]
    second = matrices[1] if len(matrices) > 1 else None
    return (
        '<table style="border:none"><tr>'
        + cell(build_tier_matrix(first[1], left_cols), left_w)
        + gap_td
        + (cell(build_tier_matrix(second[1], right_cols), right_w)
           if second else f'<td style="width:{right_w:.1f}pt;'
           f'border:none"></td>')
        + '</tr></table>'
    )


def build_tier_labels_html(labels: list[str]) -> str:
    """Подписи тиров на позициях референса (центры 146.85 / 449.65)."""
    half = (CONTENT_W - TIER_COL_GAP) / 2.0
    cells = []
    for i, label in enumerate(labels[:2]):
        item = build_section_label_html(label)
        tw = text_w(label, SECTION_SIZE, bold=True)
        rule_w = max(tw + SECTION_RULE_PAD, SECTION_RULE_MIN)
        wrapper_w = rule_w + 30.0
        center = TIER_LABEL_CENTERS[i]
        td_left = MARGIN_L + (0 if i == 0 else half)
        margin_l = center - td_left - wrapper_w / 2.0
        cells.append(
            f'<td style="width:{half:.1f}pt;border:none;vertical-align:top">'
            f'<div style="margin-left:{margin_l:.1f}pt;width:{wrapper_w:.1f}pt;'
            f'text-align:center">{item}</div></td>'
        )
    if len(cells) == 1:
        cells.append(f'<td style="width:{half:.1f}pt;border:none"></td>')
    return '<table style="border:none"><tr>' + "".join(cells) + '</tr></table>'


# --- уникальные моды (страница 2) ------------------------------------------
def build_unique_mods_table(comp: Companion, set_data: dict) -> str:
    """Таблица уникальных модов по референсу: 8 колонок (название,
    ФИЗ.СУ, ЭНРГ.СУ, РАД.СУ, ВЕС, ЦЕНА, ПЕРКИ, ЭФФЕКТЫ). Значения
    вычисляются из данных (statModifiers / weight / cost / perk /
    эффекты); статистика показывается только для первой строки, как
    в референсе."""
    allowed_uniq = set_data.get("allowedUniqueModCategories") or []
    mods = [m for m in comp.unique_mods if m.get("modCategory") in allowed_uniq]

    headers = ["", "ФИЗ. СУ", "ЭНРГ. СУ", "РАД. СУ", "ВЕС", "ЦЕНА",
               "ПЕРКИ", "ЭФФЕКТЫ"]

    def stat_val(mod: dict, key: str) -> str:
        sm = (mod.get("statModifiers") or {}).get(key)
        return fmt_delta(sm["value"]) if sm else "0"

    def mod_val(mod: dict, key: str) -> str:
        m = mod.get(key) or {}
        return fmt_delta(m["value"]) if m else "0"

    rows_data: list[tuple[str, tuple[str, ...]]] = []
    for mod in mods:
        name = comp.mod_names.get(mod.get("id", ""), mod.get("id", ""))
        vals = (stat_val(mod, "physicalDamageRating"),
                stat_val(mod, "energyDamageRating"),
                stat_val(mod, "radiationDamageRating"),
                mod_val(mod, "weightModifier"),
                mod_val(mod, "costModifier"),
                (mod.get("requiredPerk") or "").upper(),
                "")
        effects = [comp.mod_effects.get(e.get("id", ""), "")
                   for e in (mod.get("specialEffects") or [])]
        effects_text = " ".join(e for e in effects if e)
        if effects_text:
            vals = vals[:-1] + (effects_text,)
        rows_data.append((name.upper(), vals))
    if not rows_data:
        return ""

    # таблица уникальных модов — во всю область контента по ширине
    col_widths = scale_to(list(UNIQ_COLS), CONTENT_W)

    # заголовок: колонка с названием — слева, статистические колонки —
    # по центру (как в референсе)
    head_cells = "".join(
        f'<td style="width:{cw:.1f}pt;background:#000;color:#fff;'
        f'font-family:CarlitoBold;font-size:{UNIQ_FONT}pt;'
        + ("text-align:left;padding-left:2.8pt;" if idx == 0 else
           "text-align:center;")
        + f'vertical-align:middle;'
        f'height:{UNIQ_HEADER_H}pt;line-height:{UNIQ_FONT}pt;'
        f'border:0.6pt solid #000">{esc(h)}</td>'
        for idx, (h, cw) in enumerate(zip(headers, col_widths))
    )

    rows_html = []
    fills = [BEIGE, ORANGE]
    for i, (name, vals) in enumerate(rows_data):
        fill = fills[i % 2]
        if name in UNIQ_WRAP_NAMES and " " in name:
            name_lines = name.split(" ", 1)
            name_html = "<br/>".join(esc(ln) for ln in name_lines)
        else:
            name_html = esc(name)
        lines = 1 if name not in UNIQ_WRAP_NAMES else 2
        row_h = max(UNIQ_ROW_MIN_H, lines * UNIQ_LINE_H + 6.4)
        cells = [
            f'<td style="width:{col_widths[0]:.1f}pt;background:#000;color:#fff;'
            f'font-family:CarlitoBold;font-size:{UNIQ_FONT}pt;'
            f'text-align:left;padding-left:2.8pt;vertical-align:middle;'
            f'height:{row_h}pt;line-height:{UNIQ_LINE_H}pt;'
            f'border:0.6pt solid #000">'
            f'{name_html}</td>'
        ]
        for ci in range(1, len(headers)):
            text = vals[ci - 1] if ci - 1 < len(vals) else ""
            cells.append(
                f'<td style="width:{col_widths[ci]:.1f}pt;background:{fill};'
                f'font-size:{UNIQ_FONT}pt;text-align:center;'
                f'vertical-align:middle;height:{row_h}pt;'
                f'line-height:{UNIQ_LINE_H}pt;border:0.6pt solid #000">'
                f'{esc(text)}</td>'
            )
        rows_html.append(f'<tr>' + "".join(cells) + f'</tr>')

    total_w = sum(col_widths)
    return (
        f'<table style="border-collapse:collapse;border:0.6pt solid #000;'
        f'width:{total_w:.1f}pt">'
        f'<tr>{head_cells}</tr>' + "".join(rows_html) +
        '</table>'
    )


# --- страницы ---------------------------------------------------------------
def build_page_1_html(spec: dict, comp: Companion, set_data: dict) -> str:
    title = spec.get("title") or comp.set_names.get(spec["set"], spec["set"])
    pieces = base_pieces(set_data)

    section = build_section_label_html("СТАНДАРТНЫЙ КОМПЛЕКТ ")
    char_grid = build_char_tables_grid(pieces)
    # блок справа: x 315.8 .. 559.3; подпись СТАНДАРТНЫЙ КОМПЛЕКТ на 29.7pt
    # ниже title-черты (реф. y110.3)
    right_block = (
        f'<div style="margin-left:{315.8 + BINDING_MARGIN_L - MARGIN_L:.1f}pt;'
        f'width:{CHAR_BLOCK_W}pt">{section}'
        f'<div style="margin-top:{CHAR_GRID_MARGIN_TOP}pt">{char_grid}</div>'
        f'</div>'
    )

    intro = build_intro_html(spec)
    heading = build_heading_html("ПОДДЕРЖИВАЕМЫЕ МОДИФИКАЦИИ", HEADING_SIZE,
                                HEADING_MARGIN_L)
    mods = build_mods_grid(comp, set_data)

    content = (
        build_title_html(title)
        + f'<div style="margin-top:24.0pt">{right_block}</div>'
        + f'<div style="margin-top:34.0pt">{intro}</div>'
        + f'<div style="margin-top:56.0pt">{heading}</div>'
        + f'<div style="margin-top:26.0pt">{mods}</div>'
    )
    return (
        '<table class="sheet">'
        f'<tr><td style="vertical-align:top;height:841pt;padding:{47.8 + TRIM_MARGIN_TOP:.1f}pt 48pt {47.8 + TRIM_MARGIN_TOP:.1f}pt 48pt">'
        f'{content}</td></tr>'
        '</table>'
    )


def build_page_2_html(spec: dict, comp: Companion, set_data: dict) -> str:
    title = spec.get("title") or comp.set_names.get(spec["set"], spec["set"])
    big_title = esc((title + "").upper())

    matrices = build_tiers_grid(set_data)
    tier_titles = spec.get("tier_titles") or {}
    non_standard = [k for k in (set_data.get("tiers") or {})
                    if k != "standard" and (set_data["tiers"][k].get("pieces"))]
    labels = [tier_titles.get(k, k) for k in non_standard[:2]]
    tier_labels = build_tier_labels_html(labels)

    # Заголовок на две строки по границе слов: слово «МОДИФИКАЦИИ» не
    # обрывает внутри себя (реф. обрывает МОДИФИКАЦ | ИИ — пользователь
    # попросил не переносить слово). «УНИКАЛЬНЫЕ МОДИФИКАЦИИ» — цело на
    # первой строке, название брони — на второй.
    heading_text = f"УНИКАЛЬНЫЕ МОДИФИКАЦИИ<br/>{big_title}".upper()
    heading = build_heading_html(heading_text, BIG_HEADING_SIZE,
                                 BIG_HEADING_MARGIN_L, raw=True)
    uniq = build_unique_mods_table(comp, set_data)

    content = (
        build_title_html("ВАРИАНТЫ", 37.1)
        + f'<div style="margin-top:30.2pt">{tier_labels}</div>'
        + f'<div style="margin-top:20.4pt">{matrices}</div>'
        + f'<div style="margin-top:47.9pt">{heading}</div>'
        + f'<div style="margin-top:9.7pt">{uniq}</div>'
    )
    return (
        '<table class="sheet">'
        f'<tr><td style="vertical-align:top;height:841pt;padding:{47.8 + TRIM_MARGIN_TOP:.1f}pt 48pt {47.8 + TRIM_MARGIN_TOP:.1f}pt 48pt">'
        f'{content}</td></tr>'
        '</table>'
    )


# --- рендер -----------------------------------------------------------------
def render_page(spec: dict, comp: Companion, out_path: str, repo: Path) -> None:
    collection = spec.get("collection", "armor")
    set_key = spec["set"]
    set_data = comp.power_armor[set_key] if collection == "powerArmor" else comp.armor[set_key]

    resources = prepare_resources(repo)
    css = build_css(resources["paper"])
    body = (
        build_page_1_html(spec, comp, set_data)
        + build_page_2_html(spec, comp, set_data)
    )
    doc = f'<html><head><style>{css}</style></head><body>{body}</body></html>'

    out = io.open(out_path, "wb")
    try:
        result = pisa.CreatePDF(doc, dest=out)
    finally:
        out.close()
        if resources["paper"] and Path(resources["paper"]).parent.exists():
            shutil.rmtree(Path(resources["paper"]).parent, ignore_errors=True)
    if result.err:
        raise RuntimeError(f"xhtml2pdf вернул ошибки: {result.err}")


# --- CLI --------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Страница брони в PDF (референсная вёрстка)")
    parser.add_argument("--data", default="data/companion", help="каталог с equipment/ и i18n/")
    parser.add_argument("--pages", default="data/armor-pages", help="каталог с JSON-описаниями")
    parser.add_argument("--out", required=True, help="выходной PDF")
    parser.add_argument("--only", help="собрать только страницу с этим id")
    args = parser.parse_args(argv)

    data_dir = Path(args.data)
    if not data_dir.exists():
        parser.error(f"нет каталога с данными: {data_dir}")
    comp = Companion(data_dir)

    pages_dir = Path(args.pages)
    specs = []
    for path in sorted(pages_dir.glob("*.json")):
        if path.name.startswith("_"):
            continue
        spec = json.loads(path.read_text(encoding="utf-8"))
        if args.only and spec.get("id") != args.only:
            continue
        specs.append(spec)
    if not specs:
        parser.error("не найдено ни одного описания страницы")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    w.register_fonts()
    if len(specs) == 1:
        render_page(specs[0], comp, str(out), Path.cwd().resolve())
    else:
        from pypdf import PdfWriter
        tmp_files = []
        for spec in specs:
            tmp = out.with_suffix(".tmp.pdf")
            render_page(spec, comp, str(tmp), Path.cwd().resolve())
            tmp_files.append(tmp)
        writer = PdfWriter()
        for tmp in tmp_files:
            for page in PdfWriter(tmp).pages:
                writer.add_page(page)
        with open(out, "wb") as fh:
            writer.write(fh)
        for tmp in tmp_files:
            tmp.unlink(missing_ok=True)
    print(f"{out}  ({2 * len(specs)} страниц)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
