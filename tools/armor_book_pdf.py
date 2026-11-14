#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
armor_book_pdf — тестовая страница брони в PDF по стилю книги оружия.

Фон (бумажная текстура), гамма (бежевый #FFEBCD, оранжевый #FFC674,
чёрные шапки, белый текст) и шрифты (Carlito) — как в PDF-справочнике
оружия.  Схема — по референсу «Броня», но в наших шрифтах, цветах,
форматах и размерах, со фоном и картинкой брони (их в референсе не было).

Структура — две страницы на броню (один разворот):
  страница 1 — заголовок; two-column-блок: слева картинка брони
    (квадратная), справа панель элементов в ДВУХ столбцах (3 детали
    + отступы); метки статов — белый на чёрном, значения — на кремовом;
    описание; таблица модов привязана к нижнему краю контента;
  страница 2 — продолжение разворота: заголовок и черта НЕ рисуются;
    матрицы всех тиров (включая базовый): заголовок тира, строки =
    элементы (заливка по ячейкам, чередование цветов), столбцы =
    статысты (в базовом тире — значения, в остальных — дельты).

Пример:
    python3 tools/armor_book_pdf.py \
        --data data/companion \
        --pages data/armor-pages \
        --out docs/render/samples/armor-leather-book.pdf
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).resolve().parent))
import weapon2pdf as w  # noqa: E402
from armor2page import (  # noqa: E402
    AREA_TITLES,
    Companion,
    area_key,
    fmt_delta,
    fmt_number,
    stat_fields,
)

# --- геометрия (как в книге оружия) ----------------------------------------
TITLE_TOP = w.TITLE_TOP          # 47.59
TITLE_SIZE = w.TITLE_SIZE
RULE_TOP = w.RULE_TOP            # 78.37
RULE_H = w.RULE_H
RULE_W = w.RULE_W

# two-column-блок: слева картинка (квадратная), справа панель элементов
IMG_SIDE = 270.0                 # квадратная картинка брони
TWO_COL_GAP = 18.0
LEFT_W = IMG_SIDE
RIGHT_X = w.MARGIN_L + LEFT_W + TWO_COL_GAP
RIGHT_W = w.CONTENT_R - RIGHT_X

# панель элементов: два столбца карточек (3 детали + отступы)
ELEM_COL_GAP = 10.0

# карточка элемента (таблица статов)
CARD_HEADER_H = 17.0
CARD_ROW_H = 13.0
CARD_GAP = 7.0
CARD_TITLE_SIZE = 10.0
CARD_FONT = 8.5

# описание
DESC_LEFT = w.DESC_LEFT
DESC_RIGHT = w.DESC_RIGHT
DESC_SIZE = 10.5
DESC_LEADING = 15.0
DESC_GAP = 8.0

# матрица тиров
TM_TITLE_SIZE = 13.0
TM_TITLE_GAP = 13.0
TM_HEADER_H = 18.0
TM_ROW_H = 14.0
TM_LABEL_W = 70.0
TM_FONT = 9.0
TM_BLOCK_GAP = 18.0
TIER_FILLS = [w.BEIGE, w.ORANGE]  # чередование цветов строк

# верхний край контента на второй странице (без заголовка и черты)
SPREAD_TOP = 75.0

BEIGE = w.BEIGE
ORANGE = w.ORANGE
BLACK = w.BLACK
WHITE = w.WHITE


# --- данные ---------------------------------------------------------------
def base_pieces(set_data: dict, tier_key: str = "standard") -> list[dict]:
    return list((set_data.get("tiers") or {}).get(tier_key, {}).get("pieces", []))


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


def build_mods_card(comp: Companion, set_data: dict) -> dict:
    """Карта модов в формате книги оружия для draw_mods."""
    allowed_std = set_data.get("allowedModCategories") or ["standardMods"]
    allowed_uniq = set_data.get("allowedUniqueModCategories") or []
    mods = []
    for piece in base_pieces(set_data):
        for area in piece.get("protectedAreas", []):
            names = area_mods(comp, area, allowed_std)
            if names:
                mods.append({"slot": AREA_TITLES.get(area, area.upper()),
                            "items": names})
    uniq = unique_mod_names(comp, allowed_uniq)
    if uniq:
        mods.append({"slot": "УНИКАЛЬНЫЙ", "items": uniq})
    return {"id": "armor", "title": "armor", "mods": mods}


