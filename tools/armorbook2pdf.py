#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
armorbook2pdf — книга брони, силовой брони и одежды в PDF.

Вёрстка снята с референса `docs/render/samples/armor-leather-book.pdf`
(2 страницы A4 на сет, все координаты ниже — замеры из этого PDF через
PyMuPDF: get_drawings() для линий/заливок, get_text("dict") для кеглей):

  страница 1 «<НАЗВАНИЕ СЕТА>»
    - заголовок 22 pt Bold по центру + линейка 385.94×2.2 pt;
    - справа «СТАНДАРТНЫЙ КОМПЛЕКТ» (10 pt Bold + линейка);
    - сетка характерист. таблиц 2×2: верхний ряд — ШЛЕМ (слева) /
      НАГРУДНИК (справа), нижний — НАРУЧ (слева) / ПОНОЖ (справа).
      Шаг строки 23.3 pt, метка — белый текст на чёрном, значение —
      кремовое (#FFEBCD). Если детали зоны в данных нет — её ячейка
      пустая и подпись не печатается;
    - описание (12 pt / 17.4 pt, по ширине) — один абзац; место под
      второй абзац остаётся свободным, чтобы вписать руками;
    - «ПОДДЕРЖИВАЕМЫЕ МОДИФИКАЦИИ» (18 pt Bold) + сетка модов:
      строки = зоны, шапки нет; 5 колонок; фон строк чередуется
      бежевый/оранжевый; последняя строка — «УНИКАЛЬНАЯ».

  страница 2 «ВАРИАНТЫ»
    - две матрицы тиров рядом (УКРЕПЛЁННАЯ, ТЯЖЁЛАЯ): шапка —
      названия деталей (белый на чёрном), строки — характеристики;
      если тира в данных нет — матрица не печатается;
    - «УНИКАЛЬНЫЕ МОДИФИКАЦИИ / <СЕТ>» (22 pt Bold, две строки) +
      таблица: название, ФИЗ./ЭНРГ./РАД. СУ, ВЕС, ЦЕНА, ПЕРКИ, ЭФФЕКТЫ.
      Шапка таблицы — белый на чёрном, значения — +1 / +10 / БРОННИК 1
      из statModifiers / weightModifier / costModifier / requiredPerk;
      эффект — русское описание из i18n; строки чередуют цвет.

Данные — Fallout 2d20 Companion (`data/companion`), оформление — Carlito
(метрический клон Calibri) и бумажная текстура `assets/pdf/paper.jpg`.

Правила, которых нет в референсе, но которые нужны для всех сетов:
  * нет детали зоны (например, шлема у кожаной брони) — нет ни подписи,
    ни таблицы, ни строки в сетке модов, ни колонки в матрицах тиров;
  * только один тир (например, «Броня охранника Волт-Тек») — вторая
    страница печатается только ради уникальных модов, без матриц;
  * нет уникальных модов — таблица уникальных модов не печатается;
  * картинки в данных Companion нет — вместо неё остаётся пустое место,
    чтобы вставить иллюстрацию в PDF-редакторе (файл ищется по адресу
    `assets/armor/<slug>.png`, если он есть — печатается он).

Пример:
    python3 tools/armorbook2pdf.py --out docs/render/samples/armor-book.pdf
    python3 tools/armorbook2pdf.py --only leatherArmor --out /tmp/leather.pdf
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from reportlab.lib.colors import Color
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import weapon2pdf as w  # noqa: E402  (шрифты, бумага, измерение текста)

FONT_DIR = str(ROOT / "assets" / "fonts")
PAGE_W, PAGE_H = A4  # 595.2756 × 841.8898

# --------------------------------------------------------------------------
# палитра и шрифты
# --------------------------------------------------------------------------

BEIGE = w.BEIGE            # #FFEBCD — кремовые значения
ORANGE = w.ORANGE          # #FFC674 — оранжевые строки
BLACK = w.BLACK
WHITE = w.WHITE
RULE_W_PT = 0.6

FONT = "Carlito"
FONT_B = "Carlito-Bold"

# --------------------------------------------------------------------------
# геометрия — всё замерено по docs/render/samples/armor-leather-book.pdf
# (y считается от верхнего края листа, как в weapon2pdf)
# --------------------------------------------------------------------------

MARGIN_L = 48.0
CONTENT_R = 547.2
CONTENT_W = CONTENT_R - MARGIN_L          # 499.2

# заголовок страницы
TITLE_TOP = 59.80
TITLE_SIZE = 22.0
TITLE_RULE_TOP = 90.43
TITLE_RULE_W = 385.94
TITLE_RULE_H = 2.2

# «СТАНДАРТНЫЙ КОМПЛЕКТ» / подписи тиров
SECTION_SIZE = 10.0
SECTION_RULE_H = 0.6
SECTION_RULE_PAD = 16.5
SECTION_RULE_MIN = 124.7
SECTION_RULE_GAP = 2.8

# сетка характерист. таблиц (страница 1) — абсолютные tops из референса:
#   подписи ШЛЕМ/НАГРУДНИК — 152.13 (12 pt), НАРУЧ/ПОНОЖ — 313.43 (14 pt);
#   таблицы начинаются на 167.33 и 330.80, шаг строки 23.3 pt (6 строк).
CHAR_LABEL_TOP_UPPER = 152.13
CHAR_LABEL_TOP_LOWER = 313.43
CHAR_TABLE_TOP_UPPER = 167.33
CHAR_TABLE_TOP_LOWER = 330.80
CHAR_ROW_H = 23.30           # высота строки таблицы (= шаг в референсе)
CHAR_ROW_GAP = 6.30          # между верхним и нижним рядом таблиц
CHAR_LABEL_SIZE = 11.0
CHAR_PIECE_SIZE_TOP = 12.0   # ШЛЕМ / НАГРУДНИК
CHAR_PIECE_SIZE_BOT = 14.0   # НАРУЧ / ПОНОЖ
CHAR_LEFT_LABEL_W = 79.6
CHAR_LEFT_VALUE_W = 39.6
CHAR_RIGHT_LABEL_W = 75.0
CHAR_RIGHT_VALUE_W = 35.0
CHAR_LEFT_X = 327.80
CHAR_RIGHT_X = 448.13
CHAR_COL_GAP = 14.3
CHAR_SECTION_TOP = 116.63    # «СТАНДАРТНЫЙ КОМПЛЕКТ»

# описание
DESC_TOP = 504.60
DESC_SIZE = 12.0
DESC_LEADING = 17.4
DESC_INDENT = 3.0

# место под иллюстрацию сета: слева от таблиц, от подписи до описания.
# Картинки в данных Companion нет — если файла `assets/armor/<slug>.png`
# тоже нет, место остаётся пустым (как в референсе) и его можно занять
# в PDF-редакторе. Границы — для справки и для тестов.
IMAGE_BOX = (MARGIN_L, 140.0, CHAR_LEFT_X - 18.0, DESC_TOP - 30.0)

# «ПОДДЕРЖИВАЕМЫЕ МОДИФИКАЦИИ» и сетка модов (страница 1)
MODS_HEADING_TOP = 613.10
MODS_HEADING_SIZE = 18.0
MODS_GRID_TOP = 658.60       # там же, где сетка в референсе
MODS_GRID_BOTTOM = 794.20    # низ сетки в референсе: сетка прижата к низу
MODS_LABEL_MIN = 67.90                 # в референсе 48.0 → 115.9
MODS_LABEL_PAD = 12.0                  # слева + справа от подписи строки
MODS_LABEL_RIGHT_PAD = 8.0             # подпись прижата к правому краю ячейки
# ширины колонок в референсе: 78.79 / 67.50 / 88.10 / 102.09 / 94.90.
# В данных компаньона есть слова длиннее этих колонок («Звукоизолированная»
# 89.7 pt, «Сбалансированная» 80.7 pt), поэтому набор ширин масштабируется
# под свободное место с сохранением пропорций — как в armor_book_pdf.py.
MODS_COLS = (78.79, 67.50, 88.10, 102.09, 94.82)
MODS_FONT = 10.0
MODS_LINE_H = 12.1
MODS_ROW_PAD = 6.7
MODS_ROW_MIN = 30.7
# шаг строк в референсе (по горизонтальным линиям сетки)
MODS_ROW_H_BY_AREA = {
    "Head": 30.7,
    "Body": 43.1,
    "Hand": 30.7,
    "Leg": 30.9,
    "Unique": 30.9,
}

# матрицы тиров (страница 2)
TIER_LABEL_TOP = 122.83
TIER_GRID_TOP = 159.13
TIER_HEADER_H = 20.50
TIER_ROW_H = 18.70
TIER_FONT = 10.0
TIER_LABEL_PAD_L = 2.8
TIER_HEAD_PAD = 6.0
TIER_COL_GAP = 14.0
TIER_LEFT_X = 48.0
TIER_RIGHT_X = 331.69
TIER_LEFT_COLS = (54.20, 71.70, 42.50, 43.40)   # метка + НАГРУДНИК/НАРУЧ/ПОНОЖ
TIER_RIGHT_COLS = (56.20, 59.50, 40.70, 45.70)

# уникальные моды (страница 2)
UNIQ_HEADING_TOP = 339.73
UNIQ_HEADING_SIZE = 22.0
UNIQ_HEADING_LINE_H = 23.84
UNIQ_GRID_TOP = 397.10
UNIQ_HEADER_H = 22.30
UNIQ_ROW_MIN = 18.50
UNIQ_ROW_H = 30.60
UNIQ_FONT = 10.0
UNIQ_LINE_H = 12.1
UNIQ_PAD = 10.0
UNIQ_COLS = (107.0, 52.8, 50.5, 48.4, 30.3, 32.0, 63.4, 114.8)
UNIQ_HEADERS = ("", "ФИЗ. СУ", "ЭНРГ. СУ", "РАД. СУ", "ВЕС", "ЦЕНА",
                "ПЕРКИ", "ЭФФЕКТЫ")

# номер страницы
PAGE_NUMBER_TOP = 810.91
PAGE_NUMBER_SIZE = 9.96

# --------------------------------------------------------------------------
# подписи
# --------------------------------------------------------------------------

AREA_TITLES = {
    "Head": "ШЛЕМ",
    "Body": "НАГРУДНИК",
    "Hand": "НАРУЧ",
    "Leg": "ПОНОЖ",
}
# порядок зон в сетке модов (как в референсе)
MODS_AREA_ORDER = ("Body", "Hand", "Leg")
# позиции зон в сетке характерист. таблиц: (строка, столбец)
CHAR_GRID_POS = {"Head": (0, 0), "Body": (0, 1), "Hand": (1, 0), "Leg": (1, 1)}

STAT_FIELDS = (
    ("physicalDamageRating", "ФИЗ. СУ"),
    ("energyDamageRating", "ЭНРГ. СУ"),
    ("radiationDamageRating", "РАД. СУ"),
)
EXTRA_FIELDS = (("weight", "ВЕС"), ("cost", "ЦЕНА"), ("rarity", "РЕДКОСТЬ"))

TIER_TITLES = {
    "standard": "Стандартная",
    "sturdy": "Укреплённая",
    "heavy": "Тяжёлая",
}
AUTO_TITLES = {
    "armor": "Броня · Силовая броня · Одежда",
    "powerArmor": "Силовая броня",
    "clothes": "Одежда",
}


# --------------------------------------------------------------------------
# данные
# --------------------------------------------------------------------------


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def fmt_number(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value)


def fmt_signed(value: Any) -> str:
    """+1 / −2 / 0 — как в таблице уникальных модов референса."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, (int, float)):
        if value > 0:
            return f"+{fmt_number(value)}"
        if value < 0:
            return f"−{fmt_number(abs(value))}"
        return "0"
    return fmt_number(value)


def stat_fields(piece: dict) -> list[tuple[str, str]]:
    """Строки таблицы характеристик: «прочность» только у силовой брони."""
    rows = list(STAT_FIELDS)
    if piece.get("hp") is not None:
        rows.append(("hp", "ПРОЧНОСТЬ"))
    rows.extend(EXTRA_FIELDS)
    return rows


def area_of(piece: dict) -> str:
    areas = piece.get("protectedAreas") or []
    return areas[0] if areas else ""


@dataclass
class Book:
    """Данные Companion + русская локализация."""

    root: Path
    item_names: dict[str, str] = field(default_factory=dict)
    set_names: dict[str, str] = field(default_factory=dict)
    mod_names: dict[str, str] = field(default_factory=dict)
    mod_effects: dict[str, str] = field(default_factory=dict)
    armor: dict = field(default_factory=dict)
    power_armor: dict = field(default_factory=dict)
    clothes: dict = field(default_factory=dict)
    mods: list = field(default_factory=list)
    unique_mods: list = field(default_factory=list)
    clothes_titles: dict[int, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        eq = self.root / "equipment"
        self.armor = read_json(eq / "armor.json")
        self.power_armor = read_json(eq / "powerArmor.json")
        self.mods = read_json(eq / "armor_mods.json")
        self.unique_mods = read_json(eq / "uniq_armor_mods.json")
        clothes_path = eq / "clothes.json"
        self.clothes = read_json(clothes_path) if clothes_path.exists() else {"clothes": []}

        i18n = self.root / "i18n" / "ru-RU" / "data" / "equipment" / "armor"
        for filename in ("armor.json", "powerArmor.json", "clothes.json"):
            path = i18n / filename
            if not path.exists():
                continue
            data = read_json(path)
            if filename == "clothes.json":
                for index, group in enumerate(next(iter(data.values()))):
                    self.clothes_titles[index] = group.get("type", "")
            for group in next(iter(data.values())):
                key = group.get("categoryKey") or group.get("type")
                if group.get("categoryKey"):
                    self.set_names[key] = group.get("type", key)
                for item in group.get("items", []):
                    self.item_names[item["id"]] = item.get("name", item["id"])
                    # эффекты одежды описаны прямо в i18n предмета
                    for effect in item.get("specialEffects") or []:
                        text = effect.get("description")
                        if text:
                            self.mod_effects.setdefault(item["id"], text)

        for filename in ("armor_mods.json", "uniq_armor_mods.json"):
            path = i18n / filename
            if not path.exists():
                continue
            for mod in read_json(path):
                self.mod_names[mod["id"]] = mod.get("name", mod["id"])
                for effect in mod.get("specialEffects") or []:
                    text = effect.get("description")
                    if text:
                        self.mod_effects.setdefault(effect.get("id", mod["id"]), text)

        effects_path = i18n / "armor_effects.json"
        if effects_path.exists():
            for effect_id, effect in read_json(effects_path).items():
                if effect.get("description"):
                    self.mod_effects.setdefault(effect_id, effect["description"])

    # -- наборы ---------------------------------------------------------

    def clothes_group_title(self, index: int) -> str:
        """Русское название группы одежды (порядок совпадает с equipment)."""
        groups = self.clothes.get("clothes", [])
        if 0 <= index < len(groups):
            return self.clothes_titles.get(index, groups[index]["type"])
        return ""

    def piece_name(self, piece: dict) -> str:
        return self.item_names.get(piece["id"], piece.get("imageName", piece["id"]))

    def set_title(self, collection: str, key: str) -> str:
        name = self.set_names.get(key)
        if name:
            return name
        item = self.piece_names(collection, key)
        return item[0] if item else key

    def piece_names(self, collection: str, key: str) -> list[str]:
        return [self.piece_name(p) for p in self.tier_pieces(collection, key, "standard")]

    def tier_pieces(self, collection: str, key: str, tier: str = "standard") -> list[dict]:
        if collection == "clothes":
            if tier != "standard":
                return []
            for group in self.clothes.get("clothes", []):
                if group.get("type") == key:
                    return list(group.get("items", []))
            return []
        if collection == "powerArmor":
            if tier != "standard":
                return []
            return list((self.power_armor.get(key) or {}).get("pieces", []))
        return list(
            ((self.armor.get(key) or {}).get("tiers") or {})
            .get(tier, {})
            .get("pieces", [])
        )

    def tiers(self, collection: str, key: str) -> dict[str, list[dict]]:
        """{tier: pieces} в порядке standard → sturdy → heavy."""
        if collection != "armor":
            pieces = self.tier_pieces(collection, key)
            return {"standard": pieces} if pieces else {}
        data = (self.armor.get(key) or {}).get("tiers") or {}
        out: dict[str, list[dict]] = {}
        for tier in ("standard", "sturdy", "heavy"):
            pieces = list((data.get(tier) or {}).get("pieces", []))
            if pieces:
                out[tier] = pieces
        return out

    def allowed_mods(self, collection: str, key: str) -> tuple[list[str], list[str]]:
        if collection == "powerArmor":
            return [], []
        data = self.armor.get(key) or {}
        return (
            list(data.get("allowedModCategories") or []),
            list(data.get("allowedUniqueModCategories") or []),
        )

    def areas(self, collection: str, key: str) -> list[str]:
        """Зоны, которые реально есть в данных (шлема может не быть)."""
        seen: list[str] = []
        for pieces in self.tiers(collection, key).values():
            for piece in pieces:
                for area in piece.get("protectedAreas") or []:
                    if area not in seen:
                        seen.append(area)
        return seen

    def mods_for_area(self, area: str, allowed: list[str]) -> list[str]:
        names = []
        for mod in self.mods:
            if mod.get("modCategory") not in allowed:
                continue
            if area in (mod.get("protectedAreas") or []):
                names.append(self.mod_names.get(mod["id"], mod["id"]))
        return names

    def unique_mods_for(self, allowed: list[str]) -> list[dict]:
        return [m for m in self.unique_mods if m.get("modCategory") in allowed]


# --------------------------------------------------------------------------
# рисование
# --------------------------------------------------------------------------


def register_fonts() -> None:
    if "Carlito" in pdfmetrics.getRegisteredFontNames():
        return
    pdfmetrics.registerFont(TTFont(FONT, os.path.join(FONT_DIR, "Carlito-Regular.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_B, os.path.join(FONT_DIR, "Carlito-Bold.ttf")))
    pdfmetrics.registerFontFamily(
        FONT, normal=FONT, bold=FONT_B, italic=FONT, boldItalic=FONT_B
    )


def sw(text: str, font: str, size: float) -> float:
    return pdfmetrics.stringWidth(text, font, size)


def y_from_top(y_top: float) -> float:
    return PAGE_H - y_top


def draw_top(c, x, y_top, text, font, size, align="left", color=BLACK):
    """Одна строка: y_top — типографский верх строки (как в референсе)."""
    width = sw(text, font, size)
    if align == "center":
        x -= width / 2.0
    elif align == "right":
        x -= width
    c.setFillColor(color)
    c.setFont(font, size)
    c.drawString(x, y_from_top(y_top + w.ASCENT * size), text)
    return width


def vcenter_top(y0: float, y1: float, size: float, lines: int = 1,
                leading: float | None = None) -> float:
    """y_top так, чтобы блок из `lines` строк встал по центру [y0, y1]."""
    leading = size if leading is None else leading
    block_h = size + (lines - 1) * leading
    return y0 + (y1 - y0 - block_h) / 2.0 + 0.6


def wrap(text: str, font: str, size: float, width: float) -> list[str]:
    return w.wrap_text(text or "", font, size, width)


def draw_lines(c, x, y_top, lines, font, size, leading=None, align="left",
               color=BLACK, width=None):
    leading = size if leading is None else leading
    for i, line in enumerate(lines):
        if align == "center" and width is not None:
            draw_top(c, x + width / 2.0, y_top + i * leading, line, font, size,
                     align="center", color=color)
        elif align == "right" and width is not None:
            draw_top(c, x + width, y_top + i * leading, line, font, size,
                     align="right", color=color)
        else:
            draw_top(c, x, y_top + i * leading, line, font, size, color=color)


def rect(c, x0, y0, x1, y1, fill=None, stroke=None, line_w=RULE_W_PT):
    if fill is not None:
        c.setFillColor(fill)
        c.rect(x0, y_from_top(y1), x1 - x0, y1 - y0, stroke=0, fill=1)
    if stroke is not None:
        c.setStrokeColor(stroke)
        c.setLineWidth(line_w)
        c.rect(x0, y_from_top(y1), x1 - x0, y1 - y0, stroke=1, fill=0)


def draw_page_title(c, title: str) -> None:
    x0 = MARGIN_L + (CONTENT_W - TITLE_RULE_W) / 2.0
    draw_top(c, x0 + TITLE_RULE_W / 2.0, TITLE_TOP, title.upper(), FONT_B,
             TITLE_SIZE, align="center")
    rect(c, x0, TITLE_RULE_TOP, x0 + TITLE_RULE_W, TITLE_RULE_TOP + TITLE_RULE_H,
         fill=BLACK)


def draw_section_label(c, center_x: float, y_top: float, title: str) -> None:
    """Подпись 10 pt Bold + короткая линейка под ней (как «УКРЕПЛЁННАЯ»)."""
    title = title.upper()
    width = sw(title, FONT_B, SECTION_SIZE)
    draw_top(c, center_x, y_top, title, FONT_B, SECTION_SIZE, align="center")
    rule_w = max(width + SECTION_RULE_PAD, SECTION_RULE_MIN)
    rect(c, center_x - rule_w / 2.0, y_top + SECTION_SIZE + SECTION_RULE_GAP,
         center_x + rule_w / 2.0,
         y_top + SECTION_SIZE + SECTION_RULE_GAP + SECTION_RULE_H, fill=BLACK)


def draw_heading(c, title: str, y_top: float, size: float,
                 align: str = "center") -> None:
    title = title.upper()
    if align == "center":
        draw_top(c, MARGIN_L + CONTENT_W / 2.0, y_top, title, FONT_B, size,
                 align="center")
    else:
        draw_top(c, MARGIN_L, y_top, title, FONT_B, size)


def draw_page_number(c, number: int) -> None:
    text = str(number)
    if number % 2 == 0:
        draw_top(c, MARGIN_L + 2.57, PAGE_NUMBER_TOP, text, FONT, PAGE_NUMBER_SIZE)
    else:
        draw_top(c, CONTENT_R - 2.57, PAGE_NUMBER_TOP, text, FONT,
                 PAGE_NUMBER_SIZE, align="right")


# -- страница 1: таблицы характеристик --------------------------------------


CHAR_TABLE_W = {"left": CHAR_LEFT_LABEL_W + CHAR_LEFT_VALUE_W,
                "right": CHAR_RIGHT_LABEL_W + CHAR_RIGHT_VALUE_W}


def char_table(c, x: float, tops: list[float], piece: dict, side: str) -> None:
    """Таблица характеристик одной детали.

    Ширины колонок — замеренные в референсе (левая 79.6 + 39.6, правая
    75.0 + 35.0). tops — верх каждой строки: в референсе шаг 23.3 pt,
    для силовой брони с «ПРОЧНОСТЬЮ» шаг такой же, но строк на одну больше.
    """
    label_w = CHAR_LEFT_LABEL_W if side == "left" else CHAR_RIGHT_LABEL_W
    value_w = CHAR_LEFT_VALUE_W if side == "left" else CHAR_RIGHT_VALUE_W
    keys = stat_fields(piece)
    for top, (key, label) in zip(tops, keys):
        height = CHAR_ROW_H
        rect(c, x, top, x + label_w, top + height, fill=BLACK)
        rect(c, x + label_w, top, x + label_w + value_w, top + height, fill=BEIGE)
        rect(c, x, top, x + label_w + value_w, top + height, stroke=BLACK)
        mid = top + height / 2.0
        draw_top(c, x + 2.8, mid - CHAR_LABEL_SIZE / 2.0, label, FONT_B,
                 CHAR_LABEL_SIZE, color=WHITE)
        draw_top(c, x + label_w + value_w / 2.0, mid - CHAR_LABEL_SIZE / 2.0,
                 fmt_number(piece.get(key, 0)), FONT, CHAR_LABEL_SIZE,
                 align="center")


def char_row_tops(pieces: list[dict], table_top: float) -> list[float]:
    """Верх строк таблицы: столько строк, сколько характеристик у детали."""
    rows = max((len(stat_fields(p)) for p in pieces), default=6)
    return [table_top + i * CHAR_ROW_H for i in range(rows)]


def char_grid_geometry(pieces: list[dict]) -> dict:
    """Вертикальная раскладка сетки 2×2.

    В референсе (6 строк, шаг 23.3): верхние таблицы 167.33…307.13,
    подписи верхнего ряда 152.13, нижние таблицы 330.80…470.60, подписи
    313.43. У силовой брони 7 строк («ПРОЧНОСТЬ») — блок выше, поэтому
    нижний ряд сдвигается вниз, а всё вместе всё равно остаётся над
    описанием (DESC_TOP).
    """
    rows = max((len(stat_fields(p)) for p in pieces), default=6)
    block_h = rows * CHAR_ROW_H
    upper_top = CHAR_TABLE_TOP_UPPER
    upper_label = upper_top - CHAR_PIECE_SIZE_TOP - 2.2
    # подпись нижнего ряда стоит в зазоре над его таблицей и не залезает
    # на верхнюю таблицу: в референсе (6 строк) это 313.43 и 330.80
    lower_label = upper_top + block_h + CHAR_ROW_GAP
    lower_top = lower_label + CHAR_PIECE_SIZE_BOT + 3.37
    return {
        "tops": [upper_top + i * CHAR_ROW_H for i in range(rows)],
        "upper_top": upper_top,
        "upper_label": upper_label,
        "lower_top": lower_top,
        "lower_label": lower_label,
        "bottom": lower_top + block_h,
        "_rows": rows,
    }


def fit_size(text: str, font: str, size: float, width: float,
             min_size: float = 7.0) -> float:
    """Уменьшить кегль, чтобы строка влезла в width (но не ниже min_size)."""
    while size > min_size and sw(text, font, size) > width:
        size -= 0.25
    return size


def char_grid_slots(pieces: list[dict]) -> list[tuple[str, dict]]:
    """Какая деталь в какой ячейке 2×2.

    Деталь, закрывающая несколько зон сразу (каркас силовой брони —
    все четыре, комбинезон — тело/руки/ноги), печатается один раз:
    в ячейке первой по порядку зоны, остальные ячейки не занимает.
    """
    slots: dict[tuple[int, int], dict] = {}
    used: set[str] = set()
    for piece in pieces:
        if piece["id"] in used:
            continue
        for area, position in CHAR_GRID_POS.items():
            if area in (piece.get("protectedAreas") or []) and position not in slots:
                slots[position] = piece
                used.add(piece["id"])
                break
    return [(area, slots[position]) for area, position in CHAR_GRID_POS.items()
            if position in slots]


def draw_char_grid(c, pieces: list[dict]) -> dict:
    """Сетка 2×2: ШЛЕМ / НАГРУДНИК сверху, НАРУЧ / ПОНОЖ снизу.

    Зоны, которой нет в данных (например, шлема у кожаной брони), просто
    нет: ни подписи, ни таблицы.
    """
    geometry = char_grid_geometry(pieces)
    for area, piece in char_grid_slots(pieces):
        row, col = CHAR_GRID_POS[area]
        side = "left" if col == 0 else "right"
        x = CHAR_LEFT_X if side == "left" else CHAR_RIGHT_X
        table_top = geometry["upper_top"] if row == 0 else geometry["lower_top"]
        label_top = geometry["upper_label"] if row == 0 else geometry["lower_label"]
        size = CHAR_PIECE_SIZE_TOP if row == 0 else CHAR_PIECE_SIZE_BOT
        title = area_title(piece)
        size = fit_size(title, FONT_B, size, CHAR_TABLE_W[side])
        draw_top(c, x + CHAR_TABLE_W[side] / 2.0, label_top, title, FONT_B,
                 size, align="center")
        tops = [top + (table_top - geometry["upper_top"])
                for top in geometry["tops"]]
        char_table(c, x, tops, piece, side)
    return geometry


def area_title(piece: dict) -> str:
    return " / ".join(AREA_TITLES.get(a, a.upper())
                      for a in piece.get("protectedAreas") or []) or "ДЕТАЛЬ"


# -- страница 1: описание ---------------------------------------------------


LOREM_MARKERS = (
    "lorem ipsum", "dolor sit amet", "consectetur", "eiusmod", "ullamco",
    "reprehenderit", "cupidatat", "occaecat", "deserunt mollit",
)


def is_placeholder(text: str) -> bool:
    """Текст-заглушка (lorem ipsum) не печатается: место остаётся пустым."""
    lowered = text.lower()
    return any(marker in lowered for marker in LOREM_MARKERS)


def description_lines(paragraphs: Iterable[str]) -> list[str]:
    lines: list[str] = []
    for paragraph in paragraphs:
        if not paragraph or is_placeholder(paragraph):
            continue
        wrapped = wrap(paragraph, FONT, DESC_SIZE, CONTENT_W - 2 * DESC_INDENT)
        if lines:
            lines.append("")
        lines.extend(wrapped)
    return lines


def draw_description(c, paragraphs: Iterable[str], top: float = DESC_TOP,
                     max_bottom: float | None = None) -> None:
    """Описание под таблицами: 12 pt / 17.4 pt, выключка по ширине.

    max_bottom — граница, ниже которой текст не печатается (там уже
    заголовок модов или сетка), чтобы описания разной длины не наезжали.
    """
    lines = description_lines(paragraphs)
    if max_bottom is not None:
        # последняя строка кончается на top+(n-1)*leading+size и не должна
        # заходить за max_bottom (там заголовок модов или сетка)
        room = int((max_bottom - top - DESC_SIZE) // DESC_LEADING) + 1
        lines = fit_lines(lines, CONTENT_W - 2 * DESC_INDENT, DESC_SIZE,
                          max(0, room))
    if not lines:
        return
    c.setFillColor(BLACK)
    c.setFont(FONT, DESC_SIZE)
    for i, line in enumerate(lines):
        baseline = y_from_top(top + w.ASCENT * DESC_SIZE + i * DESC_LEADING)
        if not line:
            continue
        if i == len(lines) - 1:
            c.drawString(MARGIN_L + DESC_INDENT, baseline, line)
            continue
        words = line.split()
        if len(words) == 1:
            c.drawString(MARGIN_L + DESC_INDENT, baseline, line)
            continue
        width = CONTENT_W - 2 * DESC_INDENT
        gap = (width - sum(sw(word, FONT, DESC_SIZE) for word in words)) / (
            len(words) - 1)
        cursor = MARGIN_L + DESC_INDENT
        for word in words:
            c.drawString(cursor, baseline, word)
            cursor += sw(word, FONT, DESC_SIZE) + gap


# -- страница 1: сетка модов ------------------------------------------------


# ---- одежда: таблица предметов вместо сетки модов --------------------

ITEM_TABLE_COLS = (188.0, 48.0, 48.0, 48.0, 52.0, 55.0, 60.2)  # = CONTENT_W
ITEM_TABLE_HEADERS = ("НАЗВАНИЕ", "ФИЗ. СУ", "ЭНРГ. СУ", "РАД. СУ",
                      "ВЕС", "ЦЕНА", "РЕДКОСТЬ")
ITEM_HEADER_H = 22.3
ITEM_ROW_H = 23.3
ITEM_FONT = 10.0
ITEM_NAME_PAD = 6.0


def item_effects(book: Book, item: dict) -> list[str]:
    """Описания эффектов предмета из i18n (у одежды они прямо в предмете)."""
    texts = []
    for effect in item.get("specialEffects") or []:
        text = book.mod_effects.get(item["id"]) or book.mod_effects.get(
            effect.get("id", ""))
        if text and text not in texts:
            texts.append(text)
    return texts


ITEM_TOP = MODS_GRID_TOP          # первая таблица начинается здесь
ITEM_BOTTOM = MODS_GRID_BOTTOM    # и не опускается ниже
ITEM_HEADING_SIZE = 18.0
ITEM_HEADING_GAP = 26.0
PAGE_SAFE_BOTTOM = 800.0          # ниже — только номер страницы


def items_table_height(count: int) -> float:
    return ITEM_HEADER_H + count * ITEM_ROW_H


def items_that_fit(top: float, bottom: float, effects_h: float = 0.0) -> int:
    room = bottom - top - ITEM_HEADER_H - effects_h
    return max(1, int(room // ITEM_ROW_H))


def draw_items_table(c, book: Book, items: list[dict], top: float) -> float:
    """Таблица предметов: шапка белым на чёрном, строки через цвет.

    Возвращает y низа таблицы.
    """
    edges = [MARGIN_L]
    for width in ITEM_TABLE_COLS:
        edges.append(edges[-1] + width)
    for i, header in enumerate(ITEM_TABLE_HEADERS):
        rect(c, edges[i], top, edges[i + 1], top + ITEM_HEADER_H, fill=BLACK)
        rect(c, edges[i], top, edges[i + 1], top + ITEM_HEADER_H, stroke=BLACK)
        draw_top(c, edges[i] + ITEM_TABLE_COLS[i] / 2.0,
                 vcenter_top(top, top + ITEM_HEADER_H, ITEM_FONT), header,
                 FONT_B, ITEM_FONT, align="center", color=WHITE)
    y = top + ITEM_HEADER_H
    for index, item in enumerate(items):
        fill = BEIGE if index % 2 == 0 else ORANGE
        values = [book.piece_name(item)] + [
            fmt_number(item.get(key, 0))
            for key in ("physicalDamageRating", "energyDamageRating",
                        "radiationDamageRating", "weight", "cost", "rarity")
        ]
        for i, value in enumerate(values):
            rect(c, edges[i], y, edges[i + 1], y + ITEM_ROW_H, fill=fill)
            rect(c, edges[i], y, edges[i + 1], y + ITEM_ROW_H, stroke=BLACK)
            if i == 0:
                draw_top(c, edges[0] + ITEM_NAME_PAD,
                         vcenter_top(y, y + ITEM_ROW_H, ITEM_FONT),
                         fit_text(value, FONT, ITEM_FONT,
                                  ITEM_TABLE_COLS[0] - 2 * ITEM_NAME_PAD),
                         FONT, ITEM_FONT)
            else:
                draw_top(c, edges[i] + ITEM_TABLE_COLS[i] / 2.0,
                         vcenter_top(y, y + ITEM_ROW_H, ITEM_FONT), value,
                         FONT, ITEM_FONT, align="center")
        y += ITEM_ROW_H
    return y


def fit_text(text: str, font: str, size: float, width: float) -> str:
    """Обрезать строку по ширине ячейки (с многоточием)."""
    if sw(text, font, size) <= width:
        return text
    cut = text
    while cut and sw(cut + "…", font, size) > width:
        cut = cut[:-1]
    return cut.rstrip() + "…"


def draw_effects(c, book: Book, items: list[dict], top: float) -> float:
    """Список эффектов предметов под таблицей (9 pt, по ширине строки)."""
    lines = effects_lines(book, items)
    if not lines:
        return top
    y = top + 10.0
    draw_top(c, MARGIN_L, y, "ЭФФЕКТЫ", FONT_B, 10.0)
    for i, line in enumerate(lines):
        draw_top(c, MARGIN_L, y + 14.0 + i * 11.0, line, FONT, 9.0)
    return y + 14.0 + len(lines) * 11.0


def mods_rows(book: Book, collection: str, key: str) -> list[tuple[str, list[str]]]:
    if collection == "clothes":
        return []
    allowed, allowed_uniq = book.allowed_mods(collection, key)
    areas = book.areas(collection, key)
    rows: list[tuple[str, list[str]]] = []
    for area in MODS_AREA_ORDER:
        if area not in areas:
            continue
        names = book.mods_for_area(area, allowed)
        if names:
            rows.append((AREA_TITLES[area], names))
    uniq = [book.mod_names.get(m["id"], m["id"])
            for m in book.unique_mods_for(allowed_uniq)]
    if uniq:
        rows.append(("УНИКАЛЬНАЯ", uniq))
    return rows


def cell_lines(text: str, width: float, size: float) -> list[str]:
    """Перенос текста по словам; слово шире ячейки режется по символам.

    Так в референсе «Звукоизолированная» разбивается на две строки, а не
    вылезает в соседнюю ячейку.
    """
    lines: list[str] = []
    current = ""
    for word in (text or "").split():
        candidate = word if not current else current + " " + word
        if sw(candidate, FONT, size) <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
        if sw(word, FONT, size) <= width:
            current = word
            continue
        piece = ""
        for ch in word:
            if piece and sw(piece + ch, FONT, size) > width:
                lines.append(piece)
                piece = ch
            else:
                piece += ch
        current = piece
    if current:
        lines.append(current)
    return lines or [""]


def fit_lines(lines: list[str], width: float, size: float,
              max_lines: int) -> list[str]:
    """Ужать текст до max_lines строк (лишнее отбрасывается)."""
    if len(lines) <= max_lines:
        return lines
    kept = lines[:max_lines]
    last = kept[-1]
    while last and sw(last + "…", FONT, size) > width:
        last = last[:-1]
    kept[-1] = last + "…"
    return kept


def mods_label_width(rows: list[tuple[str, list[str]]]) -> float:
    """Ширина колонки подписей: по самой длинной подписи, но не уже референса
    и не шире трети строки (иначе под колонки модов не остаётся места)."""
    needed = max((sw(label, FONT_B, MODS_FONT) for label, _ in rows), default=0.0)
    return min(CONTENT_W / 3.0, max(MODS_LABEL_MIN, needed + MODS_LABEL_PAD))


def mods_col_widths(label_w: float) -> list[float]:
    """Ширины колонок модов, отмасштабированные до свободного места."""
    available = CONTENT_W - label_w
    total = sum(MODS_COLS)
    return [width * available / total for width in MODS_COLS]


def draw_mods_grid(c, rows: list[tuple[str, list[str]]],
                   top_limit: float = MODS_GRID_TOP,
                   bottom: float = MODS_GRID_BOTTOM) -> tuple[float, float]:
    """Сетка модификаций: строки = зоны (+ «УНИКАЛЬНАЯ»), 5 колонок.

    Как в референсе, сетка прижата к низу листа: сначала считаем высоты
    строк по содержимому, потом рисуем от MODS_GRID_BOTTOM вверх.
    Возвращает (верх, низ) сетки.
    """
    if not rows:
        return 0.0, 0.0
    label_w = mods_label_width(rows)
    col_widths = mods_col_widths(label_w)

    prepared = []
    for label, names in rows:
        wrapped = [cell_lines(name, width, MODS_FONT)
                   for name, width in zip(names, col_widths)]
        height = max(
            MODS_ROW_H_BY_AREA.get(label, MODS_ROW_MIN),
            max((len(lines) for lines in wrapped), default=1) * MODS_LINE_H
            + MODS_ROW_PAD,
        )
        prepared.append((label, wrapped, height))

    total_h = sum(item[2] for item in prepared)
    top = min(top_limit, bottom - total_h)
    if top < top_limit:
        # сетка не влезает между заголовком и низом — жмём строки
        scale = (bottom - top_limit) / total_h
        prepared = [(label, wrapped, height * scale)
                    for label, wrapped, height in prepared]
        top = top_limit
    y = top

    for index, (label, wrapped, height) in enumerate(prepared):
        fill = BEIGE if index % 2 == 0 else ORANGE
        x_label = MARGIN_L
        x_cells = x_label + label_w
        rect(c, x_label, y, x_cells, y + height, fill=BLACK)
        rect(c, x_label, y, x_cells, y + height, stroke=BLACK)
        draw_top(c, x_cells - MODS_LABEL_RIGHT_PAD,
                 vcenter_top(y, y + height, MODS_FONT), label, FONT_B, MODS_FONT,
                 align="right", color=WHITE)
        x = x_cells
        for col, width in enumerate(col_widths):
            x1 = x + width
            rect(c, x, y, x1, y + height, fill=fill)
            rect(c, x, y, x1, y + height, stroke=BLACK)
            if col < len(wrapped):
                lines = wrapped[col]
                block_h = MODS_FONT + (len(lines) - 1) * MODS_LINE_H
                start = y + (height - block_h) / 2.0 + 0.6
                draw_lines(c, x, start, lines, FONT, MODS_FONT,
                           leading=MODS_LINE_H, align="center", width=width)
            x = x1
        y += height
    return y - sum(item[2] for item in prepared), y


# -- страница 2: матрицы тиров ----------------------------------------------


# колонки матриц тиров по референсу: (метка, НАГРУДНИК, НАРУЧ, ПОНОЖ)
TIER_COL_SETS = {
    "left": (54.20, 71.70, 42.50, 43.40),
    "right": (56.20, 59.50, 40.70, 45.70),
}
TIER_AREA_ORDER = ("Body", "Hand", "Leg", "Head")


def tier_columns(widths: tuple[float, ...], count: int) -> list[float]:
    """Ширины колонок под count деталей.

    В референсе 3 колонки значений (шлема нет). Если деталей столько же —
    берём ширины один-в-один; иначе масштабируем набор до нужного числа.
    """
    label_w, values = widths[0], list(widths[1:])
    if count == len(values):
        return [label_w] + values
    if count <= len(values):
        # лишние ширины отдаём последней колонке, чтобы сетка не сжималась
        kept = values[:count - 1]
        last = sum(values[count - 1:]) if count else 0.0
        return [label_w] + kept + ([last] if count > 1 else [])
    extra = values[-1]
    return [label_w] + values + [extra] * (count - len(values))


def tier_matrix(c, x: float, y_top: float, pieces: list[dict],
                widths: tuple[float, ...], side: str = "left") -> float:
    """Матрица тира: шапка — названия деталей (белый на чёрном),
    строки — характеристики (метка белым на чёрном, значение кремовое).
    Возвращает y низа матрицы."""
    order = {area: i for i, area in enumerate(TIER_AREA_ORDER)}
    pieces = sorted(pieces, key=lambda p: order.get(area_of(p), 99))
    cols = tier_columns(widths, len(pieces))
    label_w, col_widths = cols[0], cols[1:]
    total_w = sum(cols)

    rect(c, x, y_top, x + total_w, y_top + TIER_HEADER_H, fill=BLACK)
    rect(c, x, y_top, x + total_w, y_top + TIER_HEADER_H, stroke=BLACK)
    cx = x + label_w
    for piece, width in zip(pieces, col_widths):
        rect(c, cx, y_top, cx + width, y_top + TIER_HEADER_H, stroke=BLACK)
        draw_top(c, cx + width / 2.0,
                 vcenter_top(y_top, y_top + TIER_HEADER_H, TIER_FONT),
                 area_title(piece), FONT_B, TIER_FONT, align="center",
                 color=WHITE)
        cx += width

    rows = stat_fields(pieces[0]) if pieces else []
    y = y_top + TIER_HEADER_H
    for key, label in rows:
        rect(c, x, y, x + label_w, y + TIER_ROW_H, fill=BLACK)
        rect(c, x, y, x + total_w, y + TIER_ROW_H, stroke=BLACK)
        draw_top(c, x + TIER_LABEL_PAD_L,
                 vcenter_top(y, y + TIER_ROW_H, TIER_FONT), label, FONT_B,
                 TIER_FONT, color=WHITE)
        cx = x + label_w
        for piece, width in zip(pieces, col_widths):
            rect(c, cx, y, cx + width, y + TIER_ROW_H, fill=BEIGE)
            rect(c, cx, y, cx + width, y + TIER_ROW_H, stroke=BLACK)
            draw_top(c, cx + width / 2.0,
                     vcenter_top(y, y + TIER_ROW_H, TIER_FONT),
                     fmt_number(piece.get(key, 0)), FONT, TIER_FONT,
                     align="center")
            cx += width
        y += TIER_ROW_H
    return y


def draw_tiers(c, tiers: dict[str, list[dict]]) -> float:
    """Матрицы тиров рядом: УКРЕПЛЁННАЯ и ТЯЖЁЛАЯ.

    Тиров может быть меньше (у «Брони охранника Волт-Тек» только
    стандартный) — тогда матрицы нет вовсе. Возвращает самый низ сетки.
    """
    extra = [(k, v) for k, v in tiers.items() if k != "standard" and v]
    if not extra:
        return 0.0
    cells = [(TIER_LEFT_X, TIER_COL_SETS["left"]),
             (TIER_RIGHT_X, TIER_COL_SETS["right"])]
    bottom = 0.0
    for (tier, pieces), (x, widths) in zip(extra, cells):
        label = TIER_TITLES.get(tier, tier)
        matrix_w = sum(tier_columns(widths, len(pieces)))
        draw_section_label(c, x + matrix_w / 2.0, TIER_LABEL_TOP, label)
        bottom = max(bottom, tier_matrix(c, x, TIER_GRID_TOP, pieces, widths))
    return bottom


# -- страница 2: уникальные моды --------------------------------------------


def mod_stat_text(mod: dict, key: str) -> str:
    modifier = (mod.get("statModifiers") or {}).get(key) or {}
    value = modifier.get("value", 0)
    op = modifier.get("op", "+")
    if op not in ("+", "-"):
        return fmt_number(value)
    return fmt_signed(value)


def mod_offset_text(mod: dict, key: str) -> str:
    modifier = mod.get(key) or {}
    value = modifier.get("value", 0)
    return fmt_signed(value)


def mod_effect_text(book: Book, mod: dict) -> str:
    texts = []
    for effect in mod.get("specialEffects") or []:
        text = book.mod_effects.get(effect.get("id"))
        if text and text not in texts:
            texts.append(text)
    return "; ".join(texts)


def unique_mods_table(c, book: Book, mods: list[dict], y_top: float) -> float:
    """Таблица уникальных модов; возвращает y низа таблицы."""
    x0 = MARGIN_L
    edges = [x0]
    for width in UNIQ_COLS:
        edges.append(edges[-1] + width)
    total_w = edges[-1]
    c.setStrokeColor(BLACK)
    c.setLineWidth(RULE_W_PT)

    # шапка
    for i in range(len(UNIQ_COLS)):
        rect(c, edges[i], y_top, edges[i + 1], y_top + UNIQ_HEADER_H, fill=BLACK)
        rect(c, edges[i], y_top, edges[i + 1], y_top + UNIQ_HEADER_H, stroke=BLACK)
        header = UNIQ_HEADERS[i]
        if header:
            draw_top(c, edges[i] + UNIQ_COLS[i] / 2.0,
                     vcenter_top(y_top, y_top + UNIQ_HEADER_H, UNIQ_FONT),
                     header, FONT_B, UNIQ_FONT, align="center", color=WHITE)
    y = y_top + UNIQ_HEADER_H

    for index, mod in enumerate(mods):
        fill = BEIGE if index % 2 == 0 else ORANGE
        name_lines = cell_lines(book.mod_names.get(mod["id"], mod["id"]).upper(),
                                UNIQ_COLS[0] - 2 * UNIQ_PAD, UNIQ_FONT)
        perk = (mod.get("requiredPerk") or "").upper()
        cells = [
            name_lines,
            [mod_stat_text(mod, "physicalDamageRating")],
            [mod_stat_text(mod, "energyDamageRating")],
            [mod_stat_text(mod, "radiationDamageRating")],
            [mod_offset_text(mod, "weightModifier")],
            [mod_offset_text(mod, "costModifier")],
            cell_lines(perk, UNIQ_COLS[6] - UNIQ_PAD, UNIQ_FONT) if perk else [""],
            cell_lines(mod_effect_text(book, mod), UNIQ_COLS[7] - UNIQ_PAD,
                       UNIQ_FONT),
        ]
        height = max(
            UNIQ_ROW_MIN,
            max(len(lines) for lines in cells) * UNIQ_LINE_H + UNIQ_PAD,
        )
        if y + height > PAGE_NUMBER_TOP - 20:
            height = max(UNIQ_ROW_MIN, PAGE_NUMBER_TOP - 20 - y)
        for i, lines in enumerate(cells):
            rect(c, edges[i], y, edges[i + 1], y + height, fill=fill)
            rect(c, edges[i], y, edges[i + 1], y + height, stroke=BLACK)
            if not lines or not "".join(lines):
                continue
            block_h = UNIQ_FONT + (len(lines) - 1) * UNIQ_LINE_H
            start = y + (height - block_h) / 2.0 + 0.6
            if i == 0:
                draw_lines(c, edges[0] + UNIQ_PAD, start, lines, FONT_B,
                           UNIQ_FONT, leading=UNIQ_LINE_H)
            elif i == 7:
                draw_lines(c, edges[7] + 4.0, start, lines, FONT, UNIQ_FONT,
                           leading=UNIQ_LINE_H)
            else:
                draw_lines(c, edges[i], start, lines, FONT, UNIQ_FONT,
                           leading=UNIQ_LINE_H, align="center",
                           width=UNIQ_COLS[i])
        y += height
    return y


# --------------------------------------------------------------------------
# сборка страниц
# --------------------------------------------------------------------------


@dataclass
class Spec:
    """Один сет в книге: что рисовать и чем подписать."""

    collection: str
    set: str
    title: str = ""
    intro: list[str] = field(default_factory=list)
    image: str = ""

    @property
    def slug(self) -> str:
        return self._slug or self.set

    _slug: str = ""


def spec_from_page_json(raw: dict) -> Spec:
    """Описание из `data/armor-pages/*.json` (тот же формат, что у armor2page)."""
    image = raw.get("image")
    if isinstance(image, dict):
        image = image.get("src", "")
    return Spec(
        collection=raw.get("collection", "armor"),
        set=raw.get("set", ""),
        title=raw.get("title", ""),
        intro=[p for p in (raw.get("intro") or []) if p],
        image=image or "",
        _slug=raw.get("slug", ""),
    )


def load_specs(pages_dir: Path) -> list[Spec]:
    """Описания сетов из `data/armor-pages/*.json`.

    Файл `book.json` — это конфиг самой книги (титул/подзаголовок), а не сет:
    он читается отдельно через load_config().
    """
    specs: list[Spec] = []
    if not pages_dir.exists():
        return specs
    for path in sorted(pages_dir.glob("*.json")):
        if path.stem == BOOK_CONFIG_STEM:
            continue
        specs.append(spec_from_page_json(read_json(path)))
    return specs


def load_config(pages_dir: Path) -> dict:
    path = pages_dir / f"{BOOK_CONFIG_STEM}.json"
    return read_json(path) if path.exists() else {}


BOOK_CONFIG_STEM = "book"


def auto_specs(book: Book, collection: str) -> list[Spec]:
    """Наборы, для которых нет описания в `data/armor-pages`."""
    if collection == "armor":
        keys = list(book.armor)
    elif collection == "powerArmor":
        keys = list(book.power_armor)
    else:
        specs = []
        for index, group in enumerate(book.clothes.get("clothes", [])):
            specs.append(Spec(collection=collection, set=group["type"],
                              title=book.clothes_group_title(index)))
        return specs
    return [Spec(collection=collection, set=key,
                 title=book.set_title(collection, key)) for key in keys]


def resolve_image(spec: Spec) -> str | None:
    for candidate in (spec.image, str(Path("assets") / "armor" / f"{spec.slug}.png")):
        if not candidate:
            continue
        path = Path(candidate)
        if not path.is_absolute():
            path = ROOT / path
        if path.exists():
            return str(path)
    return None


def draw_image(c, path: str) -> None:
    """Иллюстрация сета в свободном месте слева от таблиц (по пропорциям)."""
    x0, y0, x1, y1 = IMAGE_BOX
    reader = ImageReader(path)
    img_w, img_h = reader.getSize()
    scale = min((x1 - x0) / img_w, (y1 - y0) / img_h)
    width, height = img_w * scale, img_h * scale
    c.drawImage(reader, x0 + (x1 - x0 - width) / 2.0,
                y_from_top(y0 + (y1 - y0) / 2.0 + height / 2.0),
                width, height, mask="auto")


# -- страницы одного сета ---------------------------------------------------


def draw_first_page(c, book: Book, spec: Spec, title: str) -> list[dict]:
    """Первая страница сета. Возвращает предметы, не влезшие на страницу."""
    draw_page_title(c, title)
    pieces = book.tier_pieces(spec.collection, spec.set, "standard")
    grid_bottom = CHAR_TABLE_TOP_UPPER
    if pieces and spec.collection != "clothes":
        center = CHAR_RIGHT_X - CHAR_COL_GAP / 2.0
        draw_section_label(c, center, CHAR_SECTION_TOP, "Стандартный комплект")
        grid_bottom = draw_char_grid(c, pieces)["bottom"]
    image = resolve_image(spec)
    if image:
        draw_image(c, image)
    if spec.collection == "clothes":
        return draw_clothes_page(c, book, spec)

    # сетка модов прижата к низу листа, заголовок — над ней
    rows = mods_rows(book, spec.collection, spec.set)
    heading_top = MODS_HEADING_TOP
    if rows:
        mods_top, _ = draw_mods_grid(c, rows)
        heading_top = min(MODS_HEADING_TOP, mods_top - MODS_HEADING_SIZE - 26.0)
        draw_heading(c, "Поддерживаемые модификации", heading_top,
                     MODS_HEADING_SIZE)

    # описание занимает то, что осталось между таблицами и заголовком модов
    desc_top = max(DESC_TOP, grid_bottom + MODS_LINE_H * 2)
    if desc_top < heading_top:
        draw_description(c, spec.intro, top=desc_top,
                         max_bottom=heading_top - 12.0)
    return []


def effects_lines(book: Book, items: list[dict]) -> list[str]:
    lines: list[str] = []
    for item in items:
        for text in item_effects(book, item):
            lines.extend(wrap(f"{book.piece_name(item)} — {text}", FONT, 9.0,
                              CONTENT_W))
    return lines


def items_effects_height(book: Book, items: list[dict]) -> float:
    """Сколько места займёт блок «ЭФФЕКТЫ» под таблицей."""
    lines = effects_lines(book, items)
    return 24.0 + len(lines) * 11.0 if lines else 0.0


CLOTHES_TABLE_TOP = 180.0     # где начинается таблица предметов на стр. 1
CLOTHES_CONT_TOP = 150.0      # верх таблицы на страницах-продолжениях


def clothes_split(book: Book, items: list[dict], top: float,
                  bottom: float) -> tuple[list[dict], list[dict]]:
    """Сколько предметов влезает от top до bottom (с блоком эффектов)."""
    count = 0
    for i in range(1, len(items) + 1):
        used = items_table_height(i) + items_effects_height(book, items[:i])
        if top + used > bottom:
            break
        count = i
    if count == 0:
        # хотя бы одна строка; эффекты тогда уедут на продолжение
        count = max(1, int((bottom - top - ITEM_HEADER_H) // ITEM_ROW_H))
    return items[:count], items[count:]


def draw_clothes_page(c, book: Book, spec: Spec) -> list[dict]:
    """Страница одежды: описание (если есть) и таблица предметов группы.

    Таблица характеристик-сетки у одежды не печатается: все предметы
    группы видны в общей таблице со своими статами. Таблица идёт от
    заголовка вниз и обрывается на нижнем поле; остаток продолжается
    на следующих страницах с повторённой шапкой.
    """
    items = list(book.tier_pieces("clothes", spec.set))
    desc_top = CLOTHES_TABLE_TOP - 20.0
    draw_description(c, spec.intro, top=CLOTHES_TABLE_TOP - 20.0,
                     max_bottom=CLOTHES_TABLE_TOP - 20.0)
    draw_heading(c, "Предметы", CLOTHES_TABLE_TOP - ITEM_HEADING_GAP,
                 ITEM_HEADING_SIZE)
    first, rest = clothes_split(book, items, CLOTHES_TABLE_TOP, ITEM_BOTTOM)
    bottom = draw_items_table(c, book, first, CLOTHES_TABLE_TOP)
    draw_effects(c, book, first, bottom)
    return rest


def draw_clothes_continuation(c, book: Book, spec: Spec, title: str,
                              items: list[dict]) -> list[dict]:
    """Продолжение таблицы предметов (шапка повторяется)."""
    draw_page_title(c, f"{title} — продолжение")
    first, rest = clothes_split(book, items, CLOTHES_CONT_TOP, ITEM_BOTTOM)
    bottom = draw_items_table(c, book, first, CLOTHES_CONT_TOP)
    draw_effects(c, book, first, bottom)
    return rest


def second_page_parts(book: Book, spec: Spec) -> tuple[dict, list[dict]]:
    """Что печатать на второй странице: тиры без стандартного и уникальные моды."""
    if spec.collection == "clothes":
        return {}, []
    tiers = book.tiers(spec.collection, spec.set)
    _, allowed_uniq = book.allowed_mods(spec.collection, spec.set)
    return tiers, book.unique_mods_for(allowed_uniq)


def has_second_page(book: Book, spec: Spec) -> bool:
    tiers, uniq = second_page_parts(book, spec)
    return bool(uniq) or any(k != "standard" and v for k, v in tiers.items())


def draw_second_page(c, book: Book, spec: Spec, title: str) -> None:
    """Страница «ВАРИАНТЫ»: матрицы тиров и уникальные модификации."""
    tiers = book.tiers(spec.collection, spec.set)
    _, uniq = second_page_parts(book, spec)
    draw_page_title(c, "Варианты")
    tiers_bottom = draw_tiers(c, tiers)
    if uniq:
        # без матриц тиров блок уникальных модов поднимается выше
        heading_top = UNIQ_HEADING_TOP if tiers_bottom else TIER_LABEL_TOP
        grid_top = UNIQ_GRID_TOP if tiers_bottom else TIER_GRID_TOP + 20.0
        draw_heading(c, "Уникальные модификации", heading_top,
                     UNIQ_HEADING_SIZE)
        # вторая строка заголовка — название сета (как «КОЖАНАЯ БРОНЯ»)
        draw_top(c, MARGIN_L + CONTENT_W / 2.0,
                 heading_top + UNIQ_HEADING_LINE_H, title.upper(), FONT_B,
                 UNIQ_HEADING_SIZE, align="center")
        unique_mods_table(c, book, uniq, grid_top)


# -- титул и разделы --------------------------------------------------------


COLLECTION_TITLES = {
    "armor": ("БРОНЯ", "Стандартные комплекты, варианты и модификации."),
    "powerArmor": ("СИЛОВАЯ БРОНЯ",
                   "Каркас, рейдерская и все модели — Т-45, Т-51, Т-60, X-01."),
    "clothes": ("ОДЕЖДА", "Костюмы, обмундирование и головные уборы."),
}


def draw_cover(c, config: dict) -> None:
    title = (config.get("title") or "СПРАВОЧНИК БРОНИ").upper()
    subtitle = config.get("subtitle") or AUTO_TITLES["armor"]
    draw_top(c, PAGE_W / 2.0, 250.0, title, FONT_B, 34.0, align="center")
    x0 = PAGE_W / 2.0 - TITLE_RULE_W / 2.0
    rect(c, x0, 300.0, x0 + TITLE_RULE_W, 302.2, fill=BLACK)
    draw_top(c, PAGE_W / 2.0, 322.0, subtitle, FONT, 16.0, align="center")


def draw_section(c, title: str, subtitle: str) -> None:
    draw_top(c, PAGE_W / 2.0, 250.0, title.upper(), FONT_B, 30.0,
             align="center")
    x0 = PAGE_W / 2.0 - TITLE_RULE_W / 2.0
    rect(c, x0, 295.0, x0 + TITLE_RULE_W, 297.2, fill=BLACK)
    if subtitle:
        draw_top(c, PAGE_W / 2.0, 315.0, subtitle, FONT, 14.0, align="center")


def build_book(specs: list[Spec], book: Book, out_path: Path,
               config: dict | None = None, cover: bool = True,
               sections: bool = True) -> dict:
    """Собрать PDF. Возвращает статистику: страницы и состав по коллекциям."""
    config = config or {}
    register_fonts()
    c = canvas.Canvas(str(out_path), pagesize=(PAGE_W, PAGE_H))
    c.setTitle(config.get("title") or "Справочник брони")
    c.setAuthor(config.get("author") or "fallout-2d20.ru")
    c.setSubject(config.get("subtitle") or AUTO_TITLES["armor"])

    page = 1
    stats = {"pages": 0, "sets": 0, "skipped": []}
    have_cover = False
    current: str | None = None
    for spec in specs:
        title = spec.title or book.set_title(spec.collection, spec.set)
        if not title or not book.tiers(spec.collection, spec.set):
            stats["skipped"].append(f"{spec.collection}/{spec.set}")
            continue

        if sections and spec.collection != current:
            if cover and not have_cover:
                w.draw_paper(c)
                draw_cover(c, config)
                c.showPage()
                page += 1
                stats["pages"] += 1
                have_cover = True
            name, note = COLLECTION_TITLES.get(spec.collection,
                                               (spec.collection, ""))
            w.draw_paper(c)
            draw_section(c, name, note)
            draw_page_number(c, page)
            c.showPage()
            page += 1
            stats["pages"] += 1
            current = spec.collection

        if cover and not have_cover:
            w.draw_paper(c)
            draw_cover(c, config)
            c.showPage()
            page += 1
            stats["pages"] += 1
            have_cover = True

        w.draw_paper(c)
        rest = draw_first_page(c, book, spec, title)
        draw_page_number(c, page)
        c.showPage()
        page += 1
        stats["pages"] += 1

        # длинная таблица одежды продолжается, шапка повторяется
        while rest:
            w.draw_paper(c)
            rest = draw_clothes_continuation(c, book, spec, title, rest)
            draw_page_number(c, page)
            c.showPage()
            page += 1
            stats["pages"] += 1

        if has_second_page(book, spec):
            w.draw_paper(c)
            draw_second_page(c, book, spec, title)
            draw_page_number(c, page)
            c.showPage()
            page += 1
            stats["pages"] += 1
        stats["sets"] += 1
    c.save()
    return stats


# -- CLI --------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Книга брони/силовой брони/одежды в PDF "
                    "(вёрстка по docs/render/samples/armor-leather-book.pdf)",
    )
    ap.add_argument("--data", default=str(ROOT / "data" / "companion"),
                    help="каталог данных Companion")
    ap.add_argument("--pages", default=str(ROOT / "data" / "armor-pages"),
                    help="каталог описаний сетов (JSON)")
    ap.add_argument("--out", required=True, help="куда сохранить PDF")
    ap.add_argument("--config", help="JSON с титулом книги (title/subtitle)")
    ap.add_argument("--collection", action="append",
                    choices=list(COLLECTION_TITLES),
                    help="какие коллекции включить (по умолчанию все)")
    ap.add_argument("--set", action="append", dest="only", metavar="KEY",
                    help="только эти наборы (ключ данных)")
    ap.add_argument("--no-cover", action="store_true", help="без титула")
    ap.add_argument("--no-sections", action="store_true",
                    help="без разделителей коллекций")
    args = ap.parse_args(argv)

    book = Book(Path(args.data))
    collections = args.collection or list(COLLECTION_TITLES)

    described = load_specs(Path(args.pages))
    specs: list[Spec] = []
    for collection in collections:
        known = [s for s in described if s.collection == collection]
        unknown = {s.set for s in known}
        specs.extend(known)
        specs.extend(s for s in auto_specs(book, collection)
                     if s.set not in unknown)
    if args.only:
        wanted = set(args.only)
        specs = [s for s in specs if s.set in wanted or s.slug in wanted]
        missing = wanted - {s.set for s in specs} - {s.slug for s in specs}
        for key in sorted(missing):
            print(f"нет такого набора: {key}", file=sys.stderr)

    config = load_config(Path(args.pages))
    if args.config:
        config.update(read_json(Path(args.config)))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    stats = build_book(specs, book, out, config=config,
                       cover=not args.no_cover, sections=not args.no_sections)
    print(f"{out} — страниц: {stats['pages']}, наборов: {stats['sets']}")
    if stats["skipped"]:
        print("пропущены (нет данных): " + ", ".join(stats["skipped"]),
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
