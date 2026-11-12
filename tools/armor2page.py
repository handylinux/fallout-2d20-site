#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
armor2page — собрать страницу брони из данных Fallout 2d20 Companion.

Данные берутся из `modules/fallout/data/equipment` (+ русская локализация
`modules/fallout/i18n/ru-RU`).  Оформление — по образцу «Экскаваторной
силовой брони»: базовый комплект слева, вкладки и аккордеоны с таблицами.

Страница описывается отдельным JSON (см. `data/armor-pages/*.json`):
заголовок, ссылка «назад», картинка, вступление, подписи уровней, базовый
уровень для главного блока и список вкладок.  Скрипт подставляет в этот
каркас данные компаньона, поэтому менять нужно только JSON.

Пример:
    python3 tools/armor2page.py \
        --data data/companion \
        --pages data/armor-pages \
        --out pages/armor
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sppb2html import BASE_CSS, SCRIPT  # noqa: E402

# --------------------------------------------------------------------------
# словари оформления
# --------------------------------------------------------------------------

AREA_TITLES = {"Head": "ШЛЕМ", "Body": "НАГРУДНИК", "Hand": "НАРУЧ", "Leg": "ПОНОЖ"}
AREA_NAMES = {"Head": "Голова", "Body": "Тело", "Hand": "Руки", "Leg": "Ноги"}

STAT_FIELDS = (
    ("physicalDamageRating", "ФИЗ. СУ"),
    ("energyDamageRating", "ЭНРГ. СУ"),
    ("radiationDamageRating", "РАД. СУ"),
)
EXTRA_FIELDS = (("weight", "ВЕС"), ("cost", "ЦЕНА"), ("rarity", "РЕДКОСТЬ"))

SKILLS = {
    "REPAIR": "Ремонт",
    "SCIENCE": "Наука",
    "MEDICINE": "Медицина",
    "SNEAK": "Скрытность",
}

