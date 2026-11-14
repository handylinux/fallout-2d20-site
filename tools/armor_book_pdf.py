#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
armor_book_pdf — тестовая страница брони в PDF по стилю книги оружия.

Фон (бумажная текстура), гамма (бежевый #FFEBCD, оранжевый #FFC674,
чёрные шапки, белый текст) и шрифты (Carlito) — как в PDF-справочнике
оружия.  Расположение элементов — как на тестовой странице брони:
заголовок с линейкой, подзаголовок (Вес/Цена/Редкость), картинка,
таблица базового комплекта, таблицы дельт по уровням, таблица
доступных модификаций (столбец метки + колонки модов, чередование
бежевого и оранжевого — как в книге оружия).

Пример:
    python3 tools/armor_book_pdf.py \\
        --data data/companion \\
        --pages data/armor-pages \\
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
from armor2page import AREA_TITLES, Companion, fmt_delta, fmt_number, stat_fields  # noqa: E402

# геометрия страницы брони (точки, как в книге оружия)
TITLE_TOP = w.TITLE_TOP          # 47.59
RULE_TOP = w.RULE_TOP            # 78.37
SUBTITLE_TOP = w.SUBTITLE_TOP    # 87.53
IMAGE_BOX = w.IMAGE_BOX          # below subtitle, above content

# контент начинается сразу после картинки (как статы в книге оружия)
BASE_TOP = 307.0

# стили таблиц (книжные)
HEADER_H = 24.0
ROW_H = 13.5
STAT_LABEL_W = 90.0

BEIGE = w.BEIGE
ORANGE = w.ORANGE
BLACK = w.BLACK
WHITE = w.WHITE


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


def area_titles(pieces: list[dict]) -> list[str]:
    titles = []
    for piece in pieces:
        for area in piece.get("protectedAreas", []):
            title = AREA_TITLES.get(area, area.upper())
            if title not in titles:
                titles.append(title)
    return titles


def draw_table_header(c, x, y_top, w_total, labels: list[str]) -> float:
    """Чёрная шапка таблицы с белым текстом. y_top — верх."""
    n = len(labels) - 1
    label_w = STAT_LABEL_W
    val_w = (w_total - label_w) / n
    c.setFillColor(BLACK)
    c.rect(x, w.y_from_top(y_top + HEADER_H), w_total, -HEADER_H, 0, 1)
    w.draw_cell_text(c, x, y_top, label_w, HEADER_H, labels[0],
                     "Carlito-Bold", 9.0, color=WHITE)
    for i, label in enumerate(labels[1:]):
        cx = x + label_w + val_w * i
        w.draw_cell_text(c, cx, y_top, val_w, HEADER_H, label,
                         "Carlito-Bold", 9.0, color=WHITE)
    return y_top + HEADER_H


def draw_stat_row(c, x, y_top, w_total, label: str, values: list[str]) -> float:
    """Строка статов: метка слева, значения по колонкам."""
    n = len(values)
    label_w = STAT_LABEL_W
    val_w = (w_total - label_w) / n
    c.setFillColor(BEIGE)
    c.rect(x, w.y_from_top(y_top + ROW_H), w_total, -ROW_H, 0, 1)
    c.setFillColor(BLACK)
    c.setFont("Carlito-Bold", 8.5)
    c.drawString(x + 5, w.y_from_top(y_top + ROW_H / 2.0 + 0.25 * 8.5 + 1), label)
    for i, value in enumerate(values):
        cx = x + label_w + val_w * i
        w.draw_cell_text(c, cx, y_top, val_w, ROW_H, value, "Carlito", 9.0)
    return y_top + ROW_H


def draw_grid(c, x, y_top, w_total, y_bottom, ncols: int, label_w: float = STAT_LABEL_W):
    """Сетка таблицы (вертикали + горизонтали), 0.6 pt."""
    c.setStrokeColor(BLACK)
    c.setLineWidth(w.RULE_W_PT)
    val_w = (w_total - label_w) / ncols
    c.line(x, w.y_from_top(y_top), x, w.y_from_top(y_bottom))
    c.line(x + w_total, w.y_from_top(y_top), x + w_total, w.y_from_top(y_bottom))
    c.line(x + label_w, w.y_from_top(y_top), x + label_w, w.y_from_top(y_bottom))
    for i in range(1, ncols):
        cx = x + label_w + val_w * i
        c.line(cx, w.y_from_top(y_top), cx, w.y_from_top(y_bottom))
    for y in (y_top, y_bottom):
        c.line(x, w.y_from_top(y), x + w_total, w.y_from_top(y))