# --- общие хелперы рисования ----------------------------------------------
def draw_header(c, title: str) -> None:
    """Заголовок + чёрная линейка (без подзаголовка: у сета нет единых
    Веса/Цены/Редкости — они только у деталей, в таблицах элементов)."""
    w.draw_center_line(c, TITLE_TOP, title.upper(), "Carlito-Bold", TITLE_SIZE)
    c.setFillColor(BLACK)
    c.rect(w.PAGE_W_WORK_CENTER - RULE_W / 2.0,
           w.y_from_top(RULE_TOP), RULE_W, -RULE_H, stroke=0, fill=1)


def _cell_center(c, x, y_top, w_box, h, text, font, size, color=BLACK):
    w.draw_cell_text(c, x, y_top, w_box, h, text, font, size, color=color)


def _grid_lines(c, x, y_top, width, y_bottom, edges):
    """Внешний контур и вертикальные разделители (горизонтальных линий
    между строками нет — строки разделены чередованием цветов)."""
    c.setStrokeColor(BLACK)
    c.setLineWidth(w.RULE_W_PT)
    c.line(x, w.y_from_top(y_top), x + width, w.y_from_top(y_top))
    c.line(x, w.y_from_top(y_bottom), x + width, w.y_from_top(y_bottom))
    for e in edges:
        c.line(e, w.y_from_top(y_top), e, w.y_from_top(y_bottom))


# --- страница 1: картинка + панель элементов (2 столбца) + описание + моды -
def card_height(piece: dict) -> float:
    return CARD_HEADER_H + len(stat_fields(piece)) * CARD_ROW_H


def _crop_square(path: str):
    """Центральный кроп картинки до квадрата."""
    from PIL import Image
    im = Image.open(path).convert("RGBA")
    iw, ih = im.size
    side = min(iw, ih)
    left = (iw - side) // 2
    top = (ih - side) // 2
    return im.crop((left, top, left + side, top + side))


def draw_hero_image(c, spec: dict, pages_dir: Path, y_top: float) -> float:
    """Квадратная картинка брони слева (кроп до квадрата, если горизонтальная)."""
    image = spec.get("image") or {}
    if not image.get("src"):
        return y_top + IMG_SIDE
    src = image["src"]
    if not Path(src).is_absolute():
        src = str((pages_dir / src).resolve())
    if not os.path.exists(src):
        return y_top + IMG_SIDE
    im = _crop_square(src)
    fd, tmp = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    im.save(tmp)
    try:
        box = (w.MARGIN_L, y_top, w.MARGIN_L + IMG_SIDE, y_top + IMG_SIDE)
        w.place_image(c, tmp, box, fit="contain")
    finally:
        os.unlink(tmp)
    return y_top + IMG_SIDE


def draw_element_card(c, piece: dict, x, y_top, width) -> float:
    """Таблица элемента: шапка чёрная, метки — белый на чёрном,
    значения — на кремовом.  Заливки по ячейкам, в حدود сетки."""
    areas = piece.get("protectedAreas") or [""]
    title = " / ".join(AREA_TITLES.get(a, a.upper()) for a in areas) or "ДЕТАЛЬ"

    label_w = width * 0.56
    edges = [x, x + label_w, x + width]

    # шапка (название элемента)
    c.setFillColor(BLACK)
    c.rect(x, w.y_from_top(y_top + CARD_HEADER_H), width, -CARD_HEADER_H, 0, 1)
    _cell_center(c, x, y_top, width, CARD_HEADER_H, title,
                 "Carlito-Bold", CARD_TITLE_SIZE, color=WHITE)

    # строки: метки — белый на чёрном, значения — на кремовом
    y = y_top + CARD_HEADER_H
    for label, key in stat_fields(piece):
        c.setFillColor(BLACK)
        c.rect(x, w.y_from_top(y + CARD_ROW_H), label_w, -CARD_ROW_H, 0, 1)
        _cell_center(c, x, y, label_w, CARD_ROW_H, label,
                     "Carlito", CARD_FONT, color=WHITE)
        c.setFillColor(BEIGE)
        c.rect(x + label_w, w.y_from_top(y + CARD_ROW_H),
               width - label_w, -CARD_ROW_H, 0, 1)
        _cell_center(c, x + label_w, y, width - label_w, CARD_ROW_H,
                     fmt_number(piece.get(key, 0)), "Carlito-Bold", CARD_FONT)
        y += CARD_ROW_H

    _grid_lines(c, x, y_top, width, y, edges)
    return y