ARMOR_CSS = r"""
/* ---------- страница брони ---------- */
.armor-body{background:#fff}
.armor-page{padding:0 0 70px}
.armor-container{width:100%;max-width:1140px;margin:0 auto;padding:0 15px}

.armor-header{padding:75px 0 12px}
.armor-back{margin:0 0 12px}
.armor-back h4{margin:0;font-size:1.05rem;font-weight:600;line-height:1.3}
.armor-back a{color:#0b5cad}
.armor-title{margin:0;font-size:2rem;line-height:1.2}

.armor-lead{max-width:820px;padding-top:20px}
.armor-lead p{margin:0 0 1rem;line-height:1.65;color:#2b2b2b}
.armor-lead p:last-child{margin-bottom:0}

/* главный блок: базовый комплект слева, картинка справа */
.armor-hero{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:40px;align-items:start;padding:35px 0 10px}
.armor-hero--stats-left{grid-template-columns:minmax(0,1.35fr) minmax(0,1fr)}
.armor-hero-stats{min-width:0}
.armor-hero-media{min-width:0;margin:0}
.armor-hero-media img{display:block;width:100%;height:auto}
.armor-hero-title{margin:0 0 14px;font-size:1.25rem;line-height:1.2;text-transform:uppercase;color:#000}
.armor-hero-title::after{content:"";display:block;width:64px;height:4px;margin-top:8px;background:#e1b91e}

.armor-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}
.armor-cards--hero{grid-template-columns:repeat(2,minmax(0,1fr));padding:0}
.armor-card{min-width:0}
.armor-card-title{margin:0 0 3px;text-align:center;font-size:1.05rem;line-height:1.2;text-transform:uppercase;color:#000}
.armor-card-name{margin:0 0 9px;text-align:center;font-size:.76rem;line-height:1.3;color:#6c757d}
.armor-stat-table{width:100%;border:1px solid #000;border-collapse:collapse;table-layout:fixed;background:#ffebcd}
.armor-stat-table th{width:58%;padding:5px 7px;background:#000;color:#fff;border:1px solid #fff;text-align:left;font-size:.8rem;font-weight:600;line-height:1.25;text-transform:uppercase;letter-spacing:.01em}
.armor-stat-table td{padding:5px 7px;background:#ffebcd;border:1px solid #000;text-align:center;font-size:.88rem;font-weight:700;line-height:1.25}
.armor-cards--hero .armor-stat-table th{font-size:.72rem;padding:4px 6px}
.armor-cards--hero .armor-stat-table td{font-size:.83rem;padding:4px 6px}

/* ---------- вкладки ---------- */
.armor-tabs-section{padding:65px 0 0}
.armor-tabs-title{margin:0 0 22px;text-align:center;font-size:1.6rem;line-height:1.2;text-transform:uppercase;color:#e1b91e}
.armor-tab{margin-bottom:6px}
.armor-tab-heading{margin:0}
.armor-tab-toggle{display:flex;width:100%;align-items:center;justify-content:space-between;gap:12px;padding:10px 14px;background:#000;color:#fff;border:1px solid #bdbdbd;border-radius:5px;font:inherit;font-weight:700;text-transform:uppercase;font-size:.85rem;line-height:1.3;letter-spacing:.02em;text-align:left;cursor:pointer;transition:background-color .2s,color .2s}
.armor-tab-toggle::after{content:"+";flex:none;font-size:1.25em;line-height:1}
.armor-tab-toggle:hover{background:#3366ff;color:#fff}
.armor-tab.is-open .armor-tab-toggle{background:#f2c74b;color:#333;border-radius:5px 5px 0 0}
.armor-tab.is-open .armor-tab-toggle::after{content:"\2212"}
.armor-tab-panel{display:none;margin:0;padding:15px;background:#fff;box-shadow:0 0 12px #000;border-radius:0 0 5px 5px}
.armor-tab.is-open .armor-tab-panel{display:block}
.armor-tabs .sppb-accordion-item{background:#fff;border:1px solid rgba(0,0,0,.15);border-radius:4px;margin-bottom:5px}
.armor-tabs .sppb-accordion-title{font-size:1rem}
.armor-tabs .sppb-accordion-content{padding:0}

/* ---------- таблицы модификаций ---------- */
.armor-mods-table{width:100%;border-collapse:collapse;font-size:.86rem;line-height:1.4}
.armor-mods-table thead th{padding:7px 8px;background:#000;color:#fff;border:1px solid #000;text-align:center;font-weight:600;text-transform:uppercase;font-size:.72rem;letter-spacing:.02em}
.armor-mods-table tbody tr{background:#f8f1da}
.armor-mods-table td{padding:7px 8px;background:transparent;border:1px solid #000;text-align:center;vertical-align:middle}
.armor-mods-table td:first-child{font-weight:600}
.armor-mods-table .armor-mod-effect{text-align:left}

/* ---------- таблица «дельта от базового уровня» ---------- */
.armor-delta-table{width:100%;border-collapse:collapse;font-size:.88rem;line-height:1.35}
.armor-delta-table th,.armor-delta-table td{padding:8px 9px;border:1px solid #000;text-align:center;vertical-align:middle}
.armor-delta-table thead th{background:#000;color:#fff;font-size:.74rem;font-weight:600;text-transform:uppercase;letter-spacing:.02em}
.armor-delta-table tbody th{background:#f8f1da;text-align:left;font-weight:600;font-size:.78rem;text-transform:uppercase;color:#000}
.armor-delta-table td{background:#ffebcd;font-weight:700}
.armor-delta-table td.is-zero{color:#8a8a8a;font-weight:400}
.armor-delta-mobile{display:none}
.armor-delta-mobile-table{width:100%;border-collapse:collapse;font-size:.88rem;line-height:1.35}
.armor-delta-mobile-table th,.armor-delta-mobile-table td{padding:8px 9px;border:1px solid #000;text-align:center;vertical-align:middle}
.armor-delta-mobile-table thead th{background:#000;color:#fff;font-size:.74rem;font-weight:600;text-transform:uppercase;letter-spacing:.02em}
.armor-delta-mobile-table tbody th{background:#f8f1da;text-align:left;font-weight:600;font-size:.78rem;text-transform:uppercase;color:#000}
.armor-delta-mobile-table td{background:#ffebcd;font-weight:700}
.armor-delta-mobile-table td.is-zero{color:#8a8a8a;font-weight:400}

.armor-footer{margin-top:55px;text-align:center;font-size:.78rem;color:#adb5bd}

@media (max-width: 991.98px){
  .armor-hero{grid-template-columns:1fr;gap:25px}
  .armor-hero-media{order:1}
  .armor-hero-stats{order:2}
  .armor-cards{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media (max-width: 767.98px){
  /* модификации: из горизонтальной таблицы в вертикальную «категория → значение»,
     цвета ячеек те же, что на ПК (подписи — тёмные, значения — фон строки) */
  .armor-mods-table thead{display:none}
  .armor-mods-table,.armor-mods-table tbody,.armor-mods-table tr,.armor-mods-table td{display:block;width:100%}
  .armor-mods-table tr{border:1px solid #000;margin-bottom:10px}
  .armor-mods-table tr:last-child{margin-bottom:0}
  .armor-mods-table td{position:relative;padding:8px 9px 8px calc(42% + 9px);border:0;border-bottom:1px solid #000;background:transparent;text-align:left}
  .armor-mods-table td:last-child{border-bottom:0}
  .armor-mods-table td::before{content:attr(data-label);position:absolute;left:0;top:0;bottom:0;width:42%;display:flex;align-items:center;padding:8px 9px;background:#000;color:#fff;border-right:1px solid #000;font-size:.68rem;font-weight:700;line-height:1.2;text-transform:uppercase;letter-spacing:.02em}
  .armor-mods-table td:first-child{font-weight:700}
  .armor-mods-table .armor-mod-effect{text-align:left}

  /* «Категории»: одна деталь — одна таблица в две колонки */
  .armor-delta-desktop{display:none}
  .armor-delta-mobile{display:grid;gap:14px}
}
@media (max-width: 575.98px){
  .armor-header{padding:40px 0 10px}
  .armor-hero{padding-top:20px}
  .armor-lead{padding-top:14px}
}
@media (max-width: 420px){
  .armor-card-title{font-size:.92rem}
  .armor-card-name{font-size:.7rem}
  .armor-stat-table th{font-size:.66rem;padding:4px 5px}
  .armor-stat-table td{font-size:.78rem;padding:4px 5px}
}
"""