def draw_base_table(c, pieces: list[dict], y_top: float) -> float:
    """Таблица базового комплекта: колонки (детали) × строки статов."""
    titles = area_titles(pieces)
    fields = stat_fields(pieces[0])
    left = w.MARGIN_L
    width = w.CONTENT_R - w.MARGIN_L
    y = draw_table_header(c, left, y_top, width, ["Характеристика"] + titles)
    for label, key in fields:
        values = [fmt_number(piece.get(key, 0)) for piece in pieces]
        y = draw_stat_row(c, left, y, width, label, values)
    draw_grid(c, left, y_top, width, y, len(pieces))
    return y


def draw_delta_table(c, base_pieces: list[dict], pieces: list[dict], y_top: float) -> float:
    """Таблица дельты уровня: значения (+N) от базового уровня."""
    titles = area_titles(pieces)
    base_by_area = {
        tuple(sorted(p.get("protectedAreas", []))): p for p in base_pieces
    }
    fields = stat_fields(base_pieces[0] if base_pieces else {})
    left = w.MARGIN_L
    width = w.CONTENT_R - w.MARGIN_L
    y = draw_table_header(c, left, y_top, width, ["Характеристика"] + titles)
    for label, key in fields:
        values = []
        for piece in pieces:
            base = base_by_area.get(tuple(sorted(piece.get("protectedAreas", []))))
            if base is None or key not in piece or key not in base:
                values.append("—")
            else:
                values.append(fmt_delta(piece[key] - base[key]))
        y = draw_stat_row(c, left, y, width, label, values)
    draw_grid(c, left, y_top, width, y, len(pieces))
    return y


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
                mods.append({"slot": AREA_TITLES.get(area, area.upper()), "items": names})
    uniq = unique_mod_names(comp, allowed_uniq)
    if uniq:
        mods.append({"slot": "УНИКАЛЬНЫЙ", "items": uniq})
    return {"id": "armor", "title": "armor", "mods": mods}


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

    # === страница 1: заголовок, картинка, таблицы характеристик ===
    w.draw_paper(c)

    # заголовок + линейка + подзаголовок (как в книге оружия)
    w.draw_center_line(c, TITLE_TOP, title.upper(), "Carlito-Bold", w.TITLE_SIZE)
    c.setFillColor(BLACK)
    c.rect(w.PAGE_W_WORK_CENTER - w.RULE_W / 2.0,
           w.y_from_top(RULE_TOP), w.RULE_W, -w.RULE_H, stroke=0, fill=1)
    subtitle = "Вес: {w}, Цена: {c}, Редкость: {r}".format(
        w=fmt_number(totals["weight"]), c=fmt_number(totals["cost"]),
        r=fmt_number(totals["rarity"]),
    )
    w.draw_center_line(c, SUBTITLE_TOP, subtitle, "Carlito", w.SUBTITLE_SIZE)

    # картинка (путь разрешается относительно каталога страниц,
    # как в HTML: ../../assets/... от pages/armor/)
    image = spec.get("image") or {}
    if image.get("src"):
        src = image["src"]
        if not Path(src).is_absolute():
            src = str((pages_dir / src).resolve())
        w.place_image(c, src, IMAGE_BOX, fit="contain")

    # базовый комплект
    y = draw_base_table(c, pieces, BASE_TOP)

    # уровни (дельты)
    tier_titles = spec.get("tier_titles") or {}
    y += 14
    for key, tier in (set_data.get("tiers") or {}).items():
        if key == "standard":
            continue
        tier_pieces = list(tier.get("pieces", []))
        if not tier_pieces:
            continue
        tier_y = y + 4
        w.draw_center_line(c, tier_y, tier_titles.get(key, key).upper(),
                           "Carlito-Bold", 12.0)
        y = draw_delta_table(c, pieces, tier_pieces, tier_y + 12)
        y += 20

    w.draw_page_number(c, page_num)
    c.showPage()

    # === страница 2: таблица модов в стиле книги оружия ===
    w.draw_paper(c)

    # заголовок страницы (повтор, чтобы страница модов самодостаточна)
    w.draw_center_line(c, TITLE_TOP, title.upper(), "Carlito-Bold", w.TITLE_SIZE)
    c.setFillColor(BLACK)
    c.rect(w.PAGE_W_WORK_CENTER - w.RULE_W / 2.0,
           w.y_from_top(RULE_TOP), w.RULE_W, -w.RULE_H, stroke=0, fill=1)
    w.draw_center_line(c, SUBTITLE_TOP, "МОДИФИКАЦИИ",
                       "Carlito", w.SUBTITLE_SIZE)

    # модификации — таблица книги оружия (нижнепривязанная)
    card = build_mods_card(comp, set_data)
    block = w.mods_block(card)
    if block is None:
        w.draw_center_line(c, w.MODS_HEADING_TOP, "НЕТ ПОДДЕРЖИВАЕМЫХ МОДИФИКАЦИЙ",
                           "Carlito-Bold", w.MODS_HEADING_SIZE)
    else:
        w.draw_mods(c, card, block)

    w.draw_page_number(c, page_num + 1)
    c.showPage()
    c.save()


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