def draw_stats_column(c, pieces: list[dict], x, y_top, width) -> float:
    """Столбец таблиц элементов; низ колонки."""
    y = y_top
    for piece in pieces:
        y = draw_element_card(c, piece, x, y, width) + CARD_GAP
    return y - CARD_GAP


def draw_element_panel(c, pieces: list[dict], x, y_top, width) -> float:
    """Панель элементов брони в ДВУХ столбцах (3 детали + отступы)."""
    col_w = (width - ELEM_COL_GAP) / 2.0
    first_col = pieces[:2] if len(pieces) >= 2 else list(pieces)
    second_col = pieces[2:]
    bottom1 = draw_stats_column(c, first_col, x, y_top, col_w)
    bottom2 = draw_stats_column(c, second_col, x + col_w + ELEM_COL_GAP,
                                y_top, col_w)
    return max(bottom1, bottom2)


def draw_two_column(c, spec: dict, comp: Companion, set_data: dict,
                    pages_dir: Path, y_top: float) -> float:
    """Слева картинка брони (квадрат), справа панель элементов в 2 столбца."""
    pieces = base_pieces(set_data)
    img_bottom = draw_hero_image(c, spec, pages_dir, y_top)
    panel_bottom = draw_element_panel(c, pieces, RIGHT_X, y_top, RIGHT_W)
    return max(img_bottom, panel_bottom)


def draw_intro(c, spec: dict, y_top: float, bottom: float) -> float:
    intro = spec.get("intro") or []
    if not intro:
        return y_top
    width = DESC_RIGHT - DESC_LEFT
    y = y_top
    for para in intro:
        lines = w.wrap_text(para, "Carlito", DESC_SIZE, width)
        if y + len(lines) * DESC_LEADING > bottom:
            break
        w.draw_justified(c, DESC_LEFT, width, y, lines,
                         "Carlito", DESC_SIZE, DESC_LEADING)
        y += len(lines) * DESC_LEADING + DESC_GAP
    return y


def draw_mods_section(c, comp: Companion, set_data: dict) -> None:
    """Таблица модов привязана к нижнему краю контента (как в книге оружия)."""
    card = build_mods_card(comp, set_data)
    block = w.mods_block(card)
    w.draw_mods(c, card, block)


# --- страница 2: матрицы всех тиров (чередование цветов по ячейкам) --------
def tier_edges(x, width, label_w, n_stats) -> list[float]:
    step = (width - label_w) / n_stats
    edges = [x, x + label_w]
    for i in range(1, n_stats + 1):
        edges.append(x + label_w + step * i)
    return edges


