#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
armor_book_pdf — тестовая страница брони в PDF по стилю книги оружия.

Фон (бумажная текстура), гамма (бежевый #FFEBCD, оранжевый #FFC674,
чёрные шапки, белый текст) и шрифты (Carlito) — как в PDF-справочнике
оружия.  Расположение — как на странице брони, в two-column-блоке.

Структура — две страницы на броню:
  страница 1 — заголовок, два столбца (слева броня, справа характеристики
    её элементов: грудь/ноги/руки), затем краткое описание;
  страница 2 — матрицы тиров (строки = элементы, столбцы = дельты статов,
    заголовок = тип тира) и ниже таблица модификаций в книжном стиле.

Пример:
    python3 tools/armor_book_pdf.py \
        --data data/companion \
        --pages data/armor-pages \
        --out docs/render/samples/armor-leather-book.pdf
"""

from __future__ import annotations

import argparse
import json
import sys
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
SUBTITLE_TOP = w.SUBTITLE_TOP    # 87.53
SUBTITLE_SIZE = w.SUBTITLE_SIZE

# two-column-блок (слева броня, справа статы элементов)
HERO_TOP = 126.0
HERO_GAP = 18.0
LEFT_W = 288.0                   # колонка с картинкой
LEFT_X = w.MARGIN_L
RIGHT_X = LEFT_X + LEFT_W + HERO_GAP
RIGHT_W = w.CONTENT_R - RIGHT_X

# карточка элемента (вертикальная таблица статов)
CARD_HEADER_H = 17.0
CARD_ROW_H = 13.0
CARD_GAP = 7.0
CARD_TITLE_SIZE = 10.5
CARD_FONT = 9.0

# матрица тиров
TM_TITLE_SIZE = 13.0
TM_TITLE_GAP = 13.0
TM_HEADER_H = 18.0
TM_ROW_H = 14.0
TM_LABEL_W = 70.0
TM_FONT = 9.0
TM_BLOCK_GAP = 18.0

# описание
DESC_LEFT = w.DESC_LEFT
DESC_RIGHT = w.DESC_RIGHT
DESC_SIZE = 10.5
DESC_LEADING = 15.0
DESC_GAP = 8.0

BEIGE = w.BEIGE
ORANGE = w.ORANGE
BLACK = w.BLACK
WHITE = w.WHITE


# --- данные ---------------------------------------------------------------
def base_pieces(set_data: dict, tier_key: str = "standard") -> list[dict]:
    return list((set_data.get("tiers") or {}).get(tier_key, {}).get("pieces", []))


def set_totals(pieces: list[dict]) -> dict:
    weight = sum(float(p.get("weight", 0) or 0) for p in pieces)
    cost = sum(float(p.get("cost", 0) or 0) for p in pieces)
    rarity = max((float(p.get("rarity", 0) or 0) for p in pieces), default=0)
    return {
        "weight": int(weight) if float(weight).is_integer() else weight,
        "cost": int(cost) if float(cost).is_integer() else cost,
        "rarity": int(rarity) if float(rarity).is_integer() else rarity,
    }


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
def draw_header(c, title: str, totals: dict) -> None:
    """Заголовок + чёрная линейка + подзаголовок (как в книге оружия)."""
    w.draw_center_line(c, TITLE_TOP, title.upper(), "Carlito-Bold", TITLE_SIZE)
    c.setFillColor(BLACK)
    c.rect(w.PAGE_W_WORK_CENTER - RULE_W / 2.0,
           w.y_from_top(RULE_TOP), RULE_W, -RULE_H, stroke=0, fill=1)
    subtitle = "Вес: {w}, Цена: {c}, Редкость: {r}".format(
        w=fmt_number(totals["weight"]), c=fmt_number(totals["cost"]),
        r=fmt_number(totals["rarity"]),
    )
    w.draw_center_line(c, SUBTITLE_TOP, subtitle, "Carlito", SUBTITLE_SIZE)


def _text_left(c, x, y_top, w_box, h, text, font, size, color=BLACK, pad=4.0):
    """Текст слева, по вертикали по центру ячейки."""
    c.setFillColor(color)
    c.setFont(font, size)
    block = w.ASCENT * size
    baseline = w.y_from_top(y_top + (h - block) / 2.0 + w.ASCENT * size)
    c.drawString(x + pad, baseline, text)


def _cell_center(c, x, y_top, w_box, h, text, font, size, color=BLACK):
    w.draw_cell_text(c, x, y_top, w_box, h, text, font, size, color=color)


def _grid_lines(c, x, y_top, width, y_bottom, edges):
    c.setStrokeColor(BLACK)
    c.setLineWidth(w.RULE_W_PT)
    c.line(x, w.y_from_top(y_top), x + width, w.y_from_top(y_top))
    c.line(x, w.y_from_top(y_bottom), x + width, w.y_from_top(y_bottom))
    for e in edges:
        c.line(e, w.y_from_top(y_top), e, w.y_from_top(y_bottom))


# --- страница 1: броня + характеристики + описание ----------------------
def stat_card_height(piece: dict) -> float:
    return CARD_HEADER_H + len(stat_fields(piece)) * CARD_ROW_H


def draw_stat_card(c, piece: dict, x, y_top, width) -> float:
    """Вертикальная карточка элемента: чёрная шапка + строки статов."""
    areas = piece.get("protectedAreas") or [""]
    title = " / ".join(AREA_TITLES.get(a, a.upper()) for a in areas) or "ДЕТАЛЬ"

    # шапка
    c.setFillColor(BLACK)
    c.rect(x, w.y_from_top(y_top + CARD_HEADER_H), width, -CARD_HEADER_H, 0, 1)
    _cell_center(c, x, y_top, width, CARD_HEADER_H, title,
                 "Carlito-Bold", CARD_TITLE_SIZE, color=WHITE)

    # строки
    label_w = width * 0.56
    y = y_top + CARD_HEADER_H
    edges = [x, x + label_w, x + width]
    for label, key in stat_fields(piece):
        c.setFillColor(BEIGE)
        c.rect(x, w.y_from_top(y + CARD_ROW_H), width, -CARD_ROW_H, 0, 1)
        _text_left(c, x, y, label_w, CARD_ROW_H, label, "Carlito", CARD_FONT)
        _cell_center(c, x + label_w, y, width - label_w, CARD_ROW_H,
                     fmt_number(piece.get(key, 0)), "Carlito-Bold", CARD_FONT)
        y += CARD_ROW_H
    _grid_lines(c, x, y_top, width, y, edges)
    return y


def draw_stats_column(c, pieces: list[dict], x, y_top, width) -> float:
    """Столбец карточек элементов; возвращает низ колонки."""
    y = y_top
    for piece in pieces:
        y = draw_stat_card(c, piece, x, y, width) + CARD_GAP
    return y - CARD_GAP


def draw_hero(c, spec: dict, comp: Companion, set_data: dict,
              pages_dir: Path, y_top: float) -> float:
    """Two-column-блок: слева броня, справа характеристики элементов."""
    pieces = base_pieces(set_data)
    col_h = sum(stat_card_height(p) for p in pieces) + CARD_GAP * max(0, len(pieces) - 1)

    # картинка (путь разрешается относительно каталога страниц,
    # как в HTML: ../../assets/... от pages/armor/)
    image_box = (LEFT_X, y_top, LEFT_X + LEFT_W, y_top + col_h)
    image = spec.get("image") or {}
    if image.get("src"):
        src = image["src"]
        if not Path(src).is_absolute():
            src = str((pages_dir / src).resolve())
        w.place_image(c, src, image_box, fit="contain")

    # справа — характеристики элементов
    draw_stats_column(c, pieces, RIGHT_X, y_top, RIGHT_W)
    return y_top + col_h


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


# --- страница 2: матрицы тиров + таблица модов ----------------------------
def tier_edges(x, width, label_w, n_stats) -> list[float]:
    step = (width - label_w) / n_stats
    edges = [x, x + label_w]
    for i in range(1, n_stats + 1):
        edges.append(x + label_w + step * i)
    return edges


def draw_tier_matrix(c, base_pieces_list: list[dict], tier_pieces: list[dict],
                     tier_title: str, y_top: float) -> float:
    """Матрица тира: строки = элементы, столбцы = дельты статов."""
    x = w.MARGIN_L
    width = w.CONTENT_W
    base_by_area = {area_key(p): p for p in base_pieces_list}
    fields = stat_fields(base_pieces_list[0] if base_pieces_list else {})
    edges = tier_edges(x, width, TM_LABEL_W, len(fields))

    # заголовок тира
    w.draw_center_line(c, y_top, tier_title.upper(), "Carlito-Bold", TM_TITLE_SIZE)
    y = y_top + TM_TITLE_SIZE + TM_TITLE_GAP

    # шапка
    c.setFillColor(BLACK)
    c.rect(x, w.y_from_top(y + TM_HEADER_H), width, -TM_HEADER_H, 0, 1)
    for i, (label, _) in enumerate(fields):
        _cell_center(c, edges[i + 1], y, edges[i + 2] - edges[i + 1],
                     TM_HEADER_H, label, "Carlito-Bold", TM_FONT, color=WHITE)
    y += TM_HEADER_H

    # строки
    for piece in tier_pieces:
        areas = piece.get("protectedAreas") or [""]
        name = " / ".join(AREA_TITLES.get(a, a.upper()) for a in areas)
        c.setFillColor(BEIGE)
        c.rect(x, w.y_from_top(y + TM_ROW_H), width, -TM_ROW_H, 0, 1)
        _text_left(c, x, y, TM_LABEL_W, TM_ROW_H, name, "Carlito-Bold", TM_FONT)
        base = base_by_area.get(area_key(piece))
        for i, (_, key) in enumerate(fields):
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
    """Все матрицы тиров; возвращает низ блока."""
    base_list = base_pieces(set_data)
    y = y_top
    first = True
    for key, tier in (set_data.get("tiers") or {}).items():
        if key == "standard":
            continue
        pieces = list(tier.get("pieces", []))
        if not pieces:
            continue
        if not first:
            y += TM_BLOCK_GAP
        y = draw_tier_matrix(c, base_list, pieces,
                             tier_titles.get(key, key), y)
        first = False
    return y


def draw_mods_section(c, comp: Companion, set_data: dict, y_top: float) -> None:
    """Таблица модов в книжном стиле, сразу под матрицами тиров.

    y_top — желаемый верх таблицы; шапка идёт выше него на MODS_HEADING_GAP.
    Нижняя граница считается по высоте блока.
    """
    card = build_mods_card(comp, set_data)
    block = w.mods_block(card)
    if block is None:
        w.draw_center_line(c, y_top, "НЕТ ПОДДЕРЖИВАЕМЫХ МОДИФИКАЦИЙ",
                           "Carlito-Bold", w.MODS_HEADING_SIZE)
        return
    # подгоняем позицию: верх — как задано, низ — по высоте блока
    rows, _top, ncols = block
    bottom = y_top + sum(r["h"] for r in rows)
    adjusted = (rows, y_top, ncols)
    w.draw_mods(c, card, adjusted, bottom=bottom)


# --- рендер страницы ------------------------------------------------------
def render_page(spec: dict, comp: Companion, out_path: str, pages_dir: Path,
                page_num: int = 1) -> None:
    collection = spec.get("collection", "armor")
    set_key = spec["set"]
    set_data = comp.power_armor[set_key] if collection == "powerArmor" else comp.armor[set_key]
    title = spec.get("title") or comp.set_names.get(set_key, set_key)

    pieces = base_pieces(set_data)
    totals = set_totals(pieces)

    c = canvas.Canvas(out_path, pagesize=(w.PAGE_W, w.PAGE_H), pageCompression=1)
    c.setTitle(f"{title} — тестовая страница брони")
    c.setAuthor("fallout-2d20.ru")

    tier_titles = spec.get("tier_titles") or {}

    # === страница 1: броня + характеристики + описание ===
    w.draw_paper(c)
    draw_header(c, title, totals)
    hero_bottom = draw_hero(c, spec, comp, set_data, pages_dir, HERO_TOP)
    draw_intro(c, spec, hero_bottom + 16, 640.0)
    w.draw_page_number(c, page_num)
    c.showPage()

    # === страница 2: матрицы тиров + таблица модов ===
    w.draw_paper(c)
    draw_header(c, title, totals)
    tiers_top = 126.0
    tiers_bottom = draw_tiers_block(c, set_data, tier_titles, tiers_top)
    # таблица модов сразу под матрицами: шапка идёт выше верха на MODS_HEADING_GAP
    mods_top = tiers_bottom + w.MODS_HEADING_GAP + 6.0
    draw_mods_section(c, comp, set_data, mods_top)
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
        total_pages += 2  # каждая страница брони: характеристики + модификации
    print(f"{out}  ({total_pages} страниц)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