ARMOR_SCRIPT = r"""
(function () {
  "use strict";
  var tabs = Array.prototype.slice.call(document.querySelectorAll("[data-armor-tab]"));

  function setOpen(tab, open) {
    tab.classList.toggle("is-open", open);
    var button = tab.querySelector(".armor-tab-toggle");
    var panel = tab.querySelector(".armor-tab-panel");
    if (button) { button.setAttribute("aria-expanded", open ? "true" : "false"); }
    if (panel) { if (open) { panel.removeAttribute("hidden"); } else { panel.setAttribute("hidden", ""); } }
  }

  /* внутри вкладки открыт максимум один спойлер */
  function closeItem(item) {
    item.classList.remove("is-open");
    var button = item.querySelector(".sppb-accordion-toggle");
    if (button) { button.setAttribute("aria-expanded", "false"); }
    for (var i = 0; i < item.children.length; i++) {
      var child = item.children[i];
      if (child.classList && child.classList.contains("sppb-accordion-content")) {
        child.setAttribute("hidden", "");
      }
    }
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest(".armor-tab-panel .sppb-accordion-toggle");
    if (!button) { return; }
    var item = button.closest(".sppb-accordion-item");
    var accordion = item ? item.parentElement : null;
    if (!accordion) { return; }
    Array.prototype.forEach.call(accordion.children, function (other) {
      if (other !== item && other.classList && other.classList.contains("sppb-accordion-item")) {
        closeItem(other);
      }
    });
  }, true);

  tabs.forEach(function (tab) {
    var button = tab.querySelector(".armor-tab-toggle");
    if (!button) { return; }
    button.addEventListener("click", function () {
      setOpen(tab, !tab.classList.contains("is-open"));
    });
  });

  var hash = window.location.hash.slice(1);
  if (hash) {
    var panel = document.getElementById(hash);
    if (panel) {
      var tab = panel.closest("[data-armor-tab]");
      if (tab) {
        var button = tab.querySelector(".armor-tab-toggle");
        if (button) { button.click(); }
      }
    }
  }
})();
"""


# --------------------------------------------------------------------------
# данные компаньона
# --------------------------------------------------------------------------

