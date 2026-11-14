#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
armor_book_pdf — тестовая страница брони в PDF по стилю книги оружия.

Конвейер — сначала HTML, потом PDF:
  данные брони  →  печатный HTML (стиль книги оружия)  →  xhtml2pdf  →  PDF

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
    элементы (чередование цветов), столбцы = статысты (в базовом тире —
    значения, в остальных — дельты).

Пример:
    python3 tools/armor_book_pdf.py \
        --data data/companion \
        --pages data/armor-pages \
        --out docs/render/samples/armor-leather-book.pdf
"""

from __future__ import annotations

import argparse
import html
import io
import json
import shutil
import sys
from pathlib import Path

from xhtml2pdf import pisa

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
TITLE_LEADING = 0.75 * TITLE_SIZE

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
CARD_TITLE_SIZE = 11.5
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
TM_LABEL_W = 66.0          # узкий столбец с названиями элементов
TM_COL_W = 20.0            # единые узкие столбцы статов (по значению)
TM_FONT = 9.0
TM_CELL_PAD = "padding:0 2pt"  # минимальный отступ — ячейка плотно к содержимому
TM_BLOCK_GAP = 18.0
TM_TIER_GAP = 12.0        # отступ между стандартным и блоком «в 2 столбца»

# верхний край контента на второй странице (без заголовка и черты)
SPREAD_TOP = 75.0

BEIGE = "#FFEBCD"
ORANGE = "#FFC674"
BLACK = "#000000"
WHITE = "#FFFFFF"


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
    """Карта модов в формате книги оружия для таблицы модов."""
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


# --- подготовка временных ресурсов (для xhtml2pdf) ------------------------
def prepare_resources(spec: dict, pages_dir: Path, repo: Path) -> dict:
    """Сгенерировать временные ресурсы внутри репозитория: растянутую
    бумагу до размера A4 и квадратный кроп картинки брони."""
    from PIL import Image

    tmp_dir = repo / "docs" / "render" / ".tmp-pdf"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # бумага: текстура растягивается до A4 (xhtml2pdf не знает background-size)
    paper = Image.open(repo / "assets" / "pdf" / "paper.jpg").convert("RGB")
    paper.resize((1191, 1684), Image.LANCZOS).save(
        tmp_dir / "paper_a4.jpg", quality=90)

    # картинка брони: центральный кроп до квадрата
    resources = {"paper": str(tmp_dir / "paper_a4.jpg")}
    image = spec.get("image") or {}
    src = image.get("src")
    if src:
        if not Path(src).is_absolute():
            src = str((pages_dir / src).resolve())
        if Path(src).exists():
            im = Image.open(src).convert("RGBA")
            iw, ih = im.size
            side = min(iw, ih)
            im = im.crop(((iw - side) // 2, (ih - side) // 2,
                          (iw - side) // 2 + side, (ih - side) // 2 + side))
            img_path = tmp_dir / "armor_square.png"
            im.save(img_path)
            resources["image"] = str(img_path)

    return resources


# --- генерация HTML --------------------------------------------------------
def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


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


def build_header_html(title: str) -> str:
    title = esc(title.upper())
    rule_margin = RULE_TOP - (TITLE_TOP + TITLE_LEADING)
    return (
        f'<div style="margin-top:{TITLE_TOP}pt;text-align:center;'
        f'font-size:{TITLE_SIZE}pt;font-family:CarlitoBold;line-height:{TITLE_LEADING}pt">'
        f'{title}</div>'
        f'<div style="width:{RULE_W}pt;height:{RULE_H}pt;background:#000;'
        f'margin:{rule_margin}pt auto 0 auto"></div>'
    )


def build_element_card_html(piece: dict, card_w: float, comp: Companion) -> str:
    name = comp.item_name(piece)
    label_w = card_w * 0.56
    value_w = card_w - label_w
    rows = []
    for label, key in stat_fields(piece):
        rows.append(
            f'<tr>'
            f'<td style="width:{label_w:.1f}pt;background:#000;color:#fff;'
            f'font-size:{CARD_FONT}pt;text-align:center;'
            f'height:{CARD_ROW_H}pt;line-height:{CARD_ROW_H}pt">'
            f'{esc(label)}</td>'
            f'<td style="width:{value_w:.1f}pt;background:{BEIGE};color:#000;'
            f'font-family:CarlitoBold;font-size:{CARD_FONT}pt;text-align:center;'
            f'height:{CARD_ROW_H}pt;line-height:{CARD_ROW_H}pt">'
            f'{esc(fmt_number(piece.get(key, 0)))}</td>'
            f'</tr>'
        )
    return (
        f'<table class="card" style="width:{card_w:.1f}pt;border-collapse:'
        f'collapse;border:0.6pt solid #000">'
        f'<tr><td colspan="2" style="background:#000;color:#fff;'
        f'font-family:CarlitoBold;font-size:{CARD_TITLE_SIZE}pt;text-align:center;'
        f'height:{CARD_HEADER_H}pt;line-height:{CARD_HEADER_H}pt;'
        f'border:0.6pt solid #000">{esc(name)}</td></tr>'
        + "".join(rows) +
        '</table>'
    )


def build_element_panel_html(pieces: list[dict], panel_w: float,
                             comp: Companion) -> str:
    """Панель элементов брони в ДВУХ столбцах (3 детали + отступы)."""
    col_w = (panel_w - ELEM_COL_GAP) / 2.0
    first_col = pieces[:2] if len(pieces) >= 2 else list(pieces)
    second_col = pieces[2:]

    def column(col_pieces: list[dict]) -> str:
        out = []
        for i, piece in enumerate(col_pieces):
            if i:
                out.append(f'<div style="height:{CARD_GAP}pt"></div>')
            out.append(build_element_card_html(piece, col_w, comp))
        return "".join(out)

    return (
        f'<table style="width:{panel_w:.1f}pt;border:none">'
        f'<tr>'
        f'<td style="width:{col_w:.1f}pt;border:none;vertical-align:top">'
        f'{column(first_col)}</td>'
        f'<td style="width:{ELEM_COL_GAP}pt;border:none"></td>'
        f'<td style="width:{col_w:.1f}pt;border:none;vertical-align:top">'
        f'{column(second_col)}</td>'
        f'</tr></table>'
    )


def build_two_column_html(spec: dict, set_data: dict, resources: dict,
                          comp: Companion) -> str:
    """Слева картинка брони (квадрат), справа панель элементов в 2 столбца."""
    pieces = base_pieces(set_data)
    img = ""
    if resources.get("image"):
        img = (f'<img src="file://{resources["image"]}" '
               f'style="width:{IMG_SIDE}pt;height:{IMG_SIDE}pt">')
    panel = build_element_panel_html(pieces, RIGHT_W, comp)
    return (
        f'<table style="border:none">'
        f'<tr>'
        f'<td style="width:{LEFT_W}pt;border:none;vertical-align:top">'
        f'{img}</td>'
        f'<td style="width:{TWO_COL_GAP}pt;border:none"></td>'
        f'<td style="width:{RIGHT_W}pt;border:none;vertical-align:top">'
        f'{panel}</td>'
        f'</tr></table>'
    )


def build_intro_html(spec: dict) -> str:
    intro = spec.get("intro") or []
    if not intro:
        return ""
    out = []
    for para in intro:
        out.append(
            f'<div style="width:{DESC_RIGHT - DESC_LEFT}pt;'
            f'font-size:{DESC_SIZE}pt;line-height:{DESC_LEADING}pt;'
            f'text-align:justify;margin-top:{DESC_GAP}pt">'
            f'{esc(para)}</div>'
        )
    return "".join(out)


def build_mods_html(comp: Companion, set_data: dict) -> tuple[str, float]:
    """Таблица модов в стиле книги оружия (заголовок + чёрная метка +
    чередующиеся кремовый/оранжевый блоки).  Рисуется в нижней части
    страницы (вторая строка sheet-таблицы).  Возвращает (html, высота)."""
    card = build_mods_card(comp, set_data)
    block = w.mods_block(card)
    rows, table_top, ncols = block
    table_h = w.MODS_BOTTOM - table_top
    labels = w.DEFAULT_LABELS

    step = (w.MODS_RIGHT - w.MODS_LABEL_RIGHT) / ncols
    mod_col_w = step
    label_w = w.MODS_LABEL_W

    # строки: по одной на категорию (каждая — метка + ячейки модов)
    body = []
    for cat_i, cat in enumerate(card["mods"]):
        items = cat.get("items") or []
        fill = BEIGE if cat_i % 2 == 0 else ORANGE
        cells = []
        for ci in range(ncols):
            text = items[ci] if ci < len(items) else ""
            cells.append(
                f'<td style="width:{mod_col_w:.1f}pt;background:{fill};'
                f'font-size:{w.MODS_FONT_SIZE}pt;text-align:center;'
                f'vertical-align:middle;height:{w.MODS_MIN_ROW}pt;'
                f'line-height:13pt;border:0.6pt solid #000">'
                f'{esc(text)}</td>'
            )
        top_border = "#fff" if cat_i else "#000"
        body.append(
            f'<tr>'
            f'<td style="width:{label_w:.1f}pt;background:#000;color:#fff;'
            f'font-family:CarlitoBold;font-size:{w.MODS_LABEL_SIZE}pt;'
            f'text-align:center;vertical-align:middle;height:{w.MODS_MIN_ROW}pt;'
            f'line-height:13pt;border:0.6pt solid #000;border-top:0.6pt solid {top_border}">'
            f'{esc((cat.get("slot") or "").upper())}</td>'
            + "".join(cells) +
            f'</tr>'
        )

    table = (
        f'<table class="mods" style="width:{label_w + ncols * mod_col_w:.1f}pt;'
        f'border-collapse:collapse">'
        + "".join(body) +
        f'</table>'
    )

    html = (
        f'<div style="text-align:center;font-size:{w.MODS_HEADING_SIZE}pt;'
        f'font-family:CarlitoBold;line-height:{w.MODS_HEADING_SIZE}pt;'
        f'margin-bottom:{w.MODS_HEADING_GAP - w.MODS_HEADING_SIZE}pt">'
        f'{esc(labels["mods_heading"])}</div>'
        f'{table}'
    )
    # высота блока: заголовок (с отступом до таблицы) + таблица
    height = w.MODS_HEADING_GAP + table_h
    return html, height


def build_page_number_html(page: int) -> str:
    """Номер страницы внизу по центру (разворот)."""
    return (
        f'<div style="text-align:center;font-size:9pt;color:#6a5530;'
        f'line-height:11pt">{page}</div>'
    )


# --- матрицы тиров ----------------------------------------------------------
def build_tier_matrix_html(base_pieces_list: list[dict], tier_pieces: list[dict],
                           tier_title: str, absolute: bool = False) -> str:
    """Матрица тира: заголовок сверху, строки = элементы (чередование
    цветов), столбцы = статысты.  Заголовки (названия статов: ФИЗ. СУ,
    ВЕС, РЕДКОСТЬ) — белый текст на чёрном.  Единые узкие столбцы: ширина
    ячейки по значению (числу), не по заголовку — узко везде, таблица не
    выходит за область контента."""
    base_by_area = {area_key(p): p for p in base_pieces_list}
    fields = stat_fields(base_pieces_list[0] if base_pieces_list else {})
    fills = [BEIGE, ORANGE]
    label_w = TM_LABEL_W
    col_w = TM_COL_W
    n = len(fields)
    table_w = label_w + col_w * n

    def value_of(piece: dict, key: str) -> str:
        base = base_by_area.get(area_key(piece))
        if absolute:
            return fmt_number(piece.get(key, 0))
        if base is None or key not in piece or key not in base:
            return "—"
        return fmt_delta(piece[key] - base[key])

    head_cells = "".join(
        f'<td style="width:{col_w}pt;{TM_CELL_PAD};background:#000;color:#fff;'
        f'font-family:CarlitoBold;font-size:{TM_FONT}pt;text-align:center;'
        f'height:{TM_HEADER_H}pt;line-height:{TM_FONT}pt;'
        f'border:0.6pt solid #000">{esc(label)}</td>'
        for label, _ in fields
    )
    rows = []
    for idx, piece in enumerate(tier_pieces):
        areas = piece.get("protectedAreas") or [""]
        name = " / ".join(AREA_TITLES.get(a, a.upper()) for a in areas)
        fill = fills[idx % 2]
        cells = []
        for _, key in fields:
            value = esc(value_of(piece, key))
            cells.append(
                f'<td style="width:{col_w}pt;{TM_CELL_PAD};background:{fill};'
                f'font-family:CarlitoBold;font-size:{TM_FONT}pt;text-align:center;'
                f'height:{TM_ROW_H}pt;line-height:{TM_ROW_H}pt;'
                f'border:0.6pt solid #000">{value}</td>'
            )
        rows.append(
            f'<tr>'
            f'<td style="width:{label_w}pt;{TM_CELL_PAD};background:{fill};'
            f'font-family:CarlitoBold;font-size:{TM_FONT}pt;text-align:center;'
            f'height:{TM_ROW_H}pt;line-height:{TM_ROW_H}pt;'
            f'border:0.6pt solid #000">{esc(name)}</td>'
            + "".join(cells) +
            f'</tr>'
        )

    return (
        f'<div style="text-align:center;font-size:{TM_TITLE_SIZE}pt;'
        f'font-family:CarlitoBold;line-height:{TM_TITLE_SIZE}pt">'
        f'{esc(tier_title.upper())}</div>'
        f'<table style="border-collapse:collapse;border:0.6pt solid #000;'
        f'width:{table_w}pt;margin-top:{TM_TITLE_GAP}pt;margin-left:auto;'
        f'margin-right:auto">'
        f'<tr><td style="width:{label_w}pt;{TM_CELL_PAD};background:#000;color:#fff;'
        f'font-family:CarlitoBold;font-size:{TM_FONT}pt;text-align:center;'
        f'height:{TM_HEADER_H}pt;line-height:{TM_FONT}pt;'
        f'border:0.6pt solid #000"></td>{head_cells}</tr>'
        + "".join(rows) +
        f'</table>'
    )


def build_tiers_html(set_data: dict, tier_titles: dict) -> str:
    """Матрицы всех тиров: стандартный — полноширинный, нестандартные
    (укреплённая, тяжёлая) — в ДВУХ столбцах рядом."""
    base_list = base_pieces(set_data)
    standard: tuple[str, list[dict]] | None = None
    others: list[tuple[str, list[dict]]] = []
    for key, tier in (set_data.get("tiers") or {}).items():
        pieces = list(tier.get("pieces", []))
        if not pieces:
            continue
        if key == "standard":
            standard = (key, pieces)
        else:
            others.append((key, pieces))

    out = []
    if standard:
        out.append(build_tier_matrix_html(
            base_list, standard[1], tier_titles.get(standard[0], standard[0]),
            absolute=True))
    if others:
        out.append(f'<div style="height:{TM_TIER_GAP}pt"></div>')
        pair = others[:2]          # укреплённая + тяжёлая — в 2 столбца
        half = (w.CONTENT_W - TM_BLOCK_GAP) / 2.0

        def tier_cell(key: str, pieces: list[dict]) -> str:
            return (
                f'<td style="width:{half}pt;border:none;vertical-align:top">'
                + build_tier_matrix_html(
                    base_list, pieces, tier_titles.get(key, key),
                    absolute=False)
                + "</td>"
            )

        out.append(
            '<table style="border:none"><tr>'
            + (tier_cell(pair[0][0], pair[0][1]) if pair else "")
            + f'<td style="width:{TM_BLOCK_GAP}pt;border:none"></td>'
            + (tier_cell(pair[1][0], pair[1][1]) if len(pair) > 1 else "")
            + "</tr></table>"
        )
        # если тиров больше двух — остальные подбрасываем под парой
        for key, pieces in others[2:]:
            out.append(f'<div style="height:{TM_TIER_GAP}pt"></div>')
            out.append(build_tier_matrix_html(
                base_list, pieces, tier_titles.get(key, key), absolute=False))
    return "".join(out)


def build_page_1_html(spec: dict, comp: Companion, set_data: dict,
                      resources: dict) -> str:
    title = spec.get("title") or comp.set_names.get(spec["set"], spec["set"])
    mods_html, mods_h = build_mods_html(comp, set_data)
    top_h = 841.0 - mods_h - 14.0  # место для номера страницы

    content = (
        build_header_html(title)
        + f'<div style="margin-top:22pt">'
        + build_two_column_html(spec, set_data, resources, comp)
        + '</div>'
        + build_intro_html(spec)
    )
    num = build_page_number_html(1)

    return (
        '<table class="sheet">'
        f'<tr><td style="vertical-align:top;height:{top_h}pt;'
        f'padding:0">{content}</td></tr>'
        f'<tr><td style="vertical-align:bottom;height:{mods_h}pt;'
        f'padding:0">{mods_html}</td></tr>'
        f'<tr><td style="vertical-align:bottom;height:14pt;'
        f'padding:0">{num}</td></tr>'
        '</table>'
    )


def build_page_2_html(spec: dict, comp: Companion, set_data: dict) -> str:
    # страница 2 — продолжение разворота: заголовок и черта НЕ рисуются
    tiers = build_tiers_html(set_data, spec.get("tier_titles") or {})
    num = build_page_number_html(2)
    return (
        '<table class="sheet">'
        f'<tr><td style="vertical-align:top;height:827pt;'
        f'padding:0"><div style="margin-left:{w.MARGIN_L}pt;'
        f'width:{w.CONTENT_W}pt;margin-top:{SPREAD_TOP}pt">{tiers}</div></td></tr>'
        f'<tr><td style="vertical-align:bottom;height:14pt;'
        f'padding:0">{num}</td></tr>'
        '</table>'
    )


# --- рендер ----------------------------------------------------------------
def render_page(spec: dict, comp: Companion, out_path: str, pages_dir: Path,
                repo: Path) -> None:
    collection = spec.get("collection", "armor")
    set_key = spec["set"]
    set_data = comp.power_armor[set_key] if collection == "powerArmor" else comp.armor[set_key]

    resources = prepare_resources(spec, pages_dir, repo)
    css = build_css(resources["paper"])
    body = (
        build_page_1_html(spec, comp, set_data, resources)
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

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    w.register_fonts()  # weapon2pdf.mods_block использует шрифт Carlito
    total_pages = 0
    for spec in specs:
        render_page(spec, comp, str(out), pages_dir,
                    Path.cwd().resolve())
        total_pages += 2  # каждая страница брони: характеристики + тиры
    print(f"{out}  ({total_pages} страниц)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
