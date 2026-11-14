#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
armor_book_page — тестовая страница брони в стиле книги оружия.

Фон (бумажная текстура `assets/pdf/paper.jpg`) и гамма (бежевый #FFEBCD,
оранжевый #FFC674, чёрные шапки, белый текст) взяты из PDF-справочника
оружия (docs/weapon-pdf.md), шрифты — Carlito.  Расположение элементов —
как на странице брони (armor2page): заголовок, картинка, карты базового
комплекта, таблицы дельт по уровням.  Таблица доступных модов рисуется
по примеру таблицы модов оружия: столбец метки + колонки модов, блоки по
категориям с чередованием бежевого и оранжевого.

Пример:
    python3 tools/armor_book_page.py \\
        --data data/companion \\
        --pages data/armor-pages \\
        --out pages/armor
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from armor2page import (  # noqa: E402
    AREA_TITLES,
    Companion,
    area_key,
    esc,
    fmt_delta,
    fmt_number,
    stat_fields,
)

# --------------------------------------------------------------------------
# CSS: книга оружия (фон, гамма, шрифты) + элементы страницы брони
# --------------------------------------------------------------------------

BOOK_CSS = r"""
@font-face{
  font-family:'Carlito';
  src:url('../../assets/fonts/Carlito-Regular.ttf') format('truetype');
  font-weight:400;
  font-style:normal;
}
@font-face{
  font-family:'Carlito';
  src:url('../../assets/fonts/Carlito-Bold.ttf') format('truetype');
  font-weight:700;
  font-style:normal;
}

/* фон: та же бумажная текстура, что в PDF, растянута на страницу */
.ab-body{
  margin:0;
  font-family:'Carlito',Calibri,Arial,sans-serif;
  color:#000;
  background-color:#f2f1ef;
  background-image:url('../../assets/pdf/paper.jpg');
  background-size:cover;
  background-position:center;
  background-repeat:no-repeat;
}
.ab-page{max-width:1140px;margin:0 auto;padding:48px 15px 70px}
.ab-container{max-width:720px;margin:0 auto}

/* заголовок */
.ab-header{padding:0 0 8px}
.ab-back{margin:0 0 14px;font-size:.9rem}
.ab-back a{color:#000;text-decoration:underline}
.ab-title{
  margin:0;text-align:center;text-transform:uppercase;
  font-weight:700;font-size:2rem;line-height:1.2;letter-spacing:.02em;
}
.ab-rule{
  width:340px;height:3px;margin:10px auto 0;background:#000;
}
.ab-subtitle{
  margin:10px 0 0;text-align:center;font-size:1.05rem;
}

/* картинка */
.ab-hero{margin:26px 0 30px}
.ab-hero img{display:block;width:100%;max-width:720px;height:auto;margin:0 auto}

/* описание */
.ab-desc{
  margin:0 auto 34px;max-width:720px;
  font-size:.85rem;line-height:1.45;text-align:justify;
}
.ab-desc p{margin:0 0 .7em}
.ab-desc p:last-child{margin-bottom:0}

/* разделы */
.ab-section{margin:0 0 38px}
.ab-section-title{
  margin:0 0 14px;text-align:center;text-transform:uppercase;
  font-weight:700;font-size:1.05rem;letter-spacing:.04em;
}
.ab-section-title::after{
  content:"";display:block;width:120px;height:2px;margin:7px auto 0;background:#000;
}
.ab-tier-title{
  margin:0 0 10px;text-align:center;text-transform:uppercase;
  font-weight:700;font-size:.95rem;letter-spacing:.03em;
}

/* карты базового комплекта (книжная таблица статов, вертикальная) */
.ab-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.ab-card{min-width:0}
.ab-card-name{
  margin:0 0 8px;text-align:center;font-size:.78rem;line-height:1.2;color:#333;
}
.ab-stat-table{
  width:100%;border-collapse:collapse;table-layout:fixed;background:#ffebcd;
}
.ab-stat-table th{
  width:62%;padding:5px 7px;background:#000;color:#fff;
  border:1px solid #fff;text-align:left;font-weight:700;
  font-size:.72rem;line-height:1.25;text-transform:uppercase;letter-spacing:.01em;
}
.ab-stat-table td{
  padding:5px 7px;background:#ffebcd;border:1px solid #000;
  text-align:center;font-weight:700;font-size:.8rem;line-height:1.25;
}

/* таблицы дельт по уровням (книжная таблица, матрица) */
.ab-delta-table{
  width:100%;border-collapse:collapse;table-layout:fixed;background:#ffebcd;
  font-size:.82rem;line-height:1.3;
}
.ab-delta-table th,.ab-delta-table td{
  padding:6px 8px;border:1px solid #000;vertical-align:middle;
}
.ab-delta-table thead th{
  background:#000;color:#fff;text-align:center;font-weight:700;
  font-size:.72rem;text-transform:uppercase;letter-spacing:.02em;
}
.ab-delta-table tbody th{
  background:#ffebcd;text-align:left;font-weight:700;
  font-size:.72rem;text-transform:uppercase;
}
.ab-delta-table td{
  background:#ffebcd;text-align:center;font-weight:700;
}
.ab-delta-table td.is-zero{color:#8a8a8a;font-weight:400}

/* таблица доступных модификаций (книжная таблица модов оружия) */
.ab-mods-heading{
  margin:0 0 12px;text-align:center;text-transform:uppercase;
  font-weight:700;font-size:1.25rem;letter-spacing:.04em;
}
.ab-mods-heading::after{
  content:"";display:block;width:200px;height:2px;margin:8px auto 0;background:#000;
}
.ab-mods-table{
  width:100%;border-collapse:collapse;table-layout:fixed;
  font-size:.8rem;line-height:1.3;
}
.ab-mods-table th,.ab-mods-table td{
  padding:7px 5px;border:1px solid #000;text-align:center;vertical-align:middle;
}
.ab-mods-table .ab-mod-label{
  background:#000;color:#fff;font-weight:700;
  font-size:.72rem;text-transform:uppercase;letter-spacing:.02em;
}
.ab-mods-table .ab-fill-beige{background:#ffebcd}
.ab-mods-table .ab-fill-orange{background:#ffc674}

.ab-footer{
  margin-top:40px;text-align:center;font-size:.78rem;color:#555;
}

@media (max-width: 900px){
  .ab-cards{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media (max-width: 560px){
  .ab-cards{grid-template-columns:1fr}
  .ab-title{font-size:1.6rem}
}
"""

# --------------------------------------------------------------------------
# рендер
# --------------------------------------------------------------------------


def base_pieces(set_data: dict, tier_key: str = "standard") -> list[dict]:
    return list((set_data.get("tiers") or {}).get(tier_key, {}).get("pieces", []))


def set_totals(pieces: list[dict]) -> dict[str, Any]:
    """Суммарные Вес/Цена и макс. Редкость базового комплекта."""
    weight = sum(float(p.get("weight", 0) or 0) for p in pieces)
    cost = sum(float(p.get("cost", 0) or 0) for p in pieces)
    rarity = max((float(p.get("rarity", 0) or 0) for p in pieces), default=0)
    return {
        "weight": int(weight) if float(weight).is_integer() else weight,
        "cost": int(cost) if float(cost).is_integer() else cost,
        "rarity": int(rarity) if float(rarity).is_integer() else rarity,
    }


def render_header(spec: dict, totals: dict[str, Any]) -> str:
    back = spec.get("back") or {}
    back_html = ""
    if back.get("title"):
        back_html = (
            '<p class="ab-back"><a href="' + esc(back.get("href", "#")) + '">'
            + esc(back["title"]) + "</a></p>"
        )
    title = spec.get("title") or ""
    subtitle = "Вес: {w}, Цена: {c}, Редкость: {r}".format(
        w=fmt_number(totals["weight"]),
        c=fmt_number(totals["cost"]),
        r=fmt_number(totals["rarity"]),
    )
    return (
        '<div class="ab-container ab-header">'
        + back_html
        + '<h1 class="ab-title">' + esc(title) + "</h1>"
        + '<div class="ab-rule"></div>'
        + '<p class="ab-subtitle">' + esc(subtitle) + "</p>"
        "</div>"
    )


def render_hero(spec: dict) -> str:
    image = spec.get("image") or {}
    if not image.get("src"):
        return ""
    alt = image.get("alt", spec.get("title", ""))
    return (
        '<div class="ab-container ab-hero">'
        '<img src="' + esc(image["src"]) + '" alt="' + esc(alt) + '"'
        ' loading="lazy" decoding="async">'
        "</div>"
    )


def render_description(spec: dict) -> str:
    intro = spec.get("intro") or []
    if not intro:
        return ""
    paras = "".join("<p>" + esc(p) + "</p>" for p in intro)
    return '<div class="ab-container ab-desc">' + paras + "</div>"


def render_card(piece: dict, comp: Companion) -> str:
    rows = "".join(
        '<tr><th scope="row">' + esc(label) + "</th><td>"
        + esc(fmt_number(piece.get(key, 0))) + "</td></tr>"
        for label, key in stat_fields(piece)
    )
    title = AREA_TITLES.get(piece.get("protectedAreas", [""])[0], "ДЕТАЛЬ")
    name = comp.item_name(piece)
    return (
        '<article class="ab-card">'
        + '<p class="ab-card-name">' + esc(name) + "</p>"
        + '<table class="ab-stat-table"><tbody>'
        + '<tr><th scope="row">' + esc(title) + "</th><td></td></tr>"
        + rows
        + "</tbody></table>"
        "</article>"
    )


def render_base_section(spec: dict, comp: Companion, set_data: dict) -> str:
    pieces = base_pieces(set_data)
    if not pieces:
        return ""
    cards = "".join(render_card(piece, comp) for piece in pieces)
    return (
        '<section class="ab-section">'
        '<div class="ab-container">'
        '<h2 class="ab-section-title">Базовый комплект</h2>'
        '<div class="ab-cards">' + cards + "</div>"
        "</div></section>"
    )


def render_delta_table(base_pieces_list: list[dict], pieces: list[dict]) -> str:
    base_by_area = {area_key(piece): piece for piece in base_pieces_list}
    fields = stat_fields(base_pieces_list[0] if base_pieces_list else {})

    head = "".join(
        '<th scope="col">' + esc(AREA_TITLES.get(a, a.upper())) + "</th>"
        for piece in pieces
        for a in (piece.get("protectedAreas") or ["?"])
    )
    rows = []
    for label, key in fields:
        cells = []
        for piece in pieces:
            base = base_by_area.get(area_key(piece))
            if base is None or key not in piece or key not in base:
                value, zero = "—", True
            else:
                delta = piece[key] - base[key]
                value, zero = fmt_delta(delta), delta == 0
            css = ' class="is-zero"' if zero else ""
            cells.append("<td" + css + ">" + esc(value) + "</td>")
        rows.append('<tr><th scope="row">' + esc(label) + "</th>" + "".join(cells) + "</tr>")
    return (
        '<table class="ab-delta-table">'
        "<thead><tr><th scope=\"col\">Характеристика</th>" + head + "</tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody>"
        "</table>"
    )


def render_tiers_section(spec: dict, comp: Companion, set_data: dict) -> str:
    tier_titles = spec.get("tier_titles") or {}
    base_list = base_pieces(set_data)
    blocks = []
    for key, tier in (set_data.get("tiers") or {}).items():
        if key == "standard":
            continue
        pieces = list(tier.get("pieces", []))
        if not pieces:
            continue
        title = tier_titles.get(key, key)
        blocks.append(
            '<div class="ab-tier">'
            '<h3 class="ab-tier-title">' + esc(title) + "</h3>"
            + render_delta_table(base_list, pieces)
            + "</div>"
        )
    if not blocks:
        return ""
    return (
        '<section class="ab-section">'
        '<div class="ab-container">'
        '<h2 class="ab-section-title">Уровни</h2>'
        + "".join(blocks)
        + "</div></section>"
    )


def area_mods(comp: Companion, area: str, category: str = "standardMods") -> list[dict]:
    return [
        mod
        for mod in comp.mods
        if mod.get("modCategory") == category and area in (mod.get("protectedAreas") or [])
    ]


def unique_mods(comp: Companion) -> list[dict]:
    return [
        mod
        for mod in comp.unique_mods
        if (mod.get("modCategory") or "").endswith("UniqueMods")
    ]


def render_mods_table(comp: Companion, set_data: dict) -> str:
    """Таблица доступных модов по примеру таблицы модов оружия."""
    # категории: части брони в порядке базового комплекта, затем уникальные
    areas: list[str] = []
    for piece in base_pieces(set_data):
        for area in piece.get("protectedAreas", []):
            if area not in areas:
                areas.append(area)

    blocks: list[tuple[str, list[dict]]] = []
    for area in areas:
        mods = area_mods(comp, area)
        if mods:
            blocks.append((AREA_TITLES.get(area, area.upper()), mods))
    uniq = unique_mods(comp)
    if uniq:
        blocks.append(("УНИКАЛЬНЫЙ", uniq))

    if not blocks:
        return (
            '<h2 class="ab-mods-heading">Нет поддерживаемых модификаций</h2>'
        )

    ncols = max(1, min(6, max(len(mods) for _, mods in blocks)))
    colgroup = '<colgroup><col style="width:22%">' + "".join(
        "<col>" for _ in range(ncols)
    ) + "</colgroup>"

    rows = []
    for bi, (label, mods) in enumerate(blocks):
        fill = "ab-fill-beige" if bi % 2 == 0 else "ab-fill-orange"
        chunks = [mods[i:i + ncols] for i in range(0, len(mods), ncols)] or [[]]
        for ci, chunk in enumerate(chunks):
            cells = []
            for i in range(ncols):
                if i < len(chunk):
                    name = comp.mod_names.get(chunk[i].get("id", ""), chunk[i].get("id", ""))
                    cells.append(
                        '<td class="' + fill + '">' + esc(name) + "</td>"
                    )
                else:
                    cells.append('<td class="' + fill + '"></td>')
            if ci == 0:
                rows.append(
                    '<tr><th class="ab-mod-label" rowspan="' + str(len(chunks))
                    + '">' + esc(label) + "</th>" + "".join(cells) + "</tr>"
                )
            else:
                rows.append("<tr>" + "".join(cells) + "</tr>")

    return (
        '<h2 class="ab-mods-heading">Поддерживаемые модификации</h2>'
        '<div class="ab-container">'
        '<table class="ab-mods-table">' + colgroup + "".join(rows) + "</table>"
        "</div>"
    )


def render_mods_section(spec: dict, comp: Companion, set_data: dict) -> str:
    table = render_mods_table(comp, set_data)
    if not table:
        return ""
    return '<section class="ab-section">' + table + "</section>"


def render_page(spec: dict, comp: Companion) -> str:
    collection = spec.get("collection", "armor")
    set_key = spec["set"]
    set_data = comp.power_armor[set_key] if collection == "powerArmor" else comp.armor[set_key]
    title = spec.get("title") or comp.set_names.get(set_key, set_key)

    pieces = base_pieces(set_data)
    totals = set_totals(pieces)

    return (
        "<!DOCTYPE html>\n"
        '<html lang="ru">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>" + esc(title) + "</title>\n"
        '<meta name="generator" content="armor_book_page">\n'
        "<style>" + BOOK_CSS + "</style>\n"
        "</head>\n"
        '<body class="ab-body">\n'
        '<div class="ab-page">\n'
        + render_header(spec, totals)
        + render_hero(spec)
        + render_description(spec)
        + render_base_section(spec, comp, set_data)
        + render_tiers_section(spec, comp, set_data)
        + render_mods_section(spec, comp, set_data)
        + '<div class="ab-container ab-footer">Страница собрана из данных '
        "Fallout 2d20 Companion</div>\n"
        "</div>\n</body>\n</html>\n"
    )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Тестовая страница брони в стиле книги оружия")
    parser.add_argument("--data", default="data/companion", help="каталог с equipment/ и i18n/")
    parser.add_argument("--pages", default="data/armor-pages", help="каталог с JSON-описаниями страниц")
    parser.add_argument("--out", default="pages/armor", help="каталог для готовых HTML")
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

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for spec in specs:
        document = render_page(spec, comp)
        filename = f"{spec['slug']}-book.html"
        (out_dir / filename).write_text(document, encoding="utf-8")
        print(f"{out_dir / filename}  {len(document):,} B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