def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def fmt_number(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value)


class Companion:
    """Данные снаряжения + русские названия из i18n."""

    def __init__(self, root: Path) -> None:
        self.root = root
        eq = root / "equipment"
        self.armor = read_json(eq / "armor.json")
        self.power_armor = read_json(eq / "powerArmor.json")
        self.mods = read_json(eq / "armor_mods.json")
        self.unique_mods = read_json(eq / "uniq_armor_mods.json")
        self.effects = read_json(eq / "armor_effects.json")

        i18n = root / "i18n" / "ru-RU" / "data" / "equipment" / "armor"
        self.item_names: dict[str, str] = {}
        self.set_names: dict[str, str] = {}
        for filename in ("armor.json", "powerArmor.json"):
            path = i18n / filename
            if not path.exists():
                continue
            data = read_json(path)
            for group in next(iter(data.values())):
                key = group.get("categoryKey") or group.get("type")
                self.set_names[key] = group.get("type", key)
                for item in group.get("items", []):
                    self.item_names[item["id"]] = item["name"]

        self.mod_names: dict[str, str] = {}
        self.mod_effects: dict[str, str] = {}
        for filename in ("armor_mods.json", "uniq_armor_mods.json"):
            for mod in read_json(i18n / filename):
                self.mod_names[mod["id"]] = mod.get("name", mod["id"])
                for effect in mod.get("specialEffects", []):
                    if effect.get("description"):
                        self.mod_effects[effect["id"]] = effect["description"]
        for effect_id, effect in read_json(i18n / "armor_effects.json").items():
            if effect.get("description"):
                self.mod_effects[effect_id] = effect["description"]

    # -- сеты -----------------------------------------------------------

    def set_areas(self, collection: str, set_key: str) -> list[str]:
        areas: list[str] = []
        for piece in self.set_pieces(collection, set_key):
            for area in piece.get("protectedAreas", []):
                if area not in areas:
                    areas.append(area)
        return areas

    def set_pieces(self, collection: str, set_key: str) -> list[dict]:
        if collection == "powerArmor":
            return list(self.power_armor[set_key].get("pieces", []))
        pieces: list[dict] = []
        for tier in self.armor[set_key].get("tiers", {}).values():
            pieces.extend(tier.get("pieces", []))
        return pieces

    def item_name(self, piece: dict) -> str:
        return self.item_names.get(piece["id"], piece.get("imageName", piece["id"]))


# --------------------------------------------------------------------------
# отрисовка
# --------------------------------------------------------------------------

def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def stat_fields(piece: dict) -> list[tuple[str, str]]:
    rows = [(label, key) for key, label in STAT_FIELDS]
    if piece.get("hp") is not None:
        rows.append(("ПРОЧНОСТЬ", "hp"))
    rows.extend((label, key) for key, label in EXTRA_FIELDS)
    return rows


def render_card(piece: dict, comp: Companion) -> str:
    rows = "".join(
        f'<tr><th scope="row">{esc(label)}</th><td>{esc(fmt_number(piece.get(key, 0)))}</td></tr>'
        for label, key in stat_fields(piece)
    )
    return (
        '<article class="armor-card">'
        f'<h3 class="armor-card-title">{esc(card_title(piece))}</h3>'
        f'<p class="armor-card-name">{esc(comp.item_name(piece))}</p>'
        f'<table class="armor-stat-table"><tbody>{rows}</tbody></table>'
        "</article>"
    )


def card_title(piece: dict) -> str:
    areas = piece.get("protectedAreas") or []
    return " / ".join(AREA_TITLES.get(area, area.upper()) for area in areas) or "ДЕТАЛЬ"


def area_key(piece: dict) -> tuple[str, ...]:
    return tuple(sorted(piece.get("protectedAreas", [])))


def fmt_delta(value: float | int) -> str:
    if value > 0:
        return f"+{fmt_number(value)}"
    if value < 0:
        return f"−{fmt_number(abs(value))}"
    return "0"


def delta_cell(base_by_area: dict, piece: dict, key: str) -> tuple[str, bool]:
    base = base_by_area.get(area_key(piece))
    if base is None or key not in piece or key not in base:
        return "—", True
    delta = piece[key] - base[key]
    return fmt_delta(delta), delta == 0