def draw_tier_matrix(c, base_pieces_list: list[dict], tier_pieces: list[dict],
                     tier_title: str, y_top: float, absolute: bool = False) -> float:
    """Матрица тира: заголовок сверху, строки = элементы (заливка по
    ячейкам, чередование цветов), столбцы = статысты.  Заголовки —
    белый на чёрном.  absolute=True — значения вместо дельт."""
    x = w.MARGIN_L
    width = w.CONTENT_W
    base_by_area = {area_key(p): p for p in base_pieces_list}
    fields = stat_fields(base_pieces_list[0] if base_pieces_list else {})
    edges = tier_edges(x, width, TM_LABEL_W, len(fields))
    n_cells = len(fields) + 1  # метка + статы

    w.draw_center_line(c, y_top, tier_title.upper(), "Carlito-Bold", TM_TITLE_SIZE)
    y = y_top + TM_TITLE_SIZE + TM_TITLE_GAP

    # шапка (статысты) — белый на чёрном, заливка по ячейкам
    c.setFillColor(BLACK)
    for i in range(n_cells):
        cell_x = edges[i]
        cell_w = edges[i + 1] - cell_x
        c.rect(cell_x, w.y_from_top(y + TM_HEADER_H), cell_w, -TM_HEADER_H, 0, 1)
    for i, (label, _) in enumerate(fields):
        _cell_center(c, edges[i + 1], y, edges[i + 2] - edges[i + 1],
                     TM_HEADER_H, label, "Carlito-Bold", TM_FONT, color=WHITE)
    y += TM_HEADER_H

    # строки (элементы) — чередование цветов, заливка по ячейкам
    for idx, piece in enumerate(tier_pieces):
        areas = piece.get("protectedAreas") or [""]
        name = " / ".join(AREA_TITLES.get(a, a.upper()) for a in areas)
        row_fill = TIER_FILLS[idx % 2]
        c.setFillColor(row_fill)
        for i in range(n_cells):
            cell_x = edges[i]
            cell_w = edges[i + 1] - cell_x
            c.rect(cell_x, w.y_from_top(y + TM_ROW_H), cell_w, -TM_ROW_H, 0, 1)
        _cell_center(c, x, y, TM_LABEL_W, TM_ROW_H, name,
                     "Carlito-Bold", TM_FONT)
        base = base_by_area.get(area_key(piece))
        for i, (_, key) in enumerate(fields):
            if absolute:
                value = fmt_number(piece.get(key, 0))
                color = BLACK
            else:
                if base is None or key not in piece or key not in base:
                    value = "—"
                    color = BLACK
                else:
                    value = fmt_delta(piece[key] - base[key])
                    color = BLACK if value != "0" else w.Color(0.54, 0.54, 0.54)
            _cell_center(c, edges[i + 1], y, edges[i + 2] - edges[i + 1],
                         TM_ROW_H, value, "Carlito-Bold", TM_FONT, color=color)
        y += TM_ROW_H

    _grid_lines(c, x, y_top + TM_TITLE_SIZE + TM_TITLE_GAP, width, y, edges)
    return y


def draw_tiers_block(c, set_data: dict, tier_titles: dict,
                     y_top: float) -> float:
    """Матрицы всех тиров (включая базовый); низ блока."""
    base_list = base_pieces(set_data)
    y = y_top
    first = True
    for key, tier in (set_data.get("tiers") or {}).items():
        pieces = list(tier.get("pieces", []))
        if not pieces:
            continue
        if not first:
            y += TM_BLOCK_GAP
        y = draw_tier_matrix(c, base_list, pieces,
                             tier_titles.get(key, key), y,
                             absolute=(key == "standard"))
        first = False
    return y


# --- рендер страницы ------------------------------------------------------
def render_page(spec: dict, comp: Companion, out_path: str, pages_dir: Path,
                page_num: int = 1) -> None:
    collection = spec.get("collection", "armor")
    set_key = spec["set"]
    set_data = comp.power_armor[set_key] if collection == "powerArmor" else comp.armor[set_key]
    title = spec.get("title") or comp.set_names.get(set_key, set_key)

    c = canvas.Canvas(out_path, pagesize=(w.PAGE_W, w.PAGE_H), pageCompression=1)
    c.setTitle(f"{title} — тестовая страница брони")
    c.setAuthor("fallout-2d20.ru")

    # === страница 1: картинка + панель элементов (2 столбца) + моды ===
    w.draw_paper(c)
    draw_header(c, title)
    y = RULE_TOP + RULE_H + 22
    y = draw_two_column(c, spec, comp, set_data, pages_dir, y) + 18
    # описание идёт до шапки модов (таблица модов — от нижнего края)
    mods_heading_top = w.MODS_BOTTOM - w.MODS_HEADING_GAP - w.MODS_HEADING_SIZE
    draw_intro(c, spec, y, mods_heading_top - 12)
    # таблица модов привязана к нижнему краю контента
    draw_mods_section(c, comp, set_data)
    w.draw_page_number(c, page_num)
    c.showPage()

    # === страница 2: матрицы всех тиров (продолжение разворота) ===
    w.draw_paper(c)
    # заголовок и черта НЕ рисуются — страница 2 — продолжение разворота
    draw_tiers_block(c, set_data, spec.get("tier_titles") or {}, SPREAD_TOP)
    w.draw_page_number(c, page_num + 1)
    c.showPage()
    c.save()


# --- CLI -----------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Тестовая страница брони в PDF (стиль книги оружия)")
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

    w.register_fonts()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    total_pages = 0
    for page, spec in enumerate(specs, 1):
        render_page(spec, comp, str(out), pages_dir, page_num=page)
        total_pages += 2  # каждая страница брони: характеристики + тиры
    print(f"{out}  ({total_pages} страниц)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