def render_delta_table(base_pieces: list[dict], pieces: list[dict]) -> str:
    base_by_area = {area_key(piece): piece for piece in base_pieces}
    fields = stat_fields(base_pieces[0] if base_pieces else {})

    head = "".join(f'<th scope="col">{esc(card_title(piece))}</th>' for piece in pieces)
    rows = []
    for label, key in fields:
        cells = []
        for piece in pieces:
            value, zero = delta_cell(base_by_area, piece, key)
            css = ' class="is-zero"' if zero else ""
            cells.append(f"<td{css}>{esc(value)}</td>")
        rows.append(f'<tr><th scope="row">{esc(label)}</th>{"".join(cells)}</tr>')
    matrix = (
        '<div class="sppb-table-wrap"><table class="sppb-table armor-delta-table">'
        f'<thead><tr><th scope="col">Характеристика</th>{head}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )

    # мобильная версия: каждая деталь — отдельная таблица в две колонки,
    # с теми же цветами, что и в матрице на ПК
    blocks = []
    for piece in pieces:
        body = []
        for label, key in fields:
            value, zero = delta_cell(base_by_area, piece, key)
            css = ' class="is-zero"' if zero else ""
            body.append(f'<tr><th scope="row">{esc(label)}</th><td{css}>{esc(value)}</td></tr>')
        blocks.append(
            '<section class="armor-delta-mobile-piece">'
            '<table class="armor-delta-mobile-table">'
            f'<thead><tr><th colspan="2">{esc(card_title(piece))}</th></tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table>'
            "</section>"
        )

    return (
        f'<div class="armor-delta-desktop">{matrix}</div>'
        f'<div class="armor-delta-mobile">{"".join(blocks)}</div>'
    )


def mod_effect(mod: dict, comp: Companion) -> str:
    parts: list[str] = []
    for key, label in STAT_FIELDS:
        change = (mod.get("statModifiers") or {}).get(key) or {}
        value = change.get("value")
        if not value:
            continue
        op = change.get("op", "+")
        if op == "set":
            parts.append(f"= {fmt_number(value)} к {label}")
        else:
            parts.append(f"{op}{fmt_number(value)} к {label}")
    for effect in mod.get("specialEffects", []):
        description = comp.mod_effects.get(effect.get("id"))
        if description:
            parts.append(description)
        elif effect.get("id"):
            parts.append(effect["id"])
    return "; ".join(parts) or "—"


def fmt_modifier(change: dict | None) -> str:
    if not change:
        return "—"
    value = change.get("value")
    if value in (None, 0, ""):
        return "—"
    op = change.get("op", "+")
    return f"{op}{fmt_number(value)}" if op in ("+", "-") else fmt_number(value)


def mod_areas(mod: dict, set_areas: list[str]) -> str:
    areas = [area for area in mod.get("protectedAreas", []) if area in set_areas]
    if not areas:
        areas = list(mod.get("protectedAreas", []))
    return ", ".join(AREA_NAMES.get(area, area) for area in areas) or "—"


def render_mod_table(mod: dict, comp: Companion, set_areas: list[str]) -> str:
    name = comp.mod_names.get(mod["id"], mod["id"])
    skill = SKILLS.get(mod.get("requiredSkill", ""), mod.get("requiredSkill") or "—")
    cells = [
        ("Модификация", name, ""),
        ("Эффект", mod_effect(mod, comp), ' class="armor-mod-effect"'),
        ("Часть брони", mod_areas(mod, set_areas), ""),
        ("Вес", fmt_modifier(mod.get("weightModifier")), ""),
        ("Цена", fmt_modifier(mod.get("costModifier")), ""),
        ("Перки", mod.get("requiredPerk") or "—", ""),
        ("Навык", skill, ""),
    ]
    row = "".join(
        f'<td data-label="{esc(label)}"{css}>{esc(value)}</td>'
        for label, value, css in cells
    )
    return (
        '<div class="sppb-table-wrap"><table class="sppb-table armor-mods-table">'
        "<thead><tr>"
        "<th>Модификация</th><th>Эффект</th><th>Часть брони</th>"
        "<th>Вес</th><th>Цена</th><th>Перки</th><th>Навык</th>"
        f"</tr></thead><tbody><tr>{row}</tr></tbody></table></div>"
    )


def render_accordion_item(mod: dict, comp: Companion, set_areas: list[str], page_id: str, index: int) -> str:
    name = comp.mod_names.get(mod["id"], mod["id"])
    content_id = f"acc-{page_id}-{index}"
    return (
        '<div class="sppb-accordion-item">'
        f'<h3 class="sppb-accordion-title"><button type="button" class="sppb-accordion-toggle" '
        f'aria-expanded="false" aria-controls="{esc(content_id)}">{esc(name)}</button></h3>'
        f'<div class="sppb-accordion-content" id="{esc(content_id)}" hidden>'
        f"{render_mod_table(mod, comp, set_areas)}"
        "</div></div>"
    )


def render_tier_accordion(title: str, base_pieces: list[dict], pieces: list[dict], page_id: str, index: int) -> str:
    content_id = f"acc-{page_id}-{index}"
    return (
        '<div class="sppb-accordion-item">'
        f'<h3 class="sppb-accordion-title"><button type="button" class="sppb-accordion-toggle" '
        f'aria-expanded="false" aria-controls="{esc(content_id)}">{esc(title)}</button></h3>'
        f'<div class="sppb-accordion-content" id="{esc(content_id)}" hidden>'
        f"{render_delta_table(base_pieces, pieces)}"
        "</div></div>"
    )


def mods_for_category(comp: Companion, category: str, set_areas: list[str]) -> list[dict]:
    mods = comp.unique_mods if category.endswith("UniqueMods") else comp.mods
    selected = []
    for mod in mods:
        if mod.get("modCategory") != category:
            continue
        if not set(mod.get("protectedAreas", [])) & set(set_areas):
            continue
        selected.append(mod)
    return selected


def render_hero(spec: dict, comp: Companion, set_data: dict, collection: str) -> str:
    hero = spec.get("hero") or {}
    tier_titles = spec.get("tier_titles") or spec.get("tiers") or {}

    if collection == "powerArmor":
        pieces = list(set_data.get("pieces", []))
        title = hero.get("title") or "Характеристики"
    else:
        tier_key = hero.get("tier", "standard")
        tier = (set_data.get("tiers") or {}).get(tier_key, {})
        pieces = list(tier.get("pieces", []))
        title = hero.get("title") or tier_titles.get(tier_key, tier_key)

    cards = "".join(render_card(piece, comp) for piece in pieces)
    stats = (
        '<div class="armor-hero-stats">'
        f'<h2 class="armor-hero-title">{esc(title)}</h2>'
        f'<div class="armor-cards armor-cards--hero">{cards}</div>'
        "</div>"
    )

    image = spec.get("image") or {}
    media = ""
    if image.get("src"):
        media = (
            '<figure class="armor-hero-media">'
            f'<img src="{esc(image["src"])}" alt="{esc(image.get("alt", spec.get("title", "")))}" '
            'loading="lazy" decoding="async">'
            "</figure>"
        )

    if (hero.get("side") or "left") == "right":
        return f'<div class="armor-container armor-hero">{media}{stats}</div>'
    return f'<div class="armor-container armor-hero armor-hero--stats-left">{stats}{media}</div>'


def render_tabs(spec: dict, comp: Companion, set_data: dict, set_areas: list[str], collection: str) -> str:
    page_id = spec["slug"]
    tier_titles = spec.get("tier_titles") or spec.get("tiers") or {}
    base_pieces = list(((set_data.get("tiers") or {}).get("standard") or {}).get("pieces", []))
    counter = 0
    entries: list[tuple[str, str]] = []

    for tab in spec.get("tabs", []):
        title = tab.get("title") or "Вкладка"
        items: list[str] = []
        if tab.get("type") == "tiers":
            for key in tab.get("tiers", []):
                if collection == "powerArmor":
                    break
                tier = (set_data.get("tiers") or {}).get(key)
                if not tier:
                    continue
                counter += 1
                items.append(
                    render_tier_accordion(
                        tier_titles.get(key, key), base_pieces, tier.get("pieces", []), page_id, counter
                    )
                )
        elif tab.get("type") == "mods":
            for category in tab.get("categories", []):
                for mod in mods_for_category(comp, category, set_areas):
                    counter += 1
                    items.append(render_accordion_item(mod, comp, set_areas, page_id, counter))
        if not items:
            continue
        entries.append((title, f'<div class="sppb-accordion" data-sppb-accordion>{"".join(items)}</div>'))

    if not entries:
        return ""

    blocks = []
    for index, (title, content) in enumerate(entries, start=1):
        panel_id = f"panel-{page_id}-{index}"
        blocks.append(
            '<section class="armor-tab" data-armor-tab>'
            '<h3 class="armor-tab-heading">'
            f'<button type="button" class="armor-tab-toggle" aria-expanded="false" '
            f'aria-controls="{esc(panel_id)}">{esc(title)}</button>'
            "</h3>"
            f'<div class="armor-tab-panel" id="{esc(panel_id)}" hidden>{content}</div>'
            "</section>"
        )

    heading = spec.get("tabs_title", "Категории и модификации")
    return (
        '<section class="armor-tabs-section">'
        '<div class="armor-container">'
        f'<h2 class="armor-tabs-title">{esc(heading)}</h2>'
        f'<div class="armor-tabs" data-armor-tabs>{"".join(blocks)}</div>'
        "</div></section>"
    )


def render_page(spec: dict, comp: Companion) -> str:
    collection = spec.get("collection", "armor")
    set_key = spec["set"]
    set_data = comp.power_armor[set_key] if collection == "powerArmor" else comp.armor[set_key]
    set_areas = comp.set_areas(collection, set_key)
    title = spec.get("title") or comp.set_names.get(set_key, set_key)

    back = spec.get("back") or {}
    back_html = ""
    if back.get("title"):
        back_html = (
            '<div class="armor-back"><h4>'
            f'<a href="{esc(back.get("href", "#"))}">{esc(back["title"])}</a>'
            "</h4></div>"
        )

    intro = "".join(f"<p>{paragraph}</p>" for paragraph in spec.get("intro", []))
    lead = f'<div class="armor-container armor-lead">{intro}</div>' if intro else ""
    hero = render_hero(spec, comp, set_data, collection)
    tabs = render_tabs(spec, comp, set_data, set_areas, collection)

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="generator" content="armor2page">
<style>{BASE_CSS}{ARMOR_CSS}</style>
</head>
<body class="armor-body">
<div class="armor-page">
<div class="armor-container armor-header">
{back_html}
<h1 class="armor-title">{esc(title)}</h1>
</div>
{hero}
{lead}
{tabs}
<div class="armor-container armor-footer">Страница собрана из данных Fallout 2d20 Companion</div>
</div>
<script>{SCRIPT}</script>
<script>{ARMOR_SCRIPT}</script>
</body>
</html>
"""


def render_index(pages: list[tuple[str, str]]) -> str:
    items = "".join(
        f'<li><a href="{esc(href)}">{esc(title)}</a></li>' for href, title in pages
    )
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Броня</title>
<meta name="generator" content="armor2page">
<style>{BASE_CSS}
.armor-body{{background:#fff}}
.armor-list{{max-width:760px;margin:60px auto;padding:0 15px}}
.armor-list h1{{margin-bottom:1.2rem}}
.armor-list ul{{margin:0;padding-left:1.2rem}}
.armor-list li{{margin:.45rem 0;font-size:1.05rem}}
</style>
</head>
<body class="armor-body">
<div class="armor-list">
<h1>Броня</h1>
<ul>{items}</ul>
</div>
</body>
</html>
"""


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Собрать страницы брони из данных Companion")
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
        spec = read_json(path)
        if args.only and spec.get("id") != args.only:
            continue
        specs.append(spec)

    if not specs:
        parser.error("не найдено ни одного описания страницы")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    index_entries = []
    for spec in specs:
        document = render_page(spec, comp)
        filename = f"{spec['slug']}.html"
        (out_dir / filename).write_text(document, encoding="utf-8")
        index_entries.append((filename, spec.get("title") or spec["slug"]))
        print(f"{out_dir / filename}  {len(document):,} B")

    (out_dir / "index.html").write_text(render_index(index_entries), encoding="utf-8")
    print(f"{out_dir / 'index.html'}  (index)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
